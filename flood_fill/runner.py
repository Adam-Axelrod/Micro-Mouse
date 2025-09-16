import API
import sys

def log(string):
    sys.stderr.write("{}\n".format(string))
    sys.stderr.flush()


"""hug right wall"""
def main():
    log("Running...")
    API.setColor(0, 0, "G")
    API.setText(0, 0, "abc")
    while True:
        if not API.wallRight():
            API.turnRight()
        while API.wallFront():
            API.turnLeft()
        API.moveForward()


if __name__ == "__main__":
    main()
