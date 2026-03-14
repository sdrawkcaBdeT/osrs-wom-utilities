import json
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# --- CONFIG ---
REPORT_DIR = "daily_reports"
DATA_FILE = "live_wealth.json"

# Colors
BG_COLOR = "#0A0A0A"
TEXT_MAIN = "#00FF00"
TEXT_WHITE = "#FFFFFF"
TEXT_GOLD = "#FFD700"
TEXT_CYAN = "#00FFFF"
TEXT_RED = "#FF4444"

C_LOGGED = ("#00FF00", "#003300")
C_REM_HRS = ("#FFD700", "#332B00")
C_REM_DAYS = ("#00FFFF", "#003333")
C_GRAVE = ("#111111", "#222222")

if not os.path.exists(REPORT_DIR):
    os.makedirs(REPORT_DIR)

def load_font(size):
    try: return ImageFont.truetype("consola.ttf", size)
    except: return ImageFont.load_default()

def draw_waffle(draw, start_x, start_y, value, title, color_tuple, font_bold, font_main):
    box_size = 12
    gap = 2
    step = box_size + gap
    cols = 30
    rows = 40 
    
    fill_c, out_c = color_tuple
    grave_fill, grave_out = C_GRAVE
    
    full_boxes = int(value)
    half_box = (value % 1) >= 0.5

    draw.text((start_x, start_y), title, fill=TEXT_WHITE, font=font_bold)
    draw.text((start_x, start_y + 40), str(value), fill=fill_c, font=font_main)
    
    grid_y_start = start_y + 90
    
    for i in range(cols * rows):
        r = i // cols
        c = i % cols
        x = start_x + (c * step)
        y = grid_y_start + (r * step)
        
        if i < full_boxes:
            draw.rectangle([x, y, x + box_size, y + box_size], fill=fill_c, outline=out_c)
        elif i == full_boxes and half_box:
            draw.rectangle([x, y, x + (box_size//2), y + box_size], fill=fill_c, outline=out_c)
            draw.rectangle([x + (box_size//2), y, x + box_size, y + box_size], fill=grave_fill, outline=grave_out)
        else:
            draw.rectangle([x, y, x + box_size, y + box_size], fill=grave_fill, outline=grave_out)

def render_report_image(w, filepath, date_str):
    """The core drawing logic, separated so it can be called by live JSON or historical CSVs."""
    img = Image.new('RGB', (2560, 1440), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    font_title = load_font(54)
    font_waffle_main = load_font(32)
    font_waffle_bold = load_font(36)
    font_left = load_font(26)
    font_left_bold = load_font(30)

    def fmt_m(val): return f"{int(val/1000000):,}M"
    def fmt_delta(val): return f"{'+' if val > 0 else ''}{int(val/1000000):,}M"

    x_col1 = 120
    x_col2 = 450
    x_col3 = 650
    line_end = 850
    y = 100

    draw.text((x_col1, y), f"BRUTAL BLACK DRAGON LAB - {date_str}", fill=TEXT_WHITE, font=font_title)
    y += 100

    draw.text((x_col1, y), "FINANCIAL STATEMENT", fill=TEXT_WHITE, font=font_left_bold)
    y += 45; draw.line([(x_col1, y), (line_end, y)], fill="gray", width=3); y += 25
    
    metrics = [
        ("Gear", w['gear'], w['gear_delta']),
        ("Supplies", w['supplies'], w['supplies_delta']),
        ("Drops", w['drops'], w['drops_delta']),
        ("GE / Cash", w['ge'], w['ge_delta'])
    ]
    for label, val, delta in metrics:
        draw.text((x_col1, y), label, fill=TEXT_MAIN, font=font_left)
        draw.text((x_col2, y), fmt_m(val), fill=TEXT_MAIN, font=font_left)
        draw.text((x_col3, y), f"({fmt_delta(delta)})", fill=TEXT_MAIN, font=font_left)
        y += 45
        
    y += 15; draw.line([(x_col1, y), (line_end, y)], fill="#333333", width=3); y += 25
    draw.text((x_col1, y), "Subtotal", fill=TEXT_CYAN, font=font_left_bold)
    draw.text((x_col2, y), fmt_m(w['total']), fill=TEXT_CYAN, font=font_left_bold)
    draw.text((x_col3, y), f"({fmt_delta(w['total_delta'])})", fill=TEXT_CYAN, font=font_left_bold)
    
    y += 60
    draw.text((x_col1, y), "Twisted Bow", fill=TEXT_RED, font=font_left)
    draw.text((x_col2, y), f"({fmt_m(w['tbow_cost'])})", fill=TEXT_RED, font=font_left)
    y += 45; draw.line([(x_col1, y), (line_end, y)], fill="#333333", width=3); y += 25
    draw.text((x_col1, y), "Gap", fill=TEXT_GOLD, font=font_left_bold)
    draw.text((x_col2, y), fmt_m(w['gap']), fill=TEXT_GOLD, font=font_left_bold)
    y += 45
    draw.text((x_col1, y), "Progress", fill=TEXT_MAIN, font=font_left_bold)
    draw.text((x_col2, y), f"{w['progress_pct']:.1f} %", fill=TEXT_MAIN, font=font_left_bold)

    y += 80
    draw.text((x_col1, y), "TIME LOG", fill=TEXT_WHITE, font=font_left_bold)
    y += 45; draw.line([(x_col1, y), (line_end, y)], fill="gray", width=3); y += 25
    draw.text((x_col1, y), "Hours Logged", fill=TEXT_MAIN, font=font_left); draw.text((x_col3, y), f"{w['hours_logged']:.2f}", fill=TEXT_MAIN, font=font_left); y += 45
    draw.text((x_col1, y), "Days Elapsed", fill=TEXT_MAIN, font=font_left); draw.text((x_col3, y), f"{int(w['days_elapsed'])}", fill=TEXT_MAIN, font=font_left); y += 45
    draw.text((x_col1, y), "Hours / Day", fill=TEXT_MAIN, font=font_left); draw.text((x_col3, y), f"{w['hours_per_day']:.2f}", fill=TEXT_MAIN, font=font_left); y += 45

    y += 45
    draw.text((x_col1, y), "PERFORMANCE", fill=TEXT_WHITE, font=font_left_bold)
    y += 45; draw.line([(x_col1, y), (line_end, y)], fill="gray", width=3); y += 25
    draw.text((x_col1, y), "Net GP/hr", fill=TEXT_MAIN, font=font_left); draw.text((x_col3, y), f"{int(w['net_gp_hr']/1000):,} K", fill=TEXT_MAIN, font=font_left); y += 45
    draw.text((x_col1, y), "No-Gear GP/hr", fill=TEXT_MAIN, font=font_left); draw.text((x_col3, y), f"{int(w['no_gear_gp_hr']/1000):,} K", fill=TEXT_MAIN, font=font_left); y += 45

    y += 45
    draw.text((x_col1, y), "PROJECTIONS", fill=TEXT_WHITE, font=font_left_bold)
    y += 45; draw.line([(x_col1, y), (line_end, y)], fill="gray", width=3); y += 25
    draw.text((x_col1, y), "Played Hours Rem", fill=TEXT_MAIN, font=font_left); draw.text((x_col3, y), str(int(w['played_hours_rem'])), fill=TEXT_MAIN, font=font_left); y += 45
    draw.text((x_col1, y), "Real Days Rem", fill=TEXT_MAIN, font=font_left); draw.text((x_col3, y), str(int(w['real_days_rem'])), fill=TEXT_MAIN, font=font_left); y += 45
    draw.text((x_col1, y), "Completion ETA", fill=TEXT_CYAN, font=font_left_bold); draw.text((x_col3, y), str(w['eta_date']), fill=TEXT_CYAN, font=font_left_bold); y += 45

    w_start_y = 200
    draw_waffle(draw, 1000, w_start_y, round(w['hours_logged'],1), "HOURS LOGGED", C_LOGGED, font_waffle_bold, font_waffle_main)
    draw_waffle(draw, 1500, w_start_y, round(w['played_hours_rem'],1), "EST. HOURS REM", C_REM_HRS, font_waffle_bold, font_waffle_main)
    draw_waffle(draw, 2000, w_start_y, round(w['real_days_rem'],1), "REAL DAYS REM", C_REM_DAYS, font_waffle_bold, font_waffle_main)

    img.save(filepath)

def generate_report():
    today_str = datetime.now().strftime('%Y-%m-%d')
    filepath = os.path.join(REPORT_DIR, f"report_{today_str}.png")
    
    if not os.path.exists(DATA_FILE): return

    with open(DATA_FILE, 'r') as f:
        w = json.load(f)

    # Overwrites the file every time the pipeline runs
    render_report_image(w, filepath, today_str)
    print(f"[Daily Report] Updated today's snapshot: {filepath}")

if __name__ == "__main__":
    generate_report()