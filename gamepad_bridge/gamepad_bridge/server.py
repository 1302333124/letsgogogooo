#!/usr/bin/env python3
"""HTTPS/WebSocket relay for forwarding a phone's gamepad state over LAN."""

from __future__ import annotations

import argparse
import asyncio
import io
import ipaddress
import json
import os
import socket
import ssl
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web
import qrcode
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .twist_mapping import gamepad_axes_to_velocity



BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
CERT_DIR = Path(os.environ.get(
    "GAMEPAD_BRIDGE_CERT_DIR", str(Path.home() / ".gamepad_bridge")))
MAX_MESSAGE_BYTES = 64 * 1024


class RosTwistPublisher:
    """Publish the latest browser gamepad command as geometry_msgs/Twist."""

    def __init__(self, *, topic: str, gamepad_index: int,
                 max_linear_x: float, max_linear_y: float,
                 max_angular_z: float, deadzone: float,
                 timeout: float, publish_rate: float) -> None:
        try:
            import rclpy
            from geometry_msgs.msg import Twist
        except ImportError as exc:
            raise RuntimeError(
                "未找到 ROS 2 Python 环境，请先 source /opt/ros/humble/setup.bash") from exc

        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if not 0.0 <= deadzone < 1.0:
            raise ValueError("deadzone must be in [0, 1)")
        self.rclpy = rclpy
        self.Twist = Twist
        self._owns_context = not rclpy.ok()
        if self._owns_context:
            rclpy.init(args=sys.argv)
        self.node = rclpy.create_node("gamepad_twist_bridge")
        self.node.declare_parameter("publish_rate", float(publish_rate))
        self.node.declare_parameter("max_linear_x", float(max_linear_x))
        self.node.declare_parameter("max_linear_y", float(max_linear_y))
        self.node.declare_parameter("max_angular_z", float(max_angular_z))
        self.publish_rate = float(
            self.node.get_parameter("publish_rate").value)
        if self.publish_rate <= 0:
            raise ValueError("publish_rate must be positive")
        self.publisher = self.node.create_publisher(Twist, topic, 10)
        self.topic = topic
        self.gamepad_index = gamepad_index
        self.max_linear_x = abs(float(
            self.node.get_parameter("max_linear_x").value))
        self.max_linear_y = abs(float(
            self.node.get_parameter("max_linear_y").value))
        self.max_angular_z = abs(float(
            self.node.get_parameter("max_angular_z").value))
        self.deadzone = deadzone
        self.timeout = timeout
        self.period = 1.0 / self.publish_rate
        self._velocity = (0.0, 0.0, 0.0)
        self._last_input: float | None = None
        self._running = True

    def update(self, payload: dict[str, Any]) -> None:
        gamepads = payload.get("gamepads")
        if not isinstance(gamepads, list):
            self.clear()
            return
        selected = next((
            gamepad for gamepad in gamepads
            if isinstance(gamepad, dict)
            and gamepad.get("index") == self.gamepad_index
        ), None)
        axes = selected.get("axes", []) if selected else []
        if not isinstance(axes, list):
            axes = []
        self._velocity = gamepad_axes_to_velocity(
            axes, self.max_linear_x, self.max_linear_y,
            self.max_angular_z, self.deadzone)
        self._last_input = time.monotonic()

    def clear(self) -> None:
        self._velocity = (0.0, 0.0, 0.0)
        self._last_input = None

    def _publish(self, velocity: tuple[float, float, float]) -> None:
        message = self.Twist()
        message.linear.x, message.linear.y = velocity[:2]
        message.linear.z = 0.0
        message.angular.x = 0.0
        message.angular.y = 0.0
        message.angular.z = velocity[2]
        self.publisher.publish(message)

    async def run(self) -> None:
        while self._running:
            stale = (
                self._last_input is None
                or time.monotonic() - self._last_input > self.timeout)
            self._publish((0.0, 0.0, 0.0) if stale else self._velocity)
            self.rclpy.spin_once(self.node, timeout_sec=0.0)
            await asyncio.sleep(self.period)

    def close(self) -> None:
        self._running = False
        self.clear()
        self._publish(self._velocity)
        self.rclpy.spin_once(self.node, timeout_sec=0.0)
        self.node.destroy_node()
        if self._owns_context and self.rclpy.ok():
            self.rclpy.shutdown()


def local_ip() -> str:
    """Return the LAN address chosen by the OS, without sending traffic."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        return str(probe.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        probe.close()


def _write_private_key(path: Path, key: rsa.RSAPrivateKey) -> None:
    path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))


def ensure_certificates(hosts: list[str]) -> tuple[Path, Path, Path]:
    """Create a private local CA and a server certificate for the given hosts."""
    CERT_DIR.mkdir(exist_ok=True)
    ca_key_path = CERT_DIR / "ca-key.pem"
    ca_cert_path = CERT_DIR / "gamepad-bridge-ca.crt"
    server_key_path = CERT_DIR / "server-key.pem"
    server_cert_path = CERT_DIR / "server-cert.pem"

    if not ca_key_path.exists() or not ca_cert_path.exists():
        now = datetime.now(timezone.utc)
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Gamepad Bridge"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Gamepad Bridge Local CA"),
        ])
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True, key_encipherment=False,
                    content_commitment=False, data_encipherment=False,
                    key_agreement=False, key_cert_sign=True, crl_sign=True,
                    encipher_only=False, decipher_only=False,
                ),
                critical=True,
            )
            .sign(ca_key, hashes.SHA256())
        )
        _write_private_key(ca_key_path, ca_key)
        ca_cert_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))

    ca_key = serialization.load_pem_private_key(
        ca_key_path.read_bytes(), password=None)
    ca_cert = x509.load_pem_x509_certificate(ca_cert_path.read_bytes())

    wanted_names: list[x509.GeneralName] = []
    for host in dict.fromkeys([*hosts, "localhost", "127.0.0.1"]):
        try:
            wanted_names.append(x509.IPAddress(ipaddress.ip_address(host)))
        except ValueError:
            wanted_names.append(x509.DNSName(host))

    regenerate = True
    if server_key_path.exists() and server_cert_path.exists():
        try:
            old_cert = x509.load_pem_x509_certificate(server_cert_path.read_bytes())
            old_names = set(old_cert.extensions.get_extension_for_class(
                x509.SubjectAlternativeName).value)
            regenerate = not set(wanted_names).issubset(old_names)
        except (ValueError, x509.ExtensionNotFound):
            regenerate = True

    if regenerate:
        now = datetime.now(timezone.utc)
        server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Gamepad Bridge"),
            x509.NameAttribute(NameOID.COMMON_NAME, hosts[0]),
        ])
        server_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(server_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=825))
            .add_extension(x509.SubjectAlternativeName(wanted_names), critical=False)
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )
        _write_private_key(server_key_path, server_key)
        server_cert_path.write_bytes(
            server_cert.public_bytes(serialization.Encoding.PEM))

    return server_cert_path, server_key_path, ca_cert_path


class Relay:
    def __init__(self, public_url: str, ca_path: Path,
                 ros_publisher: RosTwistPublisher | None = None) -> None:
        self.public_url = public_url
        self.ca_path = ca_path
        self.senders: set[web.WebSocketResponse] = set()
        self.receivers: set[web.WebSocketResponse] = set()
        self.latest: dict[str, Any] | None = None
        self.ros_publisher = ros_publisher

    async def broadcast(self, payload: dict[str, Any]) -> None:
        if not self.receivers:
            return
        message = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        stale: list[web.WebSocketResponse] = []
        for peer in self.receivers:
            try:
                await peer.send_str(message)
            except (ConnectionError, RuntimeError):
                stale.append(peer)
        self.receivers.difference_update(stale)

    async def websocket(self, request: web.Request) -> web.WebSocketResponse:
        role = request.query.get("role", "receiver")
        if role not in {"sender", "receiver"}:
            raise web.HTTPBadRequest(text="role must be sender or receiver")

        ws = web.WebSocketResponse(heartbeat=20, max_msg_size=MAX_MESSAGE_BYTES)
        await ws.prepare(request)
        peers = self.senders if role == "sender" else self.receivers
        peers.add(ws)
        if role == "receiver" and self.latest is not None:
            await ws.send_json(self.latest)
        await self.broadcast({
            "type": "peers", "senders": len(self.senders),
            "receivers": len(self.receivers),
        })

        try:
            async for message in ws:
                if message.type != WSMsgType.TEXT or role != "sender":
                    continue
                try:
                    payload = json.loads(message.data)
                except json.JSONDecodeError:
                    await ws.send_json({"type": "error", "message": "invalid JSON"})
                    continue
                if not isinstance(payload, dict) or payload.get("type") != "gamepads":
                    continue
                payload["receivedAt"] = int(
                    datetime.now(timezone.utc).timestamp() * 1000)
                self.latest = payload
                if self.ros_publisher is not None:
                    self.ros_publisher.update(payload)
                await self.broadcast(payload)
        finally:
            peers.discard(ws)
            if role == "sender":
                if not self.senders and self.ros_publisher is not None:
                    self.ros_publisher.clear()
                await self.broadcast({
                    "type": "peers", "senders": len(self.senders),
                    "receivers": len(self.receivers),
                })
        return ws

    async def index(self, request: web.Request) -> web.FileResponse:
        return web.FileResponse(STATIC_DIR / "sender.html")

    async def monitor(self, request: web.Request) -> web.FileResponse:
        return web.FileResponse(STATIC_DIR / "monitor.html")

    async def config(self, request: web.Request) -> web.Response:
        return web.json_response({"phoneUrl": self.public_url})

    async def ca_certificate(self, request: web.Request) -> web.FileResponse:
        response = web.FileResponse(self.ca_path)
        response.headers["Content-Disposition"] = (
            'attachment; filename="gamepad-bridge-ca.crt"')
        return response

    async def qr(self, request: web.Request) -> web.Response:
        image = qrcode.make(self.public_url)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return web.Response(body=buffer.getvalue(), content_type="image/png")


def create_app(public_url: str, ca_path: Path,
               ros_publisher: RosTwistPublisher | None = None) -> web.Application:
    relay = Relay(public_url, ca_path, ros_publisher)
    app = web.Application(client_max_size=MAX_MESSAGE_BYTES)
    if ros_publisher is not None:
        async def ros_lifecycle(_app: web.Application):
            task = asyncio.create_task(ros_publisher.run())
            try:
                yield
            finally:
                ros_publisher.close()
                await task

        app.cleanup_ctx.append(ros_lifecycle)
    app.add_routes([
        web.get("/", relay.index),
        web.get("/monitor", relay.monitor),
        web.get("/ws", relay.websocket),
        web.get("/api/config", relay.config),
        web.get("/ca.crt", relay.ca_certificate),
        web.get("/qr.png", relay.qr),
        web.static("/static", STATIC_DIR),
    ])
    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="局域网手机手柄数据桥接")
    parser.add_argument("--bind", default="0.0.0.0", help="监听地址")
    parser.add_argument("--host", help="手机访问的电脑地址，默认自动检测")
    parser.add_argument("--port", type=int, default=8443, help="HTTPS 端口")
    parser.add_argument(
        "--no-ros", action="store_false", dest="ros",
        help="只运行网页/WebSocket 服务，不发布 ROS 2 Twist")
    parser.set_defaults(ros=True)
    parser.add_argument("--ros-topic", default="/cmd_vel", help="Twist 话题")
    parser.add_argument("--gamepad-index", type=int, default=0, help="使用的手柄编号")
    parser.add_argument("--max-linear-x", type=float, default=0.5,
                        help="最大前后速度，m/s")
    parser.add_argument("--max-linear-y", type=float, default=0.5,
                        help="最大左右速度，m/s")
    parser.add_argument("--max-angular-z", type=float, default=1.0,
                        help="最大旋转速度，rad/s")
    parser.add_argument("--deadzone", type=float, default=0.08,
                        help="摇杆死区，范围 [0, 1)")
    parser.add_argument("--input-timeout", type=float, default=1.0,
                        help="输入超时归零时间，秒")
    parser.add_argument("--publish-rate", type=float, default=20.0,
                        help="Twist 发布频率，Hz")
    argv = sys.argv[1:]
    if "--ros-args" in argv:
        argv = argv[:argv.index("--ros-args")]
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    host = args.host or local_ip()
    cert_path, key_path, ca_path = ensure_certificates(
        [host, socket.gethostname()])
    public_url = f"https://{host}:{args.port}/"
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(cert_path, key_path)
    ros_publisher = None
    if args.ros:
        ros_publisher = RosTwistPublisher(
            topic=args.ros_topic,
            gamepad_index=args.gamepad_index,
            max_linear_x=args.max_linear_x,
            max_linear_y=args.max_linear_y,
            max_angular_z=args.max_angular_z,
            deadzone=args.deadzone,
            timeout=args.input_timeout,
            publish_rate=args.publish_rate,
        )
    print(f"手机发送端: {public_url}", flush=True)
    print(f"电脑监视端: {public_url}monitor", flush=True)
    print(f"手机需信任 CA: {public_url}ca.crt", flush=True)
    if ros_publisher is not None:
        print(
            f"ROS 2 Twist: {ros_publisher.topic} "
            f"@ {ros_publisher.publish_rate:g} Hz "
            f"(x={ros_publisher.max_linear_x:g} m/s, "
            f"y={ros_publisher.max_linear_y:g} m/s, "
            f"yaw={ros_publisher.max_angular_z:g} rad/s)", flush=True)
    web.run_app(
        create_app(public_url, ca_path, ros_publisher),
        host=args.bind, port=args.port,
        ssl_context=ssl_context, print=None,
    )


if __name__ == "__main__":
    main()
