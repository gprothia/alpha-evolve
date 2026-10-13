"""Render side-by-side PCB placement comparison: initial_program.py vs best_program.py."""
import os
from PIL import Image, ImageDraw, ImageFont

import evaluator
import initial_program
import best_program
from problem import BOARD, COMPONENTS, NETS

COLORS = {
    "MCU": ("#2563eb", "#dbeafe"),   # Blue
    "XTAL": ("#d97706", "#fef3c7"),  # Amber
    "C1": ("#0891b2", "#cffafe"),    # Cyan
    "C2": ("#0891b2", "#cffafe"),    # Cyan
    "LDO": ("#dc2626", "#fee2e2"),   # Red
    "USB": ("#7c3aed", "#ede9fe"),   # Purple
    "HDR": ("#4f46e5", "#e0e7ff"),   # Indigo
    "LED": ("#16a34a", "#dcfce7"),   # Green
}


def get_font(size: int, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def draw_board_panel(draw: ImageDraw.ImageDraw, ox: int, oy: int, scale: float, title: str, subtitle: str, pos: dict, metrics: dict):
    bw = int(BOARD[0] * scale)
    bh = int(BOARD[1] * scale)

    font_title = get_font(24, bold=True)
    font_sub = get_font(16, bold=False)
    font_axis = get_font(13, bold=False)
    font_label = get_font(14, bold=True)
    font_small = get_font(11, bold=False)
    font_metric = get_font(15, bold=False)
    font_metric_b = get_font(16, bold=True)

    # Title & subtitle
    draw.text((ox, oy - 68), title, fill="#0f172a", font=font_title)
    draw.text((ox, oy - 36), subtitle, fill="#475569", font=font_sub)

    # PCB background (dark green solder mask style or clean light engineering grid)
    draw.rectangle([ox, oy, ox + bw, oy + bh], fill="#f8fafc", outline="#1e293b", width=3)

    # Grid lines every 5 mm
    for mm in range(0, 55, 5):
        gx = ox + int(mm * scale)
        gy = oy + bh - int(mm * scale)
        line_color = "#cbd5e1" if mm % 10 == 0 else "#e2e8f0"
        if 0 < mm < 50:
            draw.line([(gx, oy), (gx, oy + bh)], fill=line_color, width=1)
            draw.line([(ox, gy), (ox + bw, gy)], fill=line_color, width=1)
        if mm % 10 == 0:
            draw.text((gx - 8, oy + bh + 6), f"{mm}", fill="#64748b", font=font_axis)
            draw.text((ox - 28, gy - 7), f"{mm}", fill="#64748b", font=font_axis)

    draw.text((ox + bw // 2 - 20, oy + bh + 26), "X (mm)", fill="#475569", font=font_axis)
    draw.text((ox - 38, oy - 20), "Y (mm)", fill="#475569", font=font_axis)

    def to_px(x_mm: float, y_mm: float):
        return (ox + int(x_mm * scale), oy + bh - int(y_mm * scale))

    # Draw NETS (ratlines / wires)
    for net in NETS:
        a, b = net[0], net[1]
        p1 = to_px(*pos[a])
        p2 = to_px(*pos[b])
        draw.line([p1, p2], fill="#94a3b8", width=2)

    # Draw components to exact mm scale
    for name, (w_mm, h_mm) in COMPONENTS.items():
        cx_mm, cy_mm = pos[name]
        x1, y1 = to_px(cx_mm - w_mm / 2, cy_mm + h_mm / 2)
        x2, y2 = to_px(cx_mm + w_mm / 2, cy_mm - h_mm / 2)
        border_col, fill_col = COLORS.get(name, ("#334155", "#e2e8f0"))
        draw.rectangle([x1, y1, x2, y2], fill=fill_col, outline=border_col, width=2)
        cx_px, cy_px = to_px(cx_mm, cy_mm)
        draw.ellipse([cx_px - 2, cy_px - 2, cx_px + 2, cy_px + 2], fill=border_col)

    # Draw labels with smart offsets so small adjacent parts (C1, C2, LED) don't overlap text
    label_offsets = {
        "MCU": (0, -6),
        "XTAL": (20, -6),
        "USB": (0, -6),
        "HDR": (0, -6),
        "LDO": (-32, -26),
        "C1": (-82, -12),
        "C2": (-82, 4),
        "LED": (14, -6),
    }
    for name, (w_mm, h_mm) in COMPONENTS.items():
        cx_mm, cy_mm = pos[name]
        cx_px, cy_px = to_px(cx_mm, cy_mm)
        border_col, _ = COLORS.get(name, ("#334155", "#e2e8f0"))
        dx, dy = label_offsets.get(name, (0, -6))
        if w_mm >= 6 and h_mm >= 3:
            # Draw inside the box
            draw.text((cx_px - 16, cy_px - 12), name, fill=border_col, font=font_label)
            draw.text((cx_px - 24, cy_px + 3), f"({cx_mm:.1f},{cy_mm:.1f})", fill="#334155", font=font_small)
        else:
            tx, ty = cx_px + dx, cy_px + dy
            draw.text((tx, ty), f"{name} ({cx_mm:.1f},{cy_mm:.1f})", fill=border_col, font=font_small)

    # Metrics card below board
    card_y = oy + bh + 52
    draw.rounded_rectangle([ox, card_y, ox + bw, card_y + 115], radius=8, fill="#f1f5f9", outline="#cbd5e1", width=1)
    score_col = "#15803d" if metrics["combined_score"] > 0.2 else "#b45309"
    draw.text((ox + 16, card_y + 12), f"Combined Score: {metrics['combined_score']:.4f}", fill=score_col, font=font_metric_b)
    draw.text((ox + 16, card_y + 40), f"Total Wirelength (HPWL): {metrics['wirelength']:.2f} mm", fill="#1e293b", font=font_metric)
    draw.text((ox + 16, card_y + 64), f"MCU <-> XTAL dist: {metrics['xtal_dist']:.2f} mm   |   MCU <-> Decap (C1,C2) avg: {metrics['decap_dist']:.2f} mm", fill="#1e293b", font=font_metric)
    draw.text((ox + 16, card_y + 88), f"LDO <-> XTAL separation: {metrics['ldo_to_xtal']:.2f} mm (target >= 20 mm)", fill="#1e293b", font=font_metric)


def main():
    scale = 11.0  # 50mm * 11 = 550px per board
    width = 1320
    height = 820
    img = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(img)

    init_pos = initial_program.place()
    init_metrics = evaluator.evaluate("initial_program.py")

    best_pos = best_program.place()
    best_metrics = evaluator.evaluate("best_program.py")

    draw_board_panel(
        draw,
        ox=65,
        oy=95,
        scale=scale,
        title="1. Initial Seed Layout (initial_program.py)",
        subtitle="Random placement — long ratlines & scattered decoupling caps",
        pos=init_pos,
        metrics=init_metrics,
    )

    draw_board_panel(
        draw,
        ox=705,
        oy=95,
        scale=scale,
        title="2. AlphaEvolve Best Layout (best_program.py)",
        subtitle="prog-nickel-puffin — tight MCU cluster + LDO isolated 20.8 mm from XTAL",
        pos=best_pos,
        metrics=best_metrics,
    )

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layout_comparison.png")
    img.save(out_path)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
