# gamepad_bridge

该 ROS 2 包启动一个 HTTPS 网页服务，手机浏览器通过 Gamepad API 读取蓝牙或 USB
手柄数据，经局域网 WebSocket 发送到电脑，并持续发布标准 `geometry_msgs/msg/Twist`。

速度映射如下：

| 浏览器摇杆轴 | ROS Twist 字段 |
| --- | --- |
| 左摇杆前后（axis 1） | `linear.x` |
| 左摇杆左右（axis 0） | `linear.y` |
| 右摇杆左右（axis 2） | `angular.z` |

其余三个字段始终发布为零。浏览器坐标的正方向是右/下，已转换为 ROS 的前/左/逆时针正方向。

## 安装依赖

```bash
sudo apt install python3-aiohttp python3-cryptography python3-qrcode python3-pil
```

也可以在工作区根目录用 rosdep 安装包中声明的依赖：

```bash
rosdep install --from-paths src --ignore-src -r -y
```

## 构建和运行

从 ROS 2 工作区根目录运行：

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select gamepad_bridge
source install/setup.bash
ros2 run gamepad_bridge gamepad_bridge_server
```

也可以通过 launch 启动：

```bash
ros2 launch gamepad_bridge gamepad_bridge.launch.py
```

launch 参数可以覆盖默认设置，例如：

```bash
ros2 launch gamepad_bridge gamepad_bridge.launch.py \
  port:=9443 ros_topic:=/cmd_vel
```

发布频率和三个最大速度在 `config/gamepad_bridge.yaml` 中设置：

```yaml
gamepad_twist_bridge:
  ros__parameters:
    publish_rate: 200.0
    max_linear_x: 5.0
    max_linear_y: 15.0
    max_angular_z: 10.0
```

终端会输出手机发送端、电脑监视端和 CA 证书的地址。手机需与电脑位于同一局域网，并先安装和信任 CA 证书，才能让浏览器读取手柄。

默认发布 `/cmd_vel`。发布频率和最大速度以 `config/gamepad_bridge.yaml` 的当前设置为准。也可直接用命令行调整：

```bash
ros2 run gamepad_bridge gamepad_bridge_server --ros-topic /cmd_vel --max-linear-x 0.3 --max-linear-y 0.3 --max-angular-z 0.8
```

通过 `--port 9443` 使用其他端口。证书默认保存在 `~/.gamepad_bridge`；可设置 `GAMEPAD_BRIDGE_CERT_DIR` 改为其他目录。
