import API
import sys
import flood_fill.memorise as memorise

'''will create a mouse that uses memorise.py to map the maze as it goes along
it will then use flood fill to find the shortest path to the centre'''

def log(string):
    sys.stderr.write("{}\n".format(string))
    sys.stderr.flush()

"""hug right wall"""
def main():
    log("Running Write Mode...")
    API.setColor(0, 0, "G")
    API.setText(0, 0, "abc")

    maze = open("data.txt", "w")  



    while True:
        if not API.wallRight():
            API.turnRight()
        while API.wallFront():
            API.turnLeft()
        API.moveForward()


if __name__ == "__main__":
    main()
