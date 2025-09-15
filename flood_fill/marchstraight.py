import API
import sys

def log(string):
    sys.stderr.write("{}\n".format(string))
    sys.stderr.flush()


""""""
def main():

    log("Running forwards...")
    API.setColor(0, 0, "G")
    API.setText(0, 0, "abc")
    while True:
        '''test code to see what happens if the mouse hits a wall'''
        '''
        if not API.wallRight():
            API.turnRight()
        while API.wallFront():
            API.turnLeft()
        '''
        API.moveForward()


if __name__ == "__main__":
    main()
