"""The problem: board size, parts, and which parts connect. Data only."""

BOARD = (50.0, 50.0)  # width, height in mm

COMPONENTS = {  # name: (width, height) in mm
    "MCU": (7, 7), "XTAL": (3, 2.5), "C1": (1.6, 0.8), "C2": (1.6, 0.8),
    "LDO": (3, 3), "USB": (8, 6), "HDR": (10, 3), "LED": (1.6, 0.8),
}

NETS = [  # parts that must be wired together
    ["MCU", "XTAL"], ["MCU", "C1"], ["MCU", "C2"],
    ["USB", "LDO"], ["LDO", "C1"], ["LDO", "C2"],
    ["MCU", "HDR"], ["MCU", "LED"],
]
