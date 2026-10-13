"""Scores a placement program. Run it directly:  python evaluator.py [program.py]
AlphaEvolve / OpenEvolve call evaluate(program_path) and use 'combined_score'.
"""
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # so the candidate can `from problem import ...`
if not os.path.exists(os.path.join(HERE, "problem.py")):
    sys.path.insert(0, "/Users/prothiag/code/agents/pcb_simple")
from problem import BOARD, COMPONENTS, NETS  # noqa: E402

GAP = 0.3  # minimum clearance between parts, mm


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def evaluate(program_path):
    # 1. Load the candidate and run place()
    try:
        spec = importlib.util.spec_from_file_location("candidate", program_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pos = mod.place()
    except Exception as e:
        print("candidate crashed:", e)
        return {"combined_score": 0.0, "valid": 0.0}

    # 2. Hard rules. Any violation -> score 0
    names = list(COMPONENTS)
    try:
        if set(pos) != set(names):
            raise ValueError("wrong set of parts")
        for n in names:
            x, y = float(pos[n][0]), float(pos[n][1])
            w, h = COMPONENTS[n]
            if not (math.isfinite(x) and math.isfinite(y)):
                raise ValueError("bad number")
            if not (w / 2 <= x <= BOARD[0] - w / 2 and h / 2 <= y <= BOARD[1] - h / 2):
                raise ValueError(f"{n} is off the board")
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                (w1, h1), (w2, h2) = COMPONENTS[a], COMPONENTS[b]
                if (abs(pos[a][0] - pos[b][0]) < (w1 + w2) / 2 + GAP and
                        abs(pos[a][1] - pos[b][1]) < (h1 + h2) / 2 + GAP):
                    raise ValueError(f"{a} overlaps {b}")
    except Exception as e:
        print("invalid layout:", e)
        return {"combined_score": 0.0, "valid": 0.0}

    # 3. Measurements
    hpwl = 0.0  # total half-perimeter wirelength
    for net in NETS:
        xs = [pos[n][0] for n in net]
        ys = [pos[n][1] for n in net]
        hpwl += (max(xs) - min(xs)) + (max(ys) - min(ys))
    xtal = dist(pos["XTAL"], pos["MCU"])
    decap = (dist(pos["C1"], pos["MCU"]) + dist(pos["C2"], pos["MCU"])) / 2
    ldo_xtal = dist(pos["LDO"], pos["XTAL"])

    # 4. Cost (lower = better) -> score in (0, 1] (higher = better)
    cost = 1.0 * hpwl + 3.0 * xtal + 3.0 * decap - 0.5 * min(ldo_xtal, 20)
    score = 1.0 / (1.0 + max(cost, 0.0) / 25.0)

    return {"combined_score": score, "valid": 1.0, "wirelength": hpwl,
            "xtal_dist": xtal, "decap_dist": decap, "ldo_to_xtal": ldo_xtal}


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Evaluate a PCB placement program.")
    parser.add_argument("program_path", nargs="?", default=None, help="Path to candidate program.py")
    parser.add_argument("--program-dir", default=None, help="Directory containing initial_program.py (used by AlphaEvolve ae CLI)")
    parser.add_argument("--input-program-file", default=None, help="Path to candidate program file (used by AlphaEvolve ae CLI)")
    parser.add_argument("--output-file", default=None, help="Path to JSON score output file (used by AlphaEvolve ae CLI)")
    args = parser.parse_args()

    if args.input_program_file:
        path = args.input_program_file
    elif args.program_dir:
        path = os.path.join(args.program_dir, "initial_program.py")
    elif args.program_path:
        path = args.program_path
    else:
        path = os.path.join(HERE, "initial_program.py")

    metrics = evaluate(path)
    for k, v in metrics.items():
        print(f"{k:15} {v:.3f}")

    if args.output_file:
        score = float(metrics.get("combined_score", 0.0))
        insights = [
            {"label": "metrics", "text": ", ".join(f"{k}={v:.3f}" for k, v in metrics.items())}
        ]
        with open(args.output_file, "w", encoding="utf-8") as f:
            json.dump({"score": score, "insights": insights}, f, indent=2)

