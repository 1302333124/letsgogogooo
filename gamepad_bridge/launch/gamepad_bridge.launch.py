"""Launch the LAN gamepad bridge and publish geometry_msgs/Twist."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Create the gamepad bridge launch description."""
    arguments = [
        DeclareLaunchArgument('bind', default_value='0.0.0.0'),
        DeclareLaunchArgument('port', default_value='8443'),
        DeclareLaunchArgument('ros_topic', default_value='/cmd_vel'),
        DeclareLaunchArgument('gamepad_index', default_value='0'),
        DeclareLaunchArgument('deadzone', default_value='0.08'),
        DeclareLaunchArgument('input_timeout', default_value='1.0'),
        DeclareLaunchArgument(
            'config_file',
            default_value=PathJoinSubstitution([
                FindPackageShare('gamepad_bridge'),
                'config',
                'gamepad_bridge.yaml',
            ]),
        ),
    ]

    bridge = Node(
        package='gamepad_bridge',
        executable='gamepad_bridge_server',
        output='screen',
        emulate_tty=True,
        arguments=[
            '--bind', LaunchConfiguration('bind'),
            '--port', LaunchConfiguration('port'),
            '--ros-topic', LaunchConfiguration('ros_topic'),
            '--gamepad-index', LaunchConfiguration('gamepad_index'),
            '--deadzone', LaunchConfiguration('deadzone'),
            '--input-timeout', LaunchConfiguration('input_timeout'),
        ],
        parameters=[LaunchConfiguration('config_file')],
    )

    return LaunchDescription([*arguments, bridge])
