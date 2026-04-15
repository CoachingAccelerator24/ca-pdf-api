from flask import Flask, request, jsonify, send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import math
import io
import os

app = Flask(__name__)

W, H = A4

TECH_BLUE    = (51/255,  96/255,  238/255)
PUMPKIN      = (255/255, 129/255, 51/255)
DARK_JET     = (41/255,  41/255,  41/255)
JORDY_BLUE   = (130/255, 175/255, 255/255)
PLATINUM     = (248/255, 248/255, 248/255)
WHITE        = (1, 1, 1)
LIGHT_BLUE_BG= (235/255, 241/255, 255/255)
GREEN        = (39/255,  174/255, 96/255)
RED          = (231/255, 76/255,  60/255)
BLUE_S       = (51/255,  96/255,  238/255)
GREEN_BG     = (230/255, 247/255, 237/255)
RED_BG       = (252/255, 235/255, 235/255)
BLUE_BG      = (235/255, 241/255, 255/255)
ORANGE_BG    = (255/255, 244/255, 235/255)
ORANGE       = (255/255, 129/255, 51/255)

ML = 20*mm
MR = 20*mm
TW = W - ML - MR


def sf(c, rgb): c.setFillColorRGB(*rgb)
def ss(c, rgb): c.setStrokeColorRGB(*rgb)


def rrect(c, x, y, w, h, r, fill=None, stroke=None, lw=0.5):
    if fill: sf(c, fill)
    if stroke: ss(c, stroke); c.setLineWidth(lw)
    c.roundRect(x, y, w, h, r, stroke=1 if stroke else 0, fill=1 if fill else 0)


def draw_logo(c, x, y, size=32, dark=True):
    col = DARK_JET if dark else WHITE
    sf(c, col); ss(c, col)
    cx, cy = x + size*0.28, y + size*0.5
    r = size*0.26
    c.setLineWidth(size*0.11); c.setLineCap(1)
    start_a = math.radians(45); end_a = math.radians(315)
    steps = 30
    pts = [(cx + r*math.cos(start_a + (end_a-start_a)*i/steps),
            cy + r*math.sin(start_a + (end_a-start_a)*i/steps))
           for i in range(steps+1)]
    p = c.beginPath(); p.moveTo(*pts[0])
    for pt in pts[1:]: p.lineTo(*pt)
    ss(c, col); c.drawPath(p, stroke=1, fill=0)
    ax = x + size*0.62; aw = size*0.42; ah = size*0.52; ay_base = y + size*0.24
    lw = size*0.11
    c.setLineWidth(lw); c.setLineCap(1); c.setLineJoin(1)
    p2 = c.beginPath()
    p2.moveTo(ax, ay_base)
    p2.lineTo(ax+aw/2, ay_base+ah)
    p2.lineTo(ax+aw, ay_base)
    ss(c, col); c.drawPath(p2, stroke=1, fill=0)
    bar_y = ay_base + ah*0.38
    c.setLineWidth(lw*0.85)
    c.line(ax+aw*0.18, bar_y, ax+aw*0.82, bar_y)


def wrap_text(c, text, x, y, max_w, font="Helvetica", size=10.5, leading=15.5, color=DARK_JET):
    sf(c, color); c.setFont(font, size)
    paragraphs = text.split("\n\n")
    cur_y = y
    for pi, para in enumerate(paragraphs):
        if pi > 0:
            cur_y -= leading * 0.6
        words = para.replace("\n", " ").split()
        line = ""; lines = []
        for word in words:
            test = (line + " " + word).strip()
            if c.stringWidth(test, font, size) <= max_w:
                line = test
            else:
                lines.append(line); line = word
        if line: lines.append(line)
        for l in lines:
            c.drawString(x, cur_y, l)
            cur_y -= leading
    return cur_y


def topbar(c):
    sf(c, DARK_JET); c.rect(0, H-16*mm, W, 16*mm, fill=1, stroke=0)
    draw_logo(c, ML, H-14*mm, size=22, dark=False)
    sf(c, WHITE); c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W/2, H-7*mm, "COACHING ACCELERATOR")


def sev_badge_color(sev):
    s = sev.lower()
    if s in ["on target","strong","excellent","exceptional"]: return GREEN, GREEN_BG
    if s == "near miss": return BLUE_S, BLUE_BG
    return RED, RED_BG


def trend_arrow(trend):
    return "+" if trend == "improving" else ("-" if trend == "declining" else "=")


def trend_color(trend):
    return GREEN if trend == "improving" else (RED if trend == "declining" else (0.5,0.5,0.5))


def clean_float(val):
    if val is None or val == "": return 0.0
    return float(str(val).replace("%","").replace(",","").strip())

def clean_int(val):
    if val is None or val == "": return 0
    try: return int(float(str(val).replace(",","").strip()))
    except: return 0

def generate_pdf(D):
    D["ar_w1"]       = clean_float(D.get("ar_w1", 0))
    D["pr_w1"]       = clean_float(D.get("pr_w1", 0))
    D["mbr_w1"]      = clean_float(D.get("mbr_w1", 0))
    D["ar_w2"]       = clean_float(D.get("ar_w2", 0))
    D["pr_w2"]       = clean_float(D.get("pr_w2", 0))
    D["mbr_w2"]      = clean_float(D.get("mbr_w2", 0))
    D["ar_pct"]      = clean_int(D.get("ar_pct", 0))
    D["pr_pct"]      = clean_int(D.get("pr_pct", 0))
    D["mbr_pct"]     = clean_int(D.get("mbr_pct", 0))
    D["invited_w1"]  = clean_int(D.get("invited_w1", 0))
    D["messaged_w1"] = clean_int(D.get("messaged_w1", 0))
    D["pr_count_w1"] = clean_int(D.get("pr_count_w1", 0))
    D["mb_count_w1"] = clean_int(D.get("mb_count_w1", 0))
    D["invited_w2"]  = clean_int(D.get("invited_w2", 0))
    D["messaged_w2"] = clean_int(D.get("messaged_w2", 0))
    D["pr_count_w2"] = clean_int(D.get("pr_count_w2", 0))
    D["mb_count_w2"] = clean_int(D.get("mb_count_w2", 0))
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # ═══════════════════════════════════════
    # PAGE 1 — COVER
    # ═══════════════════════════════════════
    sf(c, TECH_BLUE); c.rect(0, 0, W, H, fill=1, stroke=0)
    sf(c, DARK_JET);  c.rect(0, H-18*mm, W, 18*mm, fill=1, stroke=0)

    card_x, card_y = ML, H*0.20
    card_w, card_h = TW, H*0.56
    rrect(c, card_x, card_y, card_w, card_h, 6*mm, fill=WHITE)

    draw_logo(c, card_x+10*mm, card_y+card_h-26*mm, size=36, dark=True)
    sf(c, DARK_JET); c.setFont("Helvetica-Bold", 13)
    c.drawString(card_x+54*mm, card_y+card_h-13*mm, "COACHING ACCELERATOR")

    ss(c, (220/255,220/255,220/255)); c.setLineWidth(0.5)
    c.line(card_x+10*mm, card_y+card_h-32*mm, card_x+card_w-10*mm, card_y+card_h-32*mm)

    sf(c, DARK_JET); c.setFont("Helvetica-Bold", 30)
    c.drawString(card_x+10*mm, card_y+card_h-52*mm, D["client"])

    rrect(c, card_x+10*mm, card_y+card_h-64*mm, 36*mm, 8*mm, 2*mm, fill=LIGHT_BLUE_BG)
    sf(c, TECH_BLUE); c.setFont("Helvetica-Bold", 8)
    c.drawString(card_x+13*mm, card_y+card_h-58.5*mm, D["workflow"].upper())

    ss(c, JORDY_BLUE); c.setLineWidth(2)
    c.line(card_x+10*mm, card_y+card_h-70*mm, card_x+55*mm, card_y+card_h-70*mm)

    chip_y = card_y + card_h - 85*mm
    chip_w = 60*mm
    rrect(c, card_x+10*mm, chip_y, chip_w, 12*mm, 2*mm, fill=LIGHT_BLUE_BG)
    sf(c, (120/255,120/255,120/255)); c.setFont("Helvetica", 7.5)
    c.drawString(card_x+13*mm, chip_y+8.5*mm, "STATS: THIS WEEK")
    sf(c, DARK_JET); c.setFont("Helvetica-Bold", 8.5)
    c.drawString(card_x+13*mm, chip_y+3*mm, D["week2_dates"])

    strip_y = card_y + card_h - 108*mm
    sf(c, PLATINUM); c.rect(card_x, strip_y, card_w, 22*mm, fill=1, stroke=0)
    ss(c, (220/255,220/255,220/255)); c.setLineWidth(0.5)
    c.line(card_x, strip_y+22*mm, card_x+card_w, strip_y+22*mm)
    c.line(card_x, strip_y, card_x+card_w, strip_y)

    kpi_cover = [
        ("Acceptance Rate",       f"{D['ar_w2']}%",  D['ar_pct'],  D['ar_sev'],  D['ar_trend']),
        ("Positive Response Rate", f"{D['pr_w2']}%",  D['pr_pct'],  D['pr_sev'],  D['pr_trend']),
        ("Meeting Booked Rate",   f"{D['mbr_w2']}%", D['mbr_pct'], D['mbr_sev'], D['mbr_trend']),
    ]
    kw = TW / 3
    for i, (label, val, pct, sev, trend) in enumerate(kpi_cover):
        kx = card_x + i*kw
        if i > 0:
            ss(c, (220/255,220/255,220/255)); c.setLineWidth(0.5)
            c.line(kx, strip_y+2*mm, kx, strip_y+20*mm)
        col, bg = sev_badge_color(sev)
        sf(c, (120/255,120/255,120/255)); c.setFont("Helvetica", 7.5)
        c.drawCentredString(kx+kw/2, strip_y+17*mm, label.upper())
        sf(c, col); c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(kx+kw/2, strip_y+10*mm, val)
        sf(c, (150/255,150/255,150/255)); c.setFont("Helvetica", 7.5)
        c.drawCentredString(kx+kw/2, strip_y+4.5*mm, f"{pct}% of target  {trend_arrow(trend)}")

    sf(c, PUMPKIN); c.roundRect(card_x, card_y, card_w, 12*mm, 6*mm, fill=1, stroke=0)
    sf(c, PUMPKIN); c.rect(card_x, card_y+6*mm, card_w, 6*mm, fill=1, stroke=0)
    sf(c, WHITE); c.setFont("Helvetica", 8.5)
    c.drawCentredString(W/2, card_y+4.5*mm, "Confidential — prepared by Coaching Accelerator")

    sf(c, (200/255,210/255,255/255)); c.setFont("Helvetica", 8)
    c.drawCentredString(W/2, 10*mm, "coachingaccelerator.co")

    c.showPage()

    # ═══════════════════════════════════════
    # PAGE 2 — METRICS
    # ═══════════════════════════════════════
    sf(c, PLATINUM); c.rect(0, 0, W, H, fill=1, stroke=0)
    topbar(c)

    sf(c, DARK_JET); c.setFont("Helvetica-Bold", 22)
    c.drawString(ML, H-34*mm, "KPI Performance")
    sf(c, (140/255,140/255,140/255)); c.setFont("Helvetica", 9)
    c.drawString(ML, H-41*mm, "THIS WEEK  .  " + D["week2_dates"].upper())
    ss(c, TECH_BLUE); c.setLineWidth(2)
    c.line(ML, H-44*mm, ML+22*mm, H-44*mm)

    kpis = [
        ("AR",  "Acceptance Rate",        D["ar_w2"],  35, D["ar_pct"],  D["ar_sev"],  D["ar_trend"],  D["ar_w1"]),
        ("PR",  "Positive Response Rate", D["pr_w2"],  5,  D["pr_pct"],  D["pr_sev"],  D["pr_trend"],  D["pr_w1"]),
        ("MBR", "Meeting Booked Rate",    D["mbr_w2"], 60, D["mbr_pct"], D["mbr_sev"], D["mbr_trend"], D["mbr_w1"]),
    ]
    card_top = H - 54*mm
    cw2 = (TW - 8*mm) / 3
    for i, (abbr, label, val, target, pct, sev, trend, prev) in enumerate(kpis):
        cx2 = ML + i*(cw2+4*mm)
        col, bg = sev_badge_color(sev)
        rrect(c, cx2, card_top-38*mm, cw2, 38*mm, 4*mm, fill=WHITE, stroke=(220/255,220/255,220/255))
        sf(c, col); c.roundRect(cx2, card_top-6*mm, cw2, 6*mm, 4*mm, fill=1, stroke=0)
        sf(c, col); c.rect(cx2, card_top-9*mm, cw2, 3*mm, fill=1, stroke=0)
        sf(c, WHITE); c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(cx2+cw2/2, card_top-4*mm, abbr)
        sf(c, DARK_JET); c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(cx2+cw2/2, card_top-20*mm, f"{val}%")
        sf(c, (130/255,130/255,130/255)); c.setFont("Helvetica", 7.5)
        c.drawCentredString(cx2+cw2/2, card_top-25*mm, label)
        ss(c, (220/255,220/255,220/255)); c.setLineWidth(0.5)
        c.line(cx2+4*mm, card_top-28*mm, cx2+cw2-4*mm, card_top-28*mm)
        sf(c, col); c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(cx2+cw2/2, card_top-33*mm, f"{pct}% of target")
        tc = trend_color(trend)
        sf(c, tc); c.setFont("Helvetica", 8)
        delta = round(float(val) - float(prev), 2)
        sign = "+" if delta >= 0 else ""
        c.drawCentredString(cx2+cw2/2, card_top-37.5*mm, f"{trend_arrow(trend)} {sign}{delta}% vs last week")

    badge_y = card_top - 48*mm
    sf(c, DARK_JET); c.setFont("Helvetica-Bold", 9)
    c.drawString(ML, badge_y+4*mm, "Severity")
    ss(c, (220/255,220/255,220/255)); c.setLineWidth(0.5)
    c.line(ML, badge_y+1*mm, W-MR, badge_y+1*mm)
    badge_y -= 8*mm
    for i, (abbr, label, val, target, pct, sev, trend, prev) in enumerate(kpis):
        col, bg = sev_badge_color(sev)
        bx = ML + i*(TW/3)
        rrect(c, bx, badge_y, TW/3-4*mm, 9*mm, 2*mm, fill=bg)
        sf(c, col); c.setFont("Helvetica-Bold", 9)
        c.drawString(bx+3*mm, badge_y+3*mm, f"{abbr}  -  {sev}")

    table_y = badge_y - 16*mm
    sf(c, DARK_JET); c.setFont("Helvetica-Bold", 9)
    c.drawString(ML, table_y+4*mm, "Week-on-week comparison")
    ss(c, (220/255,220/255,220/255)); c.setLineWidth(0.5)
    c.line(ML, table_y+1*mm, W-MR, table_y+1*mm)

    headers  = ["", "Invited", "Messaged", "Pos. Responses", "MB (count)", "AR %", "PR %", "MBR %"]
    col_w    = [52*mm, 16*mm, 18*mm, 18*mm, 16*mm, 14*mm, 14*mm, 16*mm]
    row_h    = 9*mm

    def table_row(y, row_data, is_header=False, bg=None):
        if bg:
            sf(c, bg); c.rect(ML, y, TW, row_h, fill=1, stroke=0)
        x = ML
        for j, (cell, cw3) in enumerate(zip(row_data, col_w)):
            if is_header:
                sf(c, (140/255,140/255,140/255)); c.setFont("Helvetica-Bold", 7.5)
            else:
                sf(c, DARK_JET); c.setFont("Helvetica", 8.5)
            if j == 0:
                c.drawString(x+2*mm, y+3*mm, str(cell))
            else:
                c.drawCentredString(x+cw3/2, y+3*mm, str(cell))
            x += cw3
        ss(c, (230/255,230/255,230/255)); c.setLineWidth(0.3)
        c.line(ML, y, W-MR, y)

    ty = table_y - 4*mm
    table_row(ty, headers, is_header=True)
    ty -= row_h
    table_row(ty, [
        "Last Week  " + D["week1_dates"],
        D["invited_w1"], D["messaged_w1"],
        D["pr_count_w1"], D["mb_count_w1"],
        f"{D['ar_w1']}%", f"{D['pr_w1']}%", f"{D['mbr_w1']}%"
    ], bg=(248/255,248/255,248/255))
    ty -= row_h
    table_row(ty, [
        "This Week  " + D["week2_dates"],
        D["invited_w2"], D["messaged_w2"],
        D["pr_count_w2"], D["mb_count_w2"],
        f"{D['ar_w2']}%", f"{D['pr_w2']}%", f"{D['mbr_w2']}%"
    ], bg=LIGHT_BLUE_BG)

    leg_y = ty - 15*mm
    items = [(GREEN, "On / above target"), (BLUE_S, "76-99% of target"), (RED, "Below 76% of target")]
    lx = ML
    for col, lbl in items:
        rrect(c, lx, leg_y, 3*mm, 3*mm, 0.5*mm, fill=col)
        sf(c, (120/255,120/255,120/255)); c.setFont("Helvetica", 7.5)
        c.drawString(lx+4.5*mm, leg_y+0.5*mm, lbl)
        lx += c.stringWidth(lbl, "Helvetica", 7.5) + 14*mm

    c.showPage()

    # ═══════════════════════════════════════
    # PAGE 3 — ANALYSIS
    # ═══════════════════════════════════════
    sf(c, PLATINUM); c.rect(0, 0, W, H, fill=1, stroke=0)
    topbar(c)

    sf(c, DARK_JET); c.setFont("Helvetica-Bold", 22)
    c.drawString(ML, H-34*mm, "Analysis")
    sf(c, (140/255,140/255,140/255)); c.setFont("Helvetica", 9)
    c.drawString(ML, H-41*mm, "FINDINGS THIS WEEK")
    ss(c, PUMPKIN); c.setLineWidth(2)
    c.line(ML, H-44*mm, ML+22*mm, H-44*mm)

    card_y2 = H*0.18
    card_h2 = H*0.60
    rrect(c, ML, card_y2, TW, card_h2, 5*mm, fill=WHITE, stroke=(220/255,220/255,220/255))

    all_hit = all(p >= 100 for p in [D["ar_pct"], D["pr_pct"], D["mbr_pct"]])
    banner_col = GREEN if all_hit else RED
    banner_bg  = GREEN_BG if all_hit else RED_BG
    banner_text = "All KPIs on target this week" if all_hit else "KPIs require attention this week"
    rrect(c, ML+8*mm, card_y2+card_h2-14*mm, TW-16*mm, 10*mm, 2*mm, fill=banner_bg)
    sf(c, banner_col); c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W/2, card_y2+card_h2-8*mm, banner_text)

    chips_y = card_y2 + card_h2 - 26*mm
    chip_data = [
        (f"AR - {D['ar_sev']}  {D['ar_pct']}%",  D['ar_sev']),
        (f"PR - {D['pr_sev']}  {D['pr_pct']}%",  D['pr_sev']),
        (f"MBR - {D['mbr_sev']}  {D['mbr_pct']}%", D['mbr_sev']),
    ]
    chip_w3 = (TW - 20*mm) / 3
    for i, (text, sev) in enumerate(chip_data):
        col, bg = sev_badge_color(sev)
        cx3 = ML + 8*mm + i*(chip_w3+2*mm)
        rrect(c, cx3, chips_y, chip_w3, 8*mm, 2*mm, fill=bg)
        sf(c, col); c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(cx3+chip_w3/2, chips_y+3*mm, text)

    ss(c, (220/255,220/255,220/255)); c.setLineWidth(0.5)
    c.line(ML+8*mm, chips_y-4*mm, ML+TW-8*mm, chips_y-4*mm)

    wrap_text(c, D["analysis"], ML+8*mm, chips_y-12*mm, TW-16*mm, size=10.5, leading=16)

    c.showPage()

    # ═══════════════════════════════════════
    # PAGE 4 — PLANS AHEAD
    # ═══════════════════════════════════════
    sf(c, PLATINUM); c.rect(0, 0, W, H, fill=1, stroke=0)
    topbar(c)

    sf(c, DARK_JET); c.setFont("Helvetica-Bold", 22)
    c.drawString(ML, H-34*mm, "Plans ahead")
    sf(c, (140/255,140/255,140/255)); c.setFont("Helvetica", 9)
    c.drawString(ML, H-41*mm, "WHAT WE'RE DOING NEXT")
    ss(c, TECH_BLUE); c.setLineWidth(2)
    c.line(ML, H-44*mm, ML+22*mm, H-44*mm)

    card_y3 = H*0.18
    card_h3 = H*0.60
    rrect(c, ML, card_y3, TW, card_h3, 5*mm, fill=WHITE, stroke=(220/255,220/255,220/255))

    rrect(c, ML+8*mm, card_y3+card_h3-14*mm, 50*mm, 9*mm, 2*mm, fill=ORANGE_BG)
    sf(c, ORANGE); c.setFont("Helvetica-Bold", 8)
    c.drawString(ML+11*mm, card_y3+card_h3-8.5*mm, "WHAT WE'RE DOING NEXT")

    ss(c, (220/255,220/255,220/255)); c.setLineWidth(0.5)
    c.line(ML+8*mm, card_y3+card_h3-18*mm, ML+TW-8*mm, card_y3+card_h3-18*mm)

    wrap_text(c, D["plans"], ML+8*mm, card_y3+card_h3-26*mm, TW-16*mm, size=10.5, leading=16)

    sf(c, PUMPKIN); c.roundRect(ML, card_y3, TW, 12*mm, 5*mm, fill=1, stroke=0)
    sf(c, PUMPKIN); c.rect(ML, card_y3+6*mm, TW, 6*mm, fill=1, stroke=0)
    sf(c, WHITE); c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(W/2, card_y3+4.5*mm, "Questions? Reach out to your campaign manager anytime.")

    c.save()
    buffer.seek(0)
    return buffer


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/generate-pdf", methods=["POST"])
def generate_pdf_endpoint():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON body received"}), 400

        required = [
            "client", "workflow",
            "week1_dates", "week2_dates",
            "invited_w1", "messaged_w1", "pr_count_w1", "mb_count_w1",
            "ar_w1", "pr_w1", "mbr_w1",
            "invited_w2", "messaged_w2", "pr_count_w2", "mb_count_w2",
            "ar_w2", "pr_w2", "mbr_w2",
            "ar_pct", "pr_pct", "mbr_pct",
            "ar_sev", "pr_sev", "mbr_sev",
            "ar_trend", "pr_trend", "mbr_trend",
            "analysis", "plans"
        ]
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"error": f"Missing fields: {missing}"}), 400

        pdf_buffer = generate_pdf(data)
        client_safe = data["client"].replace(" ", "_")
        filename = f"CA_{client_safe}_Report.pdf"

        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
