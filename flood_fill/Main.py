import API
import sys

def log(string):
    sys.stderr.write("{}\n".format(string))
    sys.stderr.flush()

class Maze:
    def __init__(self, width=None, height=None):
        self.width = width if width is not None else API.mazeWidth()
        self.height = height if height is not None else API.mazeHeight()
        self.walls = []
        self.path = []
        self.distances = []
        self.completed = False
        self.goal_pos = (self.width // 2 - 1, self.height // 2 - 1)  # Default goal position

    def get_goal_pos(self):
        return self.goal_pos
    
    def set_goal_pos(self, pos):
        self.goal_pos = pos
    
    def get_path(self):
        return self.path
    
    def get_walls(self):
        return self.walls
    
    def check_wall_between(self, cell1, cell2):
        x1, y1 = cell1
        x2, y2 = cell2
        if x1 == x2:
            if y1 < y2:
                direction = "n"
            else:
                direction = "s"
        elif y1 == y2:
            if x1 < x2:
                direction = "e"
            else:
                direction = "w"
        else:
            return False  # Not adjacent cells
        return (x1, y1, direction) in self.walls or (x2, y2, {"n": "s", "s": "n", "e": "w", "w": "e"}[direction]) in self.walls
    
    def calculate_distances(self):
        self.distances = []
        for x in range(API.mazeWidth()):
            row = []
            for y in range(API.mazeHeight()):
                row.append(float('inf'))
            self.distances.append(row)
        # Set distances to goal
        goal_x, goal_y = self.get_goal_pos()
        log("Goal Position definitely: {}".format((goal_x, goal_y)))
        self.distances[goal_x][goal_y] = 0
        # Flood fill algorithm to calculate distances
        changed = True
        while changed:
            changed = False
            for x in range(API.mazeWidth()):
                for y in range(API.mazeHeight()):
                    if (x, y) == (goal_x, goal_y):
                        continue
                    min_distance = float('inf')
                    # Check adjacent cells
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < API.mazeWidth() and 0 <= ny < API.mazeHeight():
                            if not self.check_wall_between((x, y), (nx, ny)):
                                # consider neighbor distances except unreachable (inf)
                                if self.distances[nx][ny] != float('inf'):
                                    min_distance = min(min_distance, self.distances[nx][ny])
                    # keep unreachable cells as inf; otherwise set to min+1
                    new_distance = min_distance + 1 if min_distance != float('inf') else float('inf')
                    if new_distance != self.distances[x][y]:
                        self.distances[x][y] = new_distance
                        text = "" if new_distance == float('inf') else str(int(new_distance))
                        API.setText(x,y, text)
                        changed = True

    def get_distances(self):
        return self.distances
    
    def add_wall(self, x, y, direction):
        if (x, y, direction) not in self.walls:
            self.walls.append((x, y, direction))
            API.setWall(x, y, direction)
            log("Added wall at: ({}, {})".format(x, y, direction))
    
    def calculate_path(self, mouse_pos, heading):
        self.path = []
        API.clearAllColor()
        x, y = mouse_pos
        previous_heading = heading
        path_completed = False
        self.calculate_distances()
        log("calculated distances:")
        while not path_completed:
            for square in self.path:
                API.setColor(square[0], square[1], 'G')
            current_distance = self.distances[x][y]

            adjacent_squares = []
            for i, j in [[0, 1], [-1, 0], [1, 0], [0,-1]]:
                if 0 <= x+i < API.mazeWidth() and 0 <= y+j < API.mazeHeight():
                    adjacent_squares.append((x+i, y+j))
                else:
                    adjacent_squares.append(None)

            adjacent_distances = []
            for square in adjacent_squares:
                if square is None:
                    adjacent_distances.append(None)
                else:
                    if 0 <= square[0] < API.mazeWidth() and 0 <= square[1] < API.mazeHeight():
                        adjacent_distances.append(self.distances[square[0]][square[1]])
                    else:
                        adjacent_distances.append(None)
            possible_moves = []
            for square, dist in zip(adjacent_squares, adjacent_distances):
                if dist == current_distance - 1:
                    if not self.check_wall_between((x, y), square):
                        possible_moves.append(square)
            if len(possible_moves) > 1:
                mouse_heading = previous_heading
                next_move = possible_moves[0]
                for move in possible_moves:
                    move_heading = {(x+0, y+1): 'n', (x-1, y+0): 'w', (x+1, y+0): 'e', (x+0, y-1): 's'}[move]
                    if move_heading == mouse_heading:
                        next_move = move
                        break
            elif len(possible_moves) == 1:
                next_move = possible_moves[0]
            else:
                path_completed = True
                break
            if next_move is None:
                path_completed = True
                break
            self.path.append(next_move)
            previous_heading = {(x+0, y+1): 'n', (x-1, y+0): 'w', (x+1, y+0): 'e', (x+0, y-1): 's'}[next_move]
            x, y = next_move

        log("New Path: {}".format(self.path))
    

class Mouse:
    def __init__(self, x, y, heading):
        self.pos = [x, y]
        self.heading = heading

    def get_position(self):
        return self.pos

    def set_pos(self, pos):
        self.pos = [pos[0], pos[1]]

    def get_heading(self):
        return self.heading
    
    def set_heading(self, heading):
        self.heading = heading

    def check_blocked(self, position, path):
        if not path or len(path) < 1:
            return
        next_cell = path[0]
        dx = next_cell[0] - position[0]
        dy = next_cell[1] - position[1]
        if dx == 1:  # Move right
            if self.heading == 'n':
                blocked = API.wallRight()
            elif self.heading == 'e':
                blocked = API.wallFront()
            elif self.heading == 's':
                blocked = API.wallLeft()
            elif self.heading == 'w':
                blocked = API.wallBack()
        elif dx == -1:  # Move left
            if self.heading == 'n':
                blocked = API.wallLeft()
            elif self.heading == 'e':
                blocked = API.wallBack()
            elif self.heading == 's':
                blocked = API.wallRight()
            elif self.heading == 'w':
                blocked = API.wallFront()
        elif dy == 1:  # Move up
            if self.heading == 'n':
                blocked = API.wallFront()
            elif self.heading == 'e':
                blocked = API.wallLeft()
            elif self.heading == 's':
                blocked = API.wallBack()
            elif self.heading == 'w':
                blocked = API.wallRight()
        elif dy == -1:  # Move down
            if self.heading == 'n':
                blocked = API.wallBack()
            elif self.heading == 'e':
                blocked = API.wallRight()
            elif self.heading == 's':
                blocked = API.wallFront()
            elif self.heading == 'w':
                blocked = API.wallLeft()
        else:
            blocked = False  # Not adjacent cells
        if blocked:
            log("Path Blocked at: {}".format(next_cell))
        return blocked

    def turn_left(self):
        API.turnLeft()
    
    def turn_right(self):
        API.turnRight()
    
    def move_forward(self):
        API.moveForward()

    def move_along_path(self, path, heading):
        if not path or len(path) < 1:
            return
        next_cell = path.pop(0)
        log("Moving to: {}".format(next_cell))
        dx = next_cell[0] - self.pos[0]
        dy = next_cell[1] - self.pos[1]
        if dx == 1:  # Move right
            if heading == 'n':
                self.turn_right()
            elif heading == 'e':
                pass
            elif heading == 's':
                self.turn_left()
            elif heading == 'w':
                self.turn_right()
                self.turn_right()
            self.move_forward()
            self.set_pos(next_cell)
            self.set_heading('e')
        elif dx == -1:  # Move left
            if heading == 'n':
                self.turn_left()
            elif heading == 'e':
                self.turn_right()
                self.turn_right()
            elif heading == 's':
                self.turn_right()
            elif heading == 'w':
                pass
            self.move_forward()
            self.set_pos(next_cell)
            self.set_heading('w')
        elif dy == 1:  # Move up
            if heading == 'n':
                pass
            elif heading == 'e':
                self.turn_left()
            elif heading == 's':
                self.turn_right()
                self.turn_right()
            elif heading == 'w':
                self.turn_right()
            self.move_forward()
            self.set_pos(next_cell)
            self.set_heading('n')
        elif dy == -1:  # Move down
            if heading == 'n':
                self.turn_right()
                self.turn_right()
            elif heading == 'e':
                self.turn_right()
            elif heading == 's':
                pass
            elif heading == 'w':
                self.turn_left()
            self.move_forward()
            self.set_pos(next_cell)
            self.set_heading('s')

    def check_walls(self, maze):
        wallfront = API.wallFront()
        wallback = API.wallBack()
        wallleft = API.wallLeft()
        wallright = API.wallRight()

         # Map relative sensor positions to absolute directions based on current heading
        heading_map = {
            'n': {'front': 'n', 'back': 's', 'left': 'w', 'right': 'e'},
            'e': {'front': 'e', 'back': 'w', 'left': 'n', 'right': 's'},
            's': {'front': 's', 'back': 'n', 'left': 'e', 'right': 'w'},
            'w': {'front': 'w', 'back': 'e', 'left': 's', 'right': 'n'},
        }
        m = heading_map.get(self.heading, heading_map['n'])

        if wallfront:
            maze.add_wall(self.pos[0], self.pos[1], m['front'])
        if wallback:
            maze.add_wall(self.pos[0], self.pos[1], m['back'])
        if wallleft:
            maze.add_wall(self.pos[0], self.pos[1], m['left'])
        if wallright:
            maze.add_wall(self.pos[0], self.pos[1], m['right'])
        

def main():
    log("Running...")
    API.setColor(0, 0, "G")
    API.setText(0, 0, "abc")
    mouse = Mouse(0, 0, 'n')
    maze = Maze(API.mazeWidth(), API.mazeHeight())
    goal_pos = maze.width // 2 - 1, maze.height // 2 - 1
    maze.set_goal_pos(goal_pos)
    maze.calculate_path(mouse.get_position(), mouse.get_heading())
    maze.completed = False
    counter = 0
    while True:
        heading = mouse.get_heading()
        position = mouse.get_position()
        mouse.check_walls(maze)
        path = maze.get_path()
        log("Path: {}".format(path))
        log("Position: {}, Heading: {}".format(position, heading))
        log("goal_pos: {}".format(goal_pos))
        log("Completed: {}".format(maze.completed))
        blocked = mouse.check_blocked(position, path)
        if blocked:
            log("Recalculating Path...")
            maze.calculate_path(position, heading)
            path = maze.get_path()
        mouse.move_along_path(path, heading)
        if tuple(position) == goal_pos:
            maze.completed = not maze.completed
            counter = counter + 0.5
            if counter == 5:
                log("Stopping after 5 completions")
                break
            if maze.completed:
                log("Reached Goal at: {}".format(position))
                log('Returning to Start')
                maze.set_goal_pos((0, 0))
                goal_pos = maze.get_goal_pos()
                maze.calculate_path(position, heading)
            else:
                log("Second atempt: {}".format(position))
                goal_pos = maze.width // 2 - 1, maze.height // 2 - 1
                maze.set_goal_pos(goal_pos)
                goal_pos = maze.get_goal_pos()
                maze.calculate_path(position, heading)


if __name__ == "__main__":
    main()
