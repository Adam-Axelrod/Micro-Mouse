import matplotlib.pyplot as plt
import sys

plt.ion()

def plot(scores, mean_scores):
    plt.clf()
    plt.title('Training...')
    plt.xlabel('Number of Games')
    plt.ylabel('Score')
    plt.plot(scores, label='Score')
    plt.plot(mean_scores, label='Mean Score')
    plt.ylim(ymin=0)
    plt.legend()
    plt.text(len(scores)-1, scores[-1], str(scores[-1]))
    plt.text(len(mean_scores)-1, mean_scores[-1], str(mean_scores[-1]))

    if 'ipykernel' in sys.modules:
        from IPython import display
        display.clear_output(wait=True)
        display.display(plt.gcf())
        plt.pause(0.1)
    else:
        plt.draw()
        plt.pause(0.1)

