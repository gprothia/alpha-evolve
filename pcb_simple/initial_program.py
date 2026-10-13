"""Starting point for evolution: random placement (usually invalid).
AlphaEvolve / OpenEvolve may only rewrite the code between the EVOLVE-BLOCK markers.
place() must return {name: (x, y)} = centre of every part, in mm.
"""
import math
import random

from problem import BOARD, COMPONENTS, NETS


# EVOLVE-BLOCK-START
def place(seed=0):
    rng = random.Random(seed)
    pos = {}
    for name, (w, h) in COMPONENTS.items():
        pos[name] = (rng.uniform(w / 2, BOARD[0] - w / 2),
                     rng.uniform(h / 2, BOARD[1] - h / 2))
    return pos
# EVOLVE-BLOCK-END
