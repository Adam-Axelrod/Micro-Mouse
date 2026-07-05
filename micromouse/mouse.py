from pathlib import Path

import config
import maze
from explorer import Explorer

### Mouse Class -------------------------------------------------------------------------------------

class Mouse(Explorer):
    def __init__(self, belief, destination=None, pos=None):
        super().__init__(belief, destination, pos)
        self.true_pos, self.corners =  self._geometry__init__()

    def _geometry__init__(self):
        true_pos = (config.MM_PER_CELL//2, config.MM_PER_CELL//2)
        corners = []
        return 
