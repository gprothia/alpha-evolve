"""Starting point for evolution: random placement (usually invalid).
AlphaEvolve / OpenEvolve may only rewrite the code between the EVOLVE-BLOCK markers.
place() must return {name: (x, y)} = centre of every part, in mm.
"""
import math
import random

from problem import BOARD, COMPONENTS, NETS


# EVOLVE-BLOCK-START
def place(seed=0):
    import math
    import random

    rng = random.Random(seed)
    W = float(BOARD[0])
    H = float(BOARD[1])
    clearance = float(globals().get('CLEARANCE', 0.3))
    c_target = clearance + 0.035  # Safety margin ensuring strict clearance compliance

    comp_names = list(COMPONENTS.keys())
    n = len(comp_names)
    name_to_idx = {name: i for i, name in enumerate(comp_names)}

    # Identify component roles
    mcu_name = next((k for k in comp_names if any(s in k.lower() for s in ('mcu', 'u1', 'soc', 'proc'))), None)
    if mcu_name is None:
        mcu_name = max(comp_names, key=lambda k: COMPONENTS[k][0] * COMPONENTS[k][1])

    xtal_name = next((k for k in comp_names if any(s in k.lower() for s in ('xtal', 'osc', 'crystal')) or k.lower().startswith('y')), None)
    ldo_name = next((k for k in comp_names if any(s in k.lower() for s in ('ldo', 'vreg', 'reg', 'pwr')) and k != mcu_name), None)
    if ldo_name is None:
        ldo_name = next((k for k in comp_names if k not in (mcu_name, xtal_name) and any(s in k.lower() for s in ('u2', 'vr', 'ic2', 'u'))), None)

    decap_names = [k for k in comp_names if k not in (mcu_name, xtal_name, ldo_name) and any(s in k.lower() for s in ('decap', 'cap', 'c'))]
    other_names = [k for k in comp_names if k not in (mcu_name, xtal_name, ldo_name) and k not in decap_names]

    mcu_idx = name_to_idx.get(mcu_name)
    xtal_idx = name_to_idx.get(xtal_name)
    ldo_idx = name_to_idx.get(ldo_name)
    decap_idxs = [name_to_idx[k] for k in decap_names if k in name_to_idx]

    ws = [float(COMPONENTS[k][0]) for k in comp_names]
    hs = [float(COMPONENTS[k][1]) for k in comp_names]
    min_x = [ws[i] * 0.5 + 0.05 for i in range(n)]
    max_x = [max(min_x[i], W - ws[i] * 0.5 - 0.05) for i in range(n)]
    min_y = [hs[i] * 0.5 + 0.05 for i in range(n)]
    max_y = [max(min_y[i], H - hs[i] * 0.5 - 0.05) for i in range(n)]

    # Robust netlist extraction
    raw_nets = None
    for k in ('NETS', 'nets', 'NETLIST', 'netlist', 'CONNECTIONS', 'connections'):
        if k in globals() and globals()[k]:
            raw_nets = globals()[k]
            break
    if raw_nets is None:
        for k, v in globals().items():
            if not k.startswith('__') and k not in ('BOARD', 'COMPONENTS', 'CLEARANCE', 'place'):
                if isinstance(v, (list, tuple, dict)) and len(v) > 0:
                    raw_nets = v
                    break

    nets_idx = []
    if raw_nets:
        items = raw_nets.values() if isinstance(raw_nets, dict) else raw_nets
        for item in items:
            nodes = None
            if isinstance(item, dict):
                for nk in ('nodes', 'pins', 'components', 'parts', 'net'):
                    if nk in item:
                        nodes = item[nk]
                        break
                if nodes is None:
                    nodes = list(item.values())
            elif isinstance(item, (list, tuple, set)):
                nodes = item
            if not nodes:
                continue

            comps = []
            for node in nodes:
                cname = None
                if isinstance(node, str):
                    cname = node.split('.')[0] if '.' in node else node
                elif isinstance(node, (list, tuple)) and len(node) > 0:
                    cname = node[0] if isinstance(node[0], str) else None
                elif isinstance(node, dict):
                    cname = node.get('component') or node.get('part') or node.get('comp')
                if cname and cname in name_to_idx:
                    comps.append(name_to_idx[cname])
            comps = list(dict.fromkeys(comps))
            if len(comps) >= 2:
                nets_idx.append(comps)

    # Component graph adjacency for barycentric placement
    adj = {i: [] for i in range(n)}
    for net in nets_idx:
        for i in range(len(net)):
            for j in range(i + 1, len(net)):
                adj[net[i]].append(net[j])
                adj[net[j]].append(net[i])

    def compute_cost(xs, ys):
        viol_cost = 0.0
        num_viols = 0

        # Boundary checks
        for i in range(n):
            xi, yi, wi2, hi2 = xs[i], ys[i], ws[i] * 0.5, hs[i] * 0.5
            if xi - wi2 < 0.0:
                v = -(xi - wi2)
                viol_cost += 5000.0 * v + 50000.0 * v * v
                num_viols += 1
            elif xi + wi2 > W:
                v = (xi + wi2) - W
                viol_cost += 5000.0 * v + 50000.0 * v * v
                num_viols += 1
            if yi - hi2 < 0.0:
                v = -(yi - hi2)
                viol_cost += 5000.0 * v + 50000.0 * v * v
                num_viols += 1
            elif yi + hi2 > H:
                v = (yi + hi2) - H
                viol_cost += 5000.0 * v + 50000.0 * v * v
                num_viols += 1

        # Pairwise clearance checks
        for i in range(n):
            xi, yi, wi, hi = xs[i], ys[i], ws[i], hs[i]
            for j in range(i + 1, n):
                dx = abs(xi - xs[j]) - (wi + ws[j]) * 0.5
                dy = abs(yi - ys[j]) - (hi + hs[j]) * 0.5
                sep = dx if dx > dy else dy
                if sep < c_target:
                    v = c_target - sep
                    viol_cost += 3000.0 * v + 50000.0 * v * v
                    num_viols += 1

        # HPWL Wirelength
        wl = 0.0
        for net in nets_idx:
            mn_x = mx_x = xs[net[0]]
            mn_y = mx_y = ys[net[0]]
            for k in range(1, len(net)):
                idx = net[k]
                xk, yk = xs[idx], ys[idx]
                if xk < mn_x: mn_x = xk
                elif xk > mx_x: mx_x = xk
                if yk < mn_y: mn_y = yk
                elif yk > mx_y: mx_y = yk
            wl += (mx_x - mn_x) + (mx_y - mn_y)

        # MCU to XTAL distance (minimize)
        d_xtal = 0.0
        if mcu_idx is not None and xtal_idx is not None:
            dx = xs[mcu_idx] - xs[xtal_idx]
            dy = ys[mcu_idx] - ys[xtal_idx]
            d_xtal = math.sqrt(dx * dx + dy * dy)

        # MCU to Decap distance (minimize)
        d_decap = 0.0
        if mcu_idx is not None and decap_idxs:
            mx, my = xs[mcu_idx], ys[mcu_idx]
            for didx in decap_idxs:
                dx = mx - xs[didx]
                dy = my - ys[didx]
                d_decap += math.sqrt(dx * dx + dy * dy)

        # LDO away from XTAL (maximize distance)
        d_ldo_xtal = 0.0
        if ldo_idx is not None and xtal_idx is not None:
            dx = xs[ldo_idx] - xs[xtal_idx]
            dy = ys[ldo_idx] - ys[xtal_idx]
            d_ldo_xtal = math.sqrt(dx * dx + dy * dy)

        total_cost = (
            viol_cost
            + 1.0 * wl
            + 3.5 * d_xtal
            + 2.5 * d_decap
            - 2.0 * d_ldo_xtal
        )
        return total_cost, num_viols

    def legalize_layout(xs, ys, max_iters=40):
        for _ in range(max_iters):
            violated = False
            for i in range(n):
                for j in range(i + 1, n):
                    dx = abs(xs[i] - xs[j]) - (ws[i] + ws[j]) * 0.5
                    dy = abs(ys[i] - ys[j]) - (hs[i] + hs[j]) * 0.5
                    sep = dx if dx > dy else dy
                    if sep < c_target:
                        violated = True
                        push = (c_target - sep) * 0.52
                        if dx > dy:
                            sign = 1.0 if xs[i] >= xs[j] else -1.0
                            xs[i] = max(min_x[i], min(max_x[i], xs[i] + sign * push))
                            xs[j] = max(min_x[j], min(max_x[j], xs[j] - sign * push))
                        else:
                            sign = 1.0 if ys[i] >= ys[j] else -1.0
                            ys[i] = max(min_y[i], min(max_y[i], ys[i] + sign * push))
                            ys[j] = max(min_y[j], min(max_y[j], ys[j] - sign * push))
            if not violated:
                break

    candidates = []

    # Diagonal layouts: XTAL towards one corner, LDO placed in the opposite diagonal corner
    diagonal_configs = [
        # (mcu_rel_x, mcu_rel_y, xtal_side, ldo_corner_x, ldo_corner_y)
        (0.38, 0.38, 'left', 1.0, 1.0),
        (0.38, 0.38, 'bottom', 1.0, 1.0),
        (0.38, 0.62, 'left', 1.0, 0.0),
        (0.38, 0.62, 'top', 1.0, 0.0),
        (0.62, 0.38, 'right', 0.0, 1.0),
        (0.62, 0.38, 'bottom', 0.0, 1.0),
        (0.62, 0.62, 'right', 0.0, 0.0),
        (0.62, 0.62, 'top', 0.0, 0.0),
        (0.50, 0.50, 'left', 1.0, 1.0),
        (0.50, 0.50, 'bottom', 1.0, 1.0),
        (0.50, 0.50, 'top', 0.0, 0.0),
        (0.50, 0.50, 'right', 0.0, 0.0),
    ]

    for m_rx, m_ry, xtal_side, ldo_cx, ldo_cy in diagonal_configs:
        xs = [W * 0.5] * n
        ys = [H * 0.5] * n

        mx = W * m_rx
        my = H * m_ry
        if mcu_idx is not None:
            xs[mcu_idx] = mx
            ys[mcu_idx] = my

        # Place XTAL flush against MCU edge
        side_slots = ['left', 'bottom', 'top', 'right']
        if xtal_idx is not None and mcu_idx is not None:
            wm, hm = ws[mcu_idx], hs[mcu_idx]
            wx, hx = ws[xtal_idx], hs[xtal_idx]
            if xtal_side == 'left':
                xs[xtal_idx] = mx - (wm + wx) * 0.5 - c_target
                ys[xtal_idx] = my
            elif xtal_side == 'right':
                xs[xtal_idx] = mx + (wm + wx) * 0.5 + c_target
                ys[xtal_idx] = my
            elif xtal_side == 'bottom':
                xs[xtal_idx] = mx
                ys[xtal_idx] = my - (hm + hx) * 0.5 - c_target
            elif xtal_side == 'top':
                xs[xtal_idx] = mx
                ys[xtal_idx] = my + (hm + hx) * 0.5 + c_target

        # Place LDO in opposite corner
        if ldo_idx is not None:
            xs[ldo_idx] = max_x[ldo_idx] if ldo_cx > 0.5 else min_x[ldo_idx]
            ys[ldo_idx] = max_y[ldo_idx] if ldo_cy > 0.5 else min_y[ldo_idx]

        # Place decaps snugly around remaining MCU edges
        open_sides = [s for s in side_slots if s != xtal_side]
        for s_i, didx in enumerate(decap_idxs):
            side = open_sides[s_i % len(open_sides)]
            wm, hm = ws[mcu_idx], hs[mcu_idx]
            wd, hd = ws[didx], hs[didx]
            offset = 1.2 * ((s_i // len(open_sides)) - 0.5)
            if side == 'left':
                xs[didx] = mx - (wm + wd) * 0.5 - c_target
                ys[didx] = my + offset
            elif side == 'right':
                xs[didx] = mx + (wm + wd) * 0.5 + c_target
                ys[didx] = my + offset
            elif side == 'bottom':
                xs[didx] = mx + offset
                ys[didx] = my - (hm + hd) * 0.5 - c_target
            elif side == 'top':
                xs[didx] = mx + offset
                ys[didx] = my + (hm + hd) * 0.5 + c_target

        # Place other components near their connected neighbors (Barycenter)
        for o_name in other_names:
            oidx = name_to_idx[o_name]
            neighbors = [nb for nb in adj[oidx] if nb not in other_names]
            if neighbors:
                xs[oidx] = sum(xs[nb] for nb in neighbors) / len(neighbors)
                ys[oidx] = sum(ys[nb] for nb in neighbors) / len(neighbors)
            else:
                # Place near board edge close to LDO
                xs[oidx] = (xs[ldo_idx] + mx) * 0.5 if ldo_idx is not None else W * 0.7
                ys[oidx] = (ys[ldo_idx] + my) * 0.5 if ldo_idx is not None else H * 0.7

        for i in range(n):
            xs[i] = max(min_x[i], min(max_x[i], xs[i]))
            ys[i] = max(min_y[i], min(max_y[i], ys[i]))

        legalize_layout(xs, ys)
        candidates.append((xs, ys))

    # Add random variations
    for _ in range(3):
        r_xs = [rng.uniform(min_x[i], max_x[i]) for i in range(n)]
        r_ys = [rng.uniform(min_y[i], max_y[i]) for i in range(n)]
        legalize_layout(r_xs, r_ys)
        candidates.append((r_xs, r_ys))

    best_overall_xs = None
    best_overall_ys = None
    best_overall_cost = float('inf')
    best_overall_viols = float('inf')

    # Multi-start Simulated Annealing
    for c_xs, c_ys in candidates:
        cur_xs = list(c_xs)
        cur_ys = list(c_ys)
        cur_cost, cur_viols = compute_cost(cur_xs, cur_ys)

        local_best_xs = list(cur_xs)
        local_best_ys = list(cur_ys)
        local_best_cost = cur_cost
        local_best_viols = cur_viols

        temp = 2.5
        steps = 1800
        cooling = (0.005 / temp) ** (1.0 / steps)

        for step in range(steps):
            idx = rng.randint(0, n - 1)
            orig_x, orig_y = cur_xs[idx], cur_ys[idx]

            move_type = rng.random()
            scale = max(0.04, 2.8 * (1.0 - step / steps))

            if move_type < 0.65 or not adj[idx]:
                new_x = max(min_x[idx], min(max_x[idx], orig_x + rng.gauss(0, scale)))
                new_y = max(min_y[idx], min(max_y[idx], orig_y + rng.gauss(0, scale)))
            else:
                # Directed step towards barycenter of neighbors
                target_x = sum(cur_xs[nb] for nb in adj[idx]) / len(adj[idx])
                target_y = sum(cur_ys[nb] for nb in adj[idx]) / len(adj[idx])
                alpha = rng.uniform(0.1, 0.4)
                new_x = max(min_x[idx], min(max_x[idx], orig_x * (1 - alpha) + target_x * alpha + rng.uniform(-0.1, 0.1)))
                new_y = max(min_y[idx], min(max_y[idx], orig_y * (1 - alpha) + target_y * alpha + rng.uniform(-0.1, 0.1)))

            cur_xs[idx] = new_x
            cur_ys[idx] = new_y
            new_cost, new_viols = compute_cost(cur_xs, cur_ys)

            delta = new_cost - cur_cost
            if delta < 0 or (temp > 1e-4 and rng.random() < math.exp(-delta / temp)):
                cur_cost = new_cost
                cur_viols = new_viols
                if (cur_viols < local_best_viols) or (cur_viols == local_best_viols and cur_cost < local_best_cost):
                    local_best_cost = cur_cost
                    local_best_viols = cur_viols
                    local_best_xs = list(cur_xs)
                    local_best_ys = list(cur_ys)
            else:
                cur_xs[idx] = orig_x
                cur_ys[idx] = orig_y

            temp *= cooling

        if (local_best_viols < best_overall_viols) or (local_best_viols == best_overall_viols and local_best_cost < best_overall_cost):
            best_overall_cost = local_best_cost
            best_overall_viols = local_best_viols
            best_overall_xs = list(local_best_xs)
            best_overall_ys = list(local_best_ys)

    # Fine-tuning via Coordinate Descent
    cur_xs = list(best_overall_xs)
    cur_ys = list(best_overall_ys)
    cur_cost, cur_viols = compute_cost(cur_xs, cur_ys)

    deltas = (0.6, 0.3, 0.15, 0.08, 0.04, 0.02, 0.01)
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1), (0.7, 0.7), (-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7))

    for delta_size in deltas:
        improved = True
        iterations = 0
        while improved and iterations < 12:
            improved = False
            iterations += 1
            for i in range(n):
                for dx_dir, dy_dir in dirs:
                    nx = max(min_x[i], min(max_x[i], cur_xs[i] + dx_dir * delta_size))
                    ny = max(min_y[i], min(max_y[i], cur_ys[i] + dy_dir * delta_size))
                    if nx == cur_xs[i] and ny == cur_ys[i]:
                        continue
                    ox, oy = cur_xs[i], cur_ys[i]
                    cur_xs[i], cur_ys[i] = nx, ny
                    nc, nv = compute_cost(cur_xs, cur_ys)
                    if (nv < cur_viols) or (nv == cur_viols and nc < cur_cost - 1e-5):
                        cur_cost, cur_viols = nc, nv
                        improved = True
                    else:
                        cur_xs[i], cur_ys[i] = ox, oy

    # Strict final clearance and boundary assertion
    legalize_layout(cur_xs, cur_ys, max_iters=50)
    for i in range(n):
        cur_xs[i] = max(ws[i] * 0.5 + 0.01, min(W - ws[i] * 0.5 - 0.01, cur_xs[i]))
        cur_ys[i] = max(hs[i] * 0.5 + 0.01, min(H - hs[i] * 0.5 - 0.01, cur_ys[i]))

    return {comp_names[i]: (cur_xs[i], cur_ys[i]) for i in range(n)}
# EVOLVE-BLOCK-END

