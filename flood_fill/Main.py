import API
import sys

def log(string):
    sys.stderr.write("{}\n".format(string))
    sys.stderr.flush()




def main():
    log("Running...")
    API.setColor(0, 0, "G")
    API.setText(0, 0, "abc")
    while True:
        maze.get_path()
        mouse.check_walls()
        if blocked:
            maze.calculate_path()
            break
        mouse.move_along_path()

if __name__ == "__main__":
    main()
