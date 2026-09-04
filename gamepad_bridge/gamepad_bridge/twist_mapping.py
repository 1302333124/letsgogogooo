"""Pure mapping from browser Gamepad axes to ROS base velocities."""

from __future__ import annotations

import math
from typing import Any


def _axis_value(axes: list[Any], index: int, deadzone: float) -> float:
    """Return one finite, clamped and deadzone-rescaled gamepad axis."""
    if index < 0 or index >= len(axes):
        return 0.0
    try:
        value = float(axes[index])
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value):
        return 0.0
    value = max(-1.0, min(1.0, value))
    if abs(value) <= deadzone:
        return 0.0
    return math.copysign(
        (abs(value) - deadzone) / (1.0 - deadzone), value)


def gamepad_axes_to_velocity(
        axes: list[Any], max_linear_x: float, max_linear_y: float,
        max_angular_z: float, deadzone: float) -> tuple[float, float, float]:
    """
    Map standard browser axes to REP-103 x/y/yaw velocity commands.

    Browser axes are positive right/down. ROS base coordinates are positive
    forward/left/counter-clockwise, hence all three selected axes are negated.
    """
    if not 0.0 <= deadzone < 1.0:
        raise ValueError("deadzone must be in [0, 1)")
    return (
        -_axis_value(axes, 1, deadzone) * abs(max_linear_x),
        -_axis_value(axes, 0, deadzone) * abs(max_linear_y),
        -_axis_value(axes, 2, deadzone) * abs(max_angular_z),
    )
