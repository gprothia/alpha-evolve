"""Hand-made tidy layout, only to check the evaluator rewards good placement."""
def place(seed=0):
    return {
        "MCU": (25, 25), "XTAL": (25, 19.8), "C1": (30, 23), "C2": (30, 27),
        "LDO": (33, 25), "USB": (39.5, 25), "HDR": (25, 31), "LED": (20, 25),
    }
