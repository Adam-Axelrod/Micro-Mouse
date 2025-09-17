from mouse import Mouse
import random
import math

TILE_SIZE = 40  # Size of each maze cell in pixels

class AutoMouse(Mouse):
    def __init__(self, x, y, walls, max_y=None, waypoints=None):
        super().__init__(x, y, walls)
        self.auto_mode = True
        self.waypoints = waypoints if waypoints else []
        self.returnpoints = self.waypoints[::-1]
        self.current_waypoint = 0
        self.max_y = max_y

        print(self.waypoints)
        print(self.returnpoints)

    def update(self):
        if not self.waypoints:  # Ensure there are waypoints to follow
            return None

        if self.current_waypoint < len(self.waypoints):
            target_maze_x, target_maze_y = self.waypoints[self.current_waypoint]

            # Flip Y to match screen coordinates
            render_y = self.max_y - target_maze_y
            target_pixel_x = target_maze_x * TILE_SIZE + TILE_SIZE // 2
            target_pixel_y = render_y * TILE_SIZE + TILE_SIZE // 2

            # Vector to target
            dx = target_pixel_x - self.rect.centerx
            dy = target_pixel_y - self.rect.centery
            distance = (dx**2 + dy**2)**0.5

            # If close enough, move to next waypoint
            if distance < TILE_SIZE // 1.5: # higher denominator means mouse needs to get close to the centre of the tile
                self.current_waypoint += 1
                return None

            # Calculate desired angle (Pygame Y-down, positive clockwise)
            desired_angle = math.degrees(math.atan2(dy, dx))
            current_angle = self.angle % 360
            desired_angle = desired_angle % 360

            # Shortest rotation difference [-180, 180]
            angle_diff = (desired_angle - current_angle + 180) % 360 - 180

            # Decide movement
            if abs(angle_diff) < 15:
                return "w"  # Move forward
            elif angle_diff > 0:
                return "d"  # Turn right
            else:
                return "a"  # Turn left

        else:
            self.current_waypoint = 0
            self.waypoints = self.returnpoints #loop
            target_maze_x, target_maze_y = self.waypoints[self.current_waypoint]
            self.returnpoints = self.returnpoints[::-1]
        # self.auto_mode = False #hand control back
        # return None