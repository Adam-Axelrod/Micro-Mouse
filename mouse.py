"""Differential-drive mouse physics simulation and reflective sensor phototransistor model.

Provides continuous kinematics integration (MouseState) and distance-to-ADC light intensity
mapping for the simulated reflective sensors.
"""

import math
import config
from geometry import cast_ray


class MouseState:
    def __init__(self, start_x_mm=None, start_y_mm=None, start_heading_radians=None):
        if start_x_mm is None:
            start_x_mm = config.MM_PER_CELL / 2.0
        if start_y_mm is None:
            start_y_mm = config.MM_PER_CELL / 2.0
        if start_heading_radians is None:
            start_heading_radians = math.pi / 2.0  # Facing North (+Y)

        self.x_mm = start_x_mm
        self.y_mm = start_y_mm
        self.heading_radians = start_heading_radians
        self.left_encoder_ticks = 0
        self.right_encoder_ticks = 0
        # Exact wheel travel in mm. Ticks are derived from these totals rather
        # than accumulated per step: rounding each step's increment discards the
        # residual in a correlated direction, which is a systematic drift, not
        # noise (~0.5% of distance travelled).
        self._left_travel_mm = 0.0
        self._right_travel_mm = 0.0

    def reset_pose(self, x_mm, y_mm, heading_radians):
        self.x_mm = x_mm
        self.y_mm = y_mm
        self.heading_radians = heading_radians
        self.left_encoder_ticks = 0
        self.right_encoder_ticks = 0
        self._left_travel_mm = 0.0
        self._right_travel_mm = 0.0

    def step(self, left_wheel_speed_mms, right_wheel_speed_mms, delta_time_seconds):
        """Advance mouse pose using differential-drive forward kinematics."""
        track_width_mm = config.TRACK_WIDTH_MM
        linear_velocity = (right_wheel_speed_mms + left_wheel_speed_mms) / 2.0
        angular_velocity = (right_wheel_speed_mms - left_wheel_speed_mms) / track_width_mm

        if abs(angular_velocity) < 1e-6:
            self.x_mm += linear_velocity * math.cos(self.heading_radians) * delta_time_seconds
            self.y_mm += linear_velocity * math.sin(self.heading_radians) * delta_time_seconds
        else:
            # Exact arc integration of dx/dt = v.cos0, dy/dt = v.sin0, d0/dt = w:
            #   x += R.(sin 0_new - sin 0_old)
            #   y += R.(cos 0_old - cos 0_new)
            # The y term subtracts the NEW cosine from the OLD one, not the other
            # way round -- reversing it mirrors every arc about the horizontal.
            turn_radius = linear_velocity / angular_velocity
            new_heading = self.heading_radians + angular_velocity * delta_time_seconds
            self.x_mm += turn_radius * (math.sin(new_heading) - math.sin(self.heading_radians))
            self.y_mm += turn_radius * (math.cos(self.heading_radians) - math.cos(new_heading))
            self.heading_radians = new_heading

        # Keep heading within [0, 2*pi)
        self.heading_radians = self.heading_radians % (2.0 * math.pi)

        # Accumulate exact travel, then derive ticks from the running total so the
        # rounding residual never compounds.
        self._left_travel_mm += left_wheel_speed_mms * delta_time_seconds
        self._right_travel_mm += right_wheel_speed_mms * delta_time_seconds
        self.left_encoder_ticks = round(self._left_travel_mm / config.MM_PER_TICK)
        self.right_encoder_ticks = round(self._right_travel_mm / config.MM_PER_TICK)

    def sensor_position_and_angle(self, sensor_name):
        """Compute world coordinate (x, y) and absolute angle (radians) of a sensor."""
        mount = config.SENSOR_MOUNTS.get(sensor_name)
        if mount is None:
            raise ValueError(f"Unknown sensor name: {sensor_name}")
        local_offset_x = mount["lateral_mm"]
        local_offset_y = mount["forward_mm"]
        relative_angle = mount["angle_rad"]

        cos_heading = math.cos(self.heading_radians)
        sin_heading = math.sin(self.heading_radians)

        world_x = self.x_mm + (local_offset_y * cos_heading - local_offset_x * sin_heading)
        world_y = self.y_mm + (local_offset_y * sin_heading + local_offset_x * cos_heading)
        absolute_angle = (self.heading_radians + relative_angle) % (2.0 * math.pi)

        return (world_x, world_y), absolute_angle

    def read_sensor_adc(self, sensor_name, wall_segments):
        """Cast ray for sensor_name and convert distance to 16-bit ADC light intensity."""
        origin, angle = self.sensor_position_and_angle(sensor_name)
        distance_mm = cast_ray(origin, angle, wall_segments,
                               max_range_mm=config.SENSOR_RANGE_MM)

        # Phototransistor reflectance model: intensity = K / (d + d0)^2
        if distance_mm >= config.SENSOR_BACKGROUND_MM:
            return config.SENSOR_ADC_FLOOR

        intensity = config.SENSOR_INTENSITY_SCALE / (
            (distance_mm + config.SENSOR_DISTANCE_OFFSET_MM) ** 2
        )
        return int(min(max(intensity, float(config.SENSOR_ADC_FLOOR)),
                       float(config.SENSOR_ADC_CEILING)))
