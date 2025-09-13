import API
import sys

def log(string):
    sys.stderr.write("{}\n".format(string))
    sys.stderr.flush()

class maze:
    walls = []
    path = []
    distances = []
    completed = False

    def get_path():
        x, y = mouse.get_position()
        while maze.completed:
            current_distance = maze.distances[x][y]
            adajcent_distances = [[maze.distances[-1][1], maze.distances[0][1], maze.distances[1][1]],
                                  [maze.distances[-1][0], current_distance, maze.distances[1][0]],
                                  [maze.distances[-1][-1], maze.distances[0][-1], maze.distances[1][-1]]]
            possible_moves = adajcent_distances < current_distance
            if possible_moves.len() >= 2:
                heading = mouse.get_heading()
                for move in possible_moves:
                    if move == heading:
                        next_move = move
                        break
            elif possible_moves.len() == 1:
                next_move = possible_moves[0]
            else:
                maze.completed = True
                break
            maze.path.append(next_move)
            x, y = next_move
        log("New Path: {}".format(maze.path))
            
    
    def get_walls():
        maze.walls = API.getWalls()
        log("Walls: {}".format(maze.walls))
    
    def calculate_distances():
        maze.distances = API.getDistances()
        log("Distances: {}".format(maze.distances))

    def get_distances():
        maze.distances = API.getDistances()
        log("Distances: {}".format(maze.distances))
    
    def calculate_path():
        maze.distances = API.getDistances()
        log("Distances: {}".format(maze.distances))
        maze.path = API.getMousePath()
        log("New Path: {}".format(maze.path))
    
    def add_wall(x, y, direction):
        if (x, y, direction) not in maze.walls:
            maze.walls.append((x, y, direction))
            API.setWall(x, y, direction)
            log("Added wall at: ({}, {})".format(x, y, direction))
    

class mouse:
    pos = []
    heading = []
    blocked = False

    def get_position():
        mouse.pos = API.getMousePos()
        log("Mouse Position: {}".format(mouse.pos))
        return mouse.pos

    def get_heading():
        mouse.direction = API.getMouseDir()
        log("Mouse Heading: {}".format(mouse.heading))
        return mouse.heading

    def turn_left():
        API.turnLeft()
        mouse.heading.append("L")
    
    def turn_right():
        API.turnRight()
        mouse.heading.append("R")
    
    def move_forward():
        API.moveForward()
        mouse.heading.append("F")
        mouse.pos = API.getMousePos()
    
    def move_along_path():
        if not maze.path:
            return
        next_cell = maze.path.pop(0)
        dx = next_cell[0] - mouse.pos[0]
        dy = next_cell[1] - mouse.pos[1]
        if dx == 1:  # Move right
            while API.getMouseDir() != 0:
                mouse.turn_right()
            mouse.move_forward()
        elif dx == -1:  # Move left
            while API.getMouseDir() != 2:
                mouse.turn_right()
            mouse.move_forward()
        elif dy == 1:  # Move down
            while API.getMouseDir() != 1:
                mouse.turn_right()
            mouse.move_forward()
        elif dy == -1:  # Move up
            while API.getMouseDir() != 3:
                mouse.turn_right()
            mouse.move_forward()

    def check_walls():
        wallfront = API.wallFront()
        wallback = API.wallBack()
        wallleft = API.wallLeft()
        wallright = API.wallRight()
        if wallfront:
            maze.add_wall(mouse.pos[0], mouse.pos[1], "n")
        if wallback:
            maze.add_wall(mouse.pos[0], mouse.pos[1], "s")
        if wallleft:
            maze.add_wall(mouse.pos[0], mouse.pos[1], "w")
        if wallright:
            maze.add_wall(mouse.pos[0], mouse.pos[1], "e")
        

def main():
    log("Running...")
    API.setColor(0, 0, "G")
    API.setText(0, 0, "abc")
    while True:
        maze.get_path()
        mouse.check_walls()
        if mouse.blocked:
            maze.calculate_path()
            break
        mouse.move_along_path()

if __name__ == "__main__":
    main()
