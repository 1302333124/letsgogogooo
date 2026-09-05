```text
话题：/cmd_vel
类型：geometry_msgs/msg/Twist
```

## 1. 安装依赖


```bash
sudo apt install python3-aiohttp python3-cryptography python3-qrcode python3-pil
```

## 2. 编译

```bash

colcon build --symlink-install --packages-select gamepad_bridge
source install/setup.bash
```

## 3. 启动

```bash
source install/setup.bash
ros2 launch gamepad_bridge gamepad_bridge.launch.py
```



tips：端口 `8443` 被占用时，可以更换端口：

```bash
ros2 launch gamepad_bridge gamepad_bridge.launch.py port:=9443
```
