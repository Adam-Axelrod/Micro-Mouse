import API
import sys

def log(string):
    sys.stderr.write("{}\n".format(string))
    sys.stderr.flush()

class Maze:
    walls = []
    path = []
    distances = []
    completed = False

    def get_path():
        return Maze.path
    
    def get_walls():
        return Maze.walls
    
    def calculate_distances():
        Maze.distances = API.getDistances()
        log("Distances: {}".format(Maze.distances))

    def get_distances():
        return Maze.distances
    
    def add_wall(x, y, direction):
        if (x, y, direction) not in Maze.walls:
            Maze.walls.append((x, y, direction))
            API.setWall(x, y, direction)
            log("Added wall at: ({}, {})".format(x, y, direction))
    
    def calculate_path():
        x, y = Mouse.get_position()
        while Maze.completed:
            current_distance = Maze.distances[x][y]
            adajcent_distances = [[Maze.distances[-1][1], Maze.distances[0][1], Maze.distances[1][1]],
                                  [Maze.distances[-1][0], current_distance, Maze.distances[1][0]],
                                  [Maze.distances[-1][-1], Maze.distances[0][-1], Maze.distances[1][-1]]]
            possible_moves = adajcent_distances < current_distance
            if possible_moves.len() >= 2:
                heading = Mouse.get_heading()
                for move in possible_moves:
                    if move == heading:
                        next_move = move
                        break
            elif possible_moves.len() == 1:
                next_move = possible_moves[0]
            else:
                Maze.completed = True
                break
            Maze.path.append(next_move)
            x, y = next_move
        log("New Path: {}".format(Maze.path))
    

    

class Mouse:
    pos = []
    heading = []
    blocked = False

    def get_position():
        return Mouse.pos

    def get_heading():
        return Mouse.heading

    def turn_left():
        API.turnLeft()
        Mouse.heading.append("L")
    
    def turn_right():
        API.turnRight()
        Mouse.heading.append("R")
    
    def move_forward():
        API.moveForward()
        Mouse.heading.append("F")
        Mouse.pos = API.getMousePos()
    
    def move_along_path():
        if not Maze.path:
            return
        next_cell = Maze.path.pop(0)
        dx = next_cell[0] - Mouse.pos[0]
        dy = next_cell[1] - Mouse.pos[1]
        if dx == 1:  # Move right
            while API.getMouseDir() != 0:
                Mouse.turn_right()
            Mouse.move_forward()
        elif dx == -1:  # Move left
            while API.getMouseDir() != 2:
                Mouse.turn_right()
            Mouse.move_forward()
        elif dy == 1:  # Move down
            while API.getMouseDir() != 1:
                Mouse.turn_right()
            Mouse.move_forward()
        elif dy == -1:  # Move up
            while API.getMouseDir() != 3:
                Mouse.turn_right()
            Mouse.move_forward()

    def check_walls():
        wallfront = API.wallFront()
        wallback = API.wallBack()
        wallleft = API.wallLeft()
        wallright = API.wallRight()
        if wallfront:
            Maze.add_wall(Mouse.pos[0], Mouse.pos[1], "n")
        if wallback:
            Maze.add_wall(Mouse.pos[0], Mouse.pos[1], "s")
        if wallleft:
            Maze.add_wall(Mouse.pos[0], Mouse.pos[1], "w")
        if wallright:
            Maze.add_wall(Mouse.pos[0], Mouse.pos[1], "e")
        

def main():
    log("Running...")
    API.setColor(0, 0, "G")
    API.setText(0, 0, "abc")
    while True:
        Maze.get_path()
        Mouse.check_walls()
        if Mouse.blocked:
            Maze.calculate_path()
            break
        Mouse.move_along_path()

if __name__ == "__main__":
    main()
