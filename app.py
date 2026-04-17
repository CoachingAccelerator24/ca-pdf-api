from flask import Flask, request, jsonify, send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image
import numpy as np
import io, os

app = Flask(__name__)
W, H = A4
ML = 20*mm; MR = 20*mm; TW = W - ML - MR

TECH_BLUE  = (51/255, 96/255, 238/255)
PUMPKIN    = (255/255, 129/255, 51/255)
DARK_JET   = (41/255, 41/255, 41/255)
PLATINUM   = (248/255, 248/255, 248/255)
WHITE      = (1, 1, 1)
GREEN      = (39/255, 174/255, 96/255)
RED        = (231/255, 76/255, 60/255)
BLUE_ST    = (51/255, 96/255, 238/255)
GREEN_BG   = (230/255, 247/255, 237/255)
RED_BG     = (252/255, 235/255, 235/255)
BLUE_BG    = (235/255, 241/255, 255/255)
GRAY       = (150/255, 150/255, 150/255)
LGRAY      = (220/255, 220/255, 220/255)

BASE = os.path.dirname(os.path.abspath(__file__))

# ── Font registration ─────────────────────────────────────────────────────────
def reg_fonts():
    for n, f in [('P', 'Poppins-Regular'), ('PB', 'Poppins-Bold'), ('PM', 'Poppins-Medium')]:
        path = os.path.join(BASE, f + '.ttf')
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(n, path))
            except Exception:
                pass

# ── Logo with transparency fix ────────────────────────────────────────────────
def get_logo_path(white=True):
    """
    Returns a path to a transparency-fixed version of the logo.
    The source PNGs are RGB with black backgrounds. This converts
    black pixels to transparent and caches the result.
    """
    src_name = 'logo_white_transparent.png' if white else 'logo_dark_transparent.png'
    out_name = src_name.replace('.png', '_rgba.png')
    src_path = os.path.join(BASE, src_name)
    out_path = os.path.join(BASE, out_name)

    if not os.path.exists(src_path):
        return None

    if not os.path.exists(out_path):
        img = Image.open(src_path).convert('RGBA')
        data = np.array(img)

        if white:
            # White logo on black bg — make black pixels transparent
            mask = (data[:, :, 0] < 30) & (data[:, :, 1] < 30) & (data[:, :, 2] < 30)
        else:
            # Dark logo — source file is fully black (corrupted).
            # Derive from white logo by inverting colours.
            white_path = os.path.join(BASE, 'logo_white_transparent_rgba.png')
            if not os.path.exists(white_path):
                get_logo_path(white=True)  # ensure white version is built first
            w_img = Image.open(white_path).convert('RGBA')
            w_data = np.array(w_img)
            inv_rgb = 255 - w_data[:, :, :3]
            result = np.concatenate([inv_rgb, w_data[:, :, 3:4]], axis=2)
            Image.fromarray(result.astype(np.uint8)).save(out_path)
            return out_path

        data[:, :, 3] = np.where(mask, 0, 255)
        Image.fromarray(data).save(out_path)

    return out_path

# ── Drawing helpers ───────────────────────────────────────────────────────────
def sf(c, rgb): c.setFillColorRGB(*rgb)
def ss(c, rgb): c.setStrokeColorRGB(*rgb)

def rr(c, x, y, w, h, r, fill=None, stroke=None, lw=0.5):
    if fill:
        sf(c, fill)
    if stroke:
        ss(c, stroke)
        c.setLineWidth(lw)
    c.roundRect(x, y, w, h, r, stroke=1 if stroke else 0, fill=1 if fill else 0)

def cf(val):
    if not val and val != 0:
        return 0.0
    return float(str(val).replace('%', '').replace(',', '').strip() or 0)

def ci(val):
    if not val and val != 0:
        return 0
    try:
        return int(float(str(val).replace(',', '').strip() or 0))
    except Exception:
        return 0

def sev_lbl(s):
    m = {
        'critical': 'Critical', 'severe': 'Severe', 'poor': 'Poor',
        'below target': 'Below Target', 'near miss': 'Near Miss',
        'on target': 'On Target', 'strong': 'Above Target',
        'excellent': 'Excellent', 'exceptional': 'Exceptional'
    }
    return m.get(str(s).lower(), s)

def sev_col(s):
    v = str(s).lower()
    if v in ['on target', 'strong', 'excellent', 'exceptional']:
        return GREEN, GREEN_BG
    if v == 'near miss':
        return BLUE_ST, BLUE_BG
    return RED, RED_BG

def wrap(c, text, x, y, mw, font='P', sz=10.5, lead=16, col=None):
    sf(c, col if col else DARK_JET)
    c.setFont(font, sz)
    for pi, para in enumerate(text.split('\n\n')):
        if pi > 0:
            y -= lead * 0.7
        words = para.replace('\n', ' ').split()
        line = ''
        lines = []
        for w2 in words:
            t2 = (line + ' ' + w2).strip()
            if c.stringWidth(t2, font, sz) <= mw:
                line = t2
            else:
                lines.append(line)
                line = w2
        if line:
            lines.append(line)
        for l in lines:
            c.drawString(x, y, l)
            y -= lead
    return y

def draw_logo(c, x, y, w, h, white=True):
    path = get_logo_path(white=white)
    if path and os.path.exists(path):
        c.drawImage(path, x, y, width=w, height=h, preserveAspectRatio=True, mask='auto')

def topbar(c):
    sf(c, DARK_JET)
    c.rect(0, H - 22*mm, W, 22*mm, fill=1, stroke=0)
    draw_logo(c, W/2 - 22*mm, H - 22*mm + 2.5*mm, 44*mm, 17*mm, white=True)

# ── PDF generator ─────────────────────────────────────────────────────────────
def generate_pdf(D):
    reg_fonts()

    for k in ['ar_w2', 'pr_w2', 'mbr_w2']:
        D[k] = cf(D.get(k, 0))
    for k in ['ar_pct', 'pr_pct', 'mbr_pct',
              'invited_w2', 'messaged_w2', 'pr_count_w2', 'mb_count_w2']:
        D[k] = ci(D.get(k, 0))

    w2 = D.get('week2_dates', '')
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # ── PAGE 1: COVER ────────────────────────────────────────────────────────
    sf(c, TECH_BLUE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    draw_logo(c, W/2 - 40*mm, H*0.62, 80*mm, 80*mm, white=True)
    ss(c, (200/255, 215/255, 255/255))
    c.setLineWidth(1)
    c.line(W/2 - 35*mm, H*0.595, W/2 + 35*mm, H*0.595)
    sf(c, WHITE)
    c.setFont('PB', 40)
    c.drawCentredString(W/2, H*0.46, 'Weekly Report')
    sf(c, (200/255, 215/255, 255/255))
    c.setFont('P', 14)
    c.drawCentredString(W/2, H*0.415, w2)
    c.setFont('P', 7)
    c.drawString(ML, 4*mm, 'coachingaccelerator.co')
    c.drawRightString(W - MR, 4*mm, 'Confidential')
    c.showPage()

    # ── PAGE 2: KPI METRICS ──────────────────────────────────────────────────
    sf(c, PLATINUM)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    topbar(c)
    sf(c, DARK_JET)
    c.setFont('PB', 22)
    c.drawCentredString(W/2, H - 38*mm, 'Metrics')
    sf(c, GRAY)
    c.setFont('P', 9)
    c.drawCentredString(W/2, H - 45*mm, w2)
    ss(c, TECH_BLUE)
    c.setLineWidth(2)
    c.line(W/2 - 11*mm, H - 48*mm, W/2 + 11*mm, H - 48*mm)

    ct = H - 58*mm
    # FIX: (TW-10mm)/3 ensures all 3 cards fit within margins so
    # drawCentredString centres correctly in every card
    cw2 = (TW - 10*mm) / 3

    kpis = [
        ('Acceptance Rate',      'ar_w2',  'ar_pct',  'ar_sev',  'ar_trend'),
        ('Positive Response Rate','pr_w2',  'pr_pct',  'pr_sev',  'pr_trend'),
        ('Meeting Booked Rate',  'mbr_w2', 'mbr_pct', 'mbr_sev', 'mbr_trend'),
    ]

    for i, (abbr, vk, pk, sk, tk) in enumerate(kpis):
        cx = ML + i * (cw2 + 5*mm)
        val = D[vk]
        pct = D[pk]
        col, bg = sev_col(D[sk])
        ch = 36*mm

        rr(c, cx, ct - ch, cw2, ch, 4*mm, fill=WHITE, stroke=LGRAY, lw=0.5)
        sf(c, col)
        c.roundRect(cx, ct - 5*mm, cw2, 5*mm, 4*mm, fill=1, stroke=0)
        c.rect(cx, ct - 7.5*mm, cw2, 3*mm, fill=1, stroke=0)
        sf(c, WHITE)
        c.setFont('PB', 8)
        c.drawCentredString(cx + cw2/2, ct - 3.5*mm, abbr)
        sf(c, DARK_JET)
        c.setFont('PB', 22)
        c.drawCentredString(cx + cw2/2, ct - 16*mm, f'{val}%')
        ss(c, LGRAY)
        c.setLineWidth(0.5)
        c.line(cx + 4*mm, ct - 20*mm, cx + cw2 - 4*mm, ct - 20*mm)
        sf(c, col)
        c.setFont('PB', 9)
        c.drawCentredString(cx + cw2/2, ct - 25*mm, f'{pct}% of target')

    # Target Score row
    sy = ct - 52*mm
    sf(c, DARK_JET)
    c.setFont('PB', 9)
    c.drawString(ML, sy + 4*mm, 'Target Score')
    ss(c, LGRAY)
    c.setLineWidth(0.5)
    c.line(ML, sy + 1*mm, W - MR, sy + 1*mm)
    sy -= 8*mm

    score_labels = [
        ('ar_sev',  'Acceptance Rate'),
        ('pr_sev',  'Positive Response Rate'),
        ('mbr_sev', 'Meeting Booked Rate'),
    ]
    for i, (sk, full) in enumerate(score_labels):
        col, bg = sev_col(D[sk])
        bw = TW/3 - 2*mm
        bx = ML + i * (TW/3)
        rr(c, bx, sy, bw, 9*mm, 2*mm, fill=bg)
        sf(c, col)
        c.setFont('PB', 8)
        c.drawCentredString(bx + bw/2, sy + 3*mm, f'{full}  -  {sev_lbl(D[sk])}')

    # Legend
    ly = sy - 14*mm
    lx = ML
    for col_l, lbl2 in [
        (GREEN,   'On / above target'),
        (BLUE_ST, 'Between 76-99% of target'),
        (RED,     'Below 76% of target'),
    ]:
        rr(c, lx, ly, 3*mm, 3*mm, 0.5*mm, fill=col_l)
        sf(c, GRAY)
        c.setFont('P', 7.5)
        c.drawString(lx + 4.5*mm, ly + 0.5*mm, lbl2)
        lx += c.stringWidth(lbl2, 'P', 7.5) + 14*mm

    c.showPage()

    # ── PAGE 3: ANALYSIS ─────────────────────────────────────────────────────
    sf(c, PLATINUM)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    topbar(c)
    sf(c, DARK_JET)
    c.setFont('PB', 22)
    c.drawCentredString(W/2, H - 38*mm, 'Analysis')
    sf(c, GRAY)
    c.setFont('P', 9)
    c.drawCentredString(W/2, H - 45*mm, 'FINDINGS THIS WEEK')
    ss(c, PUMPKIN)
    c.setLineWidth(2)
    c.line(W/2 - 11*mm, H - 48*mm, W/2 + 11*mm, H - 48*mm)

    cy2 = H*0.10
    ch2 = H*0.63
    rr(c, ML, cy2, TW, ch2, 5*mm, fill=WHITE, stroke=LGRAY, lw=0.5)

    all_hit = all(p >= 100 for p in [D['ar_pct'], D['pr_pct'], D['mbr_pct']])
    bc = GREEN if all_hit else RED
    bb = GREEN_BG if all_hit else RED_BG
    bt = 'All KPIs on target this week' if all_hit else 'KPIs require attention this week'
    rr(c, ML + 8*mm, cy2 + ch2 - 14*mm, TW - 16*mm, 10*mm, 2*mm, fill=bb)
    sf(c, bc)
    c.setFont('PB', 9)
    c.drawCentredString(W/2, cy2 + ch2 - 8*mm, bt)

    cpy = cy2 + ch2 - 26*mm
    cpw = (TW - 20*mm) / 3
    chips = [
        (f"AR  -  {sev_lbl(D['ar_sev'])}  {D['ar_pct']}%",  'ar_sev'),
        (f"PR  -  {sev_lbl(D['pr_sev'])}  {D['pr_pct']}%",  'pr_sev'),
        (f"MBR  -  {sev_lbl(D['mbr_sev'])}  {D['mbr_pct']}%", 'mbr_sev'),
    ]
    for i, (txt, sk) in enumerate(chips):
        col, bg = sev_col(D[sk])
        cx3 = ML + 8*mm + i * (cpw + 2*mm)
        rr(c, cx3, cpy, cpw, 8*mm, 2*mm, fill=bg)
        sf(c, col)
        c.setFont('PB', 8)
        c.drawCentredString(cx3 + cpw/2, cpy + 3*mm, txt)

    ss(c, LGRAY)
    c.setLineWidth(0.5)
    c.line(ML + 8*mm, cpy - 4*mm, ML + TW - 8*mm, cpy - 4*mm)
    wrap(c, D.get('analysis', ''), ML + 10*mm, cpy - 14*mm, TW - 20*mm, sz=10.5, lead=16)
    c.showPage()

    # ── PAGE 4: PLANS AHEAD ──────────────────────────────────────────────────
    sf(c, PLATINUM)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    topbar(c)
    sf(c, DARK_JET)
    c.setFont('PB', 22)
    c.drawCentredString(W/2, H - 38*mm, 'Plans Ahead')
    sf(c, GRAY)
    c.setFont('P', 9)
    c.drawCentredString(W/2, H - 45*mm, "WHAT WE'RE DOING NEXT")
    ss(c, TECH_BLUE)
    c.setLineWidth(2)
    c.line(W/2 - 11*mm, H - 48*mm, W/2 + 11*mm, H - 48*mm)

    cy3 = H*0.10
    ch3 = H*0.63
    rr(c, ML, cy3, TW, ch3, 5*mm, fill=WHITE, stroke=LGRAY, lw=0.5)
    sf(c, DARK_JET)
    c.setFont('PB', 9)
    c.drawCentredString(W/2, cy3 + ch3 - 10*mm, "WHAT WE'RE DOING NEXT")
    ss(c, LGRAY)
    c.setLineWidth(0.5)
    c.line(ML + 8*mm, cy3 + ch3 - 14*mm, ML + TW - 8*mm, cy3 + ch3 - 14*mm)
    wrap(c, D.get('plans', ''), ML + 10*mm, cy3 + ch3 - 26*mm, TW - 20*mm, sz=10.5, lead=16)
    draw_logo(c, W/2 - 18*mm, cy3 + 3*mm, 36*mm, 14*mm, white=False)

    c.save()
    buf.seek(0)
    return buf


# ── Flask routes ──────────────────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/generate-pdf', methods=['POST'])
def gen():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON'}), 400

        required = [
            'client', 'workflow', 'week2_dates',
            'invited_w2', 'messaged_w2', 'pr_count_w2', 'mb_count_w2',
            'ar_w2', 'pr_w2', 'mbr_w2',
            'ar_pct', 'pr_pct', 'mbr_pct',
            'ar_sev', 'pr_sev', 'mbr_sev',
            'ar_trend', 'pr_trend', 'mbr_trend',
            'analysis', 'plans',
        ]
        miss = [f for f in required if f not in data]
        if miss:
            return jsonify({'error': f'Missing fields: {miss}'}), 400

        buf = generate_pdf(data)
        fn = f"CA_{data['client'].replace(' ', '_')}_Report.pdf"
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=fn)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
