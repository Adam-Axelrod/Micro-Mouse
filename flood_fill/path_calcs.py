path = [(0, 1), (1, 1), (2, 1), (2, 2), (3, 2),
            (3, 3), (4, 3), (4, 4), (3, 4), (3, 5),
            (2, 5), (2, 6), (1, 6), (1, 7), (1, 8),
            (1, 9), (1, 10), (1, 11), (1, 12), (1, 13),
            (1, 14), (0, 14), (0, 15), (1, 15), (2, 15),
            (3, 15), (4, 15), (5, 15), (6, 15), (7, 15),
            (7, 14), (8, 14), (8, 13), (9, 13), (9, 14),
            (10, 14), (10, 13), (11, 13), (11, 12), (11, 11),
            (11, 10), (11, 9), (11, 8), (10, 8), (10, 7),
            (9, 7), (9, 6), (8, 6), (8, 5), (7, 5), (6, 5),
            (6, 6), (7, 6), (7, 7)]

def generate_turns(path):
    if len(path) < 3:
        return path[:]  # Nothing to simplify

    simplified = [path[0]]
    prev_dx = path[1][0] - path[0][0]
    prev_dy = path[1][1] - path[0][1]

    for i in range(2, len(path)):
        dx = path[i][0] - path[i - 1][0]
        dy = path[i][1] - path[i - 1][1]

        # direction change = turn
        if (dx, dy) != (prev_dx, prev_dy):
            simplified.append(path[i - 1])
        prev_dx, prev_dy = dx, dy

    simplified.append(path[-1])  # always include the goal
    return simplified