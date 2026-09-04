from glob import glob
import os

from setuptools import find_packages, setup

package_name = 'gamepad_bridge'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        (os.path.join('share', package_name, 'launch'),
         glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'),
         glob('config/*.yaml')),
    ],
    install_requires=[
        'setuptools',
        'aiohttp>=3.8,<4',
        'cryptography>=3.4',
        'qrcode[pil]>=7.3,<9',
    ],
    zip_safe=True,
    package_data={'gamepad_bridge': ['static/*']},
    maintainer='destin',
    maintainer_email='1302333124@qq.com',
    description='LAN browser gamepad to ROS 2 Twist bridge',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'gamepad_bridge_server = gamepad_bridge.server:main',
        ],
    },
)
