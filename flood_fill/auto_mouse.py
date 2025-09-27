import math
from mouse import Mouse
from actions import Action

class AutoMouse(Mouse):
    def __init__(self, x, y, walls, tile_size, colour, max_y, path=None):
        super().__init__(x, y, walls, tile_size, colour)
        self.tile_size = tile_size
        self.auto_mode = True
        self.path = path if path else []
        self.returnpoints = self.path[::-1]
        self.current_waypoint = 0
        self.max_y=max_y

    def update(self):
        if not self.path:  # Ensure there are path to follow
            return []

        if self.current_waypoint < len(self.path):
            target_maze_x, target_maze_y = self.path[self.current_waypoint]

            # Flip Y to match screen coordinates
            render_y = self.max_y - target_maze_y
            target_pixel_x = target_maze_x * self.tile_size + self.tile_size // 2
            target_pixel_y = render_y * self.tile_size + self.tile_size // 2

            # Vector to target
            dx = target_pixel_x - self.rect.centerx
            dy = target_pixel_y - self.rect.centery
            distance = (dx**2 + dy**2)**0.5

            # If close enough, move to next waypoint
            if distance < self.tile_size // 0.75: # higher denominator means mouse needs to get close to the centre of the tile
                self.current_waypoint += 1
                return []

            # Calculate desired angle (Pygame Y-down, positive clockwise)
            desired_angle = math.degrees(math.atan2(dy, dx))
            current_angle = self.angle % 360
            desired_angle = desired_angle % 360

            # Shortest rotation difference [-180, 180]
            angle_diff = (desired_angle - current_angle + 180) % 360 - 180

            # Decide movement
            if abs(angle_diff) < 15:
                return [Action.MOVE_FORWARD]
            elif angle_diff > 0:
                return [Action.TURN_RIGHT]
            elif angle_diff < 0:
                return [Action.TURN_LEFT]  # Turn left
            else:
                return []
            
        else:
            self.current_waypoint = 0
            self.path = self.returnpoints #loop
            target_maze_x, target_maze_y = self.path[self.current_waypoint]
            self.returnpoints = self.returnpoints[::-1]
        # self.auto_mode = False #hand control back
        return []