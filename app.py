from flask import Flask, request, jsonify, send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io, os

app = Flask(__name__)
W, H = A4
ML = 20*mm; MR = 20*mm; TW = W - ML - MR

TECH_BLUE  = (51/255, 96/255, 238/255)
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

def reg_fonts():
    for n, f in [('P','Poppins-Regular'),('PB','Poppins-Bold'),('PM','Poppins-Medium')]:
        path = os.path.join(BASE, f+'.ttf')
        if os.path.exists(path):
            try: pdfmetrics.registerFont(TTFont(n, path))
            except: pass

def sf(c, rgb): c.setFillColorRGB(*rgb)
def ss(c, rgb): c.setStrokeColorRGB(*rgb)

def rr(c, x, y, w, h, r, fill=None, stroke=None, lw=0.5):
    if fill: sf(c, fill)
    if stroke: ss(c, stroke); c.setLineWidth(lw)
    c.roundRect(x, y, w, h, r, stroke=1 if stroke else 0, fill=1 if fill else 0)

def cf(val):
    if not val and val != 0: return 0.0
    return float(str(val).replace('%','').replace(',','').strip() or 0)

def ci(val):
    if not val and val != 0: return 0
    try: return int(float(str(val).replace(',','').strip() or 0))
    except: return 0

def sev_lbl(s):
    m = {'critical':'Critical','severe':'Severe','poor':'Poor','below target':'Below Target',
         'near miss':'Near Miss','on target':'On Target','strong':'Above Target',
         'excellent':'Excellent','exceptional':'Exceptional'}
    return m.get(str(s).lower(), s)

def sev_col(s):
    v = str(s).lower()
    if v in ['on target','strong','excellent','exceptional']: return GREEN, GREEN_BG
    if v == 'near miss': return BLUE_ST, BLUE_BG
    return RED, RED_BG

def wrap_height(c, text, mw, font='P', sz=10, lead=15):
    total_lines = 0
    for pi, para in enumerate(text.split('\n\n')):
        if pi > 0: total_lines += 0.7
        words = para.replace('\n',' ').split()
        line = ''; lines = []
        for w2 in words:
            t2 = (line+' '+w2).strip()
            if c.stringWidth(t2, font, sz) <= mw: line = t2
            else: lines.append(line); line = w2
        if line: lines.append(line)
        total_lines += len(lines)
    return total_lines * lead

def wrap(c, text, x, y, mw, font='P', sz=10, lead=15, col=None):
    sf(c, col if col else DARK_JET)
    c.setFont(font, sz)
    for pi, para in enumerate(text.split('\n\n')):
        if pi > 0: y -= lead * 0.7
        words = para.replace('\n',' ').split()
        line = ''; lines = []
        for w2 in words:
            t2 = (line+' '+w2).strip()
            if c.stringWidth(t2, font, sz) <= mw: line = t2
            else: lines.append(line); line = w2
        if line: lines.append(line)
        for l in lines: c.drawString(x, y, l); y -= lead
    return y

def draw_logo(c, x, y, w, h, white=True):
    f = os.path.join(BASE, 'logo_white_transparent.png' if white else 'logo_dark_transparent.png')
    if os.path.exists(f):
        c.drawImage(f, x, y, width=w, height=h, preserveAspectRatio=True, mask='auto')

def topbar(c):
    sf(c, DARK_JET); c.rect(0, H-22*mm, W, 22*mm, fill=1, stroke=0)
    draw_logo(c, W/2-22*mm, H-22*mm+2.5*mm, 44*mm, 17*mm, white=True)

def generate_pdf(D):
    reg_fonts()
    for k in ['ar_w2','pr_w2','mbr_w2']: D[k] = cf(D.get(k,0))
    for k in ['ar_pct','pr_pct','mbr_pct','invited_w2','messaged_w2','pr_count_w2','mb_count_w2']:
        D[k] = ci(D.get(k,0))

    w2    = D.get('week2_dates','')
    cname = D.get('client_name','')

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # ── PAGE 1: COVER ────────────────────────────────────────────
    sf(c, TECH_BLUE); c.rect(0,0,W,H,fill=1,stroke=0)
    draw_logo(c, W/2-40*mm, H*0.62, 80*mm, 80*mm, white=True)
    ss(c,(200/255,215/255,255/255)); c.setLineWidth(1)
    c.line(W/2-35*mm, H*0.595, W/2+35*mm, H*0.595)
    sf(c,WHITE); c.setFont('PB',40)
    c.drawCentredString(W/2, H*0.46, 'Weekly Report')
    sf(c,(200/255,215/255,255/255)); c.setFont('P',14)
    c.drawCentredString(W/2, H*0.415, w2)

    # Client name below date
    if cname:
        c.setLineWidth(0.5)
        c.line(W/2-20*mm, H*0.385, W/2+20*mm, H*0.385)
        c.setFont('PM', 11)
        c.drawCentredString(W/2, H*0.365, cname)

    sf(c,(200/255,215/255,255/255)); c.setFont('P',7)
    c.drawString(ML, 4*mm, 'coachingaccelerator.co')
    c.drawRightString(W-MR, 4*mm, 'Confidential')
    c.showPage()

    # ── PAGE 2: COMBINED ─────────────────────────────────────────
    sf(c, PLATINUM); c.rect(0,0,W,H,fill=1,stroke=0); topbar(c)

    # Dynamic padding
    analysis_text_h = wrap_height(c, D.get('analysis',''), TW) / mm
    plans_text_h    = wrap_height(c, D.get('plans',''),    TW) / mm
    fixed_h = 22 + 13 + 36 + 8 + 13 + 11 + 14 + 22 + 14
    text_h  = analysis_text_h + plans_text_h
    slack   = (297 - 8) - fixed_h - text_h
    pad     = max(slack / 7, 2)

    cy = H - 22*mm - pad*mm

    # ── Metrics header ────────────────────────────────────────────
    sf(c,DARK_JET); c.setFont('PB',16); c.drawCentredString(W/2, cy, 'Metrics')
    cy -= 7*mm
    sf(c,GRAY); c.setFont('P',8); c.drawCentredString(W/2, cy, w2)
    cy -= pad*mm + 2*mm

    # ── KPI Cards ────────────────────────────────────────────────
    cw2 = (TW-10*mm)/3; ch = 37*mm; ct = cy

    kpi_targets = [
        ('Acceptance Rate',       'ar_w2','ar_pct','ar_sev',  'Target: 35%'),
        ('Positive Response Rate','pr_w2','pr_pct','pr_sev',  'Target: 5%'),
        ('Meeting Booked Rate',   'mbr_w2','mbr_pct','mbr_sev','Target: 60%'),
    ]

    for i, (abbr, vk, pk, sk, tgt_lbl) in enumerate(kpi_targets):
        cx = ML+i*(cw2+5*mm); val=D[vk]; pct=D[pk]; col,bg=sev_col(D[sk])
        rr(c,cx,ct-ch,cw2,ch,3*mm,fill=WHITE,stroke=LGRAY,lw=0.5)
        # Header bar
        sf(c,col)
        c.roundRect(cx,ct-8*mm,cw2,8*mm,3*mm,fill=1,stroke=0)
        c.rect(cx,ct-9.5*mm,cw2,2*mm,fill=1,stroke=0)
        # Metric name
        sf(c,WHITE); c.setFont('PB',7)
        c.drawCentredString(cx+cw2/2, ct-4*mm, abbr)
        # Severity label
        c.setFont('P',6.5)
        c.drawCentredString(cx+cw2/2, ct-7.2*mm, sev_lbl(D[sk]))
        # Big number
        sf(c,DARK_JET); c.setFont('PB',19)
        c.drawCentredString(cx+cw2/2, ct-18*mm, f'{val}%')
        # Divider
        ss(c,LGRAY); c.setLineWidth(0.5)
        c.line(cx+3*mm, ct-21.5*mm, cx+cw2-3*mm, ct-21.5*mm)
        # % of target
        sf(c,col); c.setFont('PB',8.5)
        c.drawCentredString(cx+cw2/2, ct-25.5*mm, f'{pct}% of target')
        # Second divider
        ss(c,LGRAY); c.setLineWidth(0.3)
        c.line(cx+3*mm, ct-28.5*mm, cx+cw2-3*mm, ct-28.5*mm)
        # Target label
        sf(c,GRAY); c.setFont('P',7)
        c.drawCentredString(cx+cw2/2, ct-32.5*mm, tgt_lbl)

    cy = ct - ch - pad*mm

    # ── Legend ───────────────────────────────────────────────────
    lx = ML
    for col_l, lbl2 in [(GREEN,'On / Above Target'),(BLUE_ST,'Between 76-99% Of Target'),(RED,'Below 76% Of Target')]:
        rr(c,lx,cy,2.5*mm,2.5*mm,0.5*mm,fill=col_l)
        sf(c,GRAY); c.setFont('P',7)
        c.drawString(lx+3.5*mm, cy+0.3*mm, lbl2)
        lx += c.stringWidth(lbl2,'P',7)+12*mm
    cy -= pad*mm + 4*mm

    # ── Divider ──────────────────────────────────────────────────
    ss(c,LGRAY); c.setLineWidth(0.5); c.line(ML,cy,W-MR,cy)
    cy -= pad*mm

    # ── Analysis header ───────────────────────────────────────────
    sf(c,DARK_JET); c.setFont('PB',14); c.drawCentredString(W/2,cy,'Analysis')
    cy -= 6*mm
    sf(c,GRAY); c.setFont('P',8); c.drawCentredString(W/2,cy,'FINDINGS THIS WEEK')
    cy -= 8*mm

    # Analysis text
    cy = wrap(c, D.get('analysis',''), ML, cy, TW, sz=10, lead=15)
    cy -= pad*mm + 2*mm

    # ── Divider ──────────────────────────────────────────────────
    ss(c,LGRAY); c.setLineWidth(0.5); c.line(ML,cy,W-MR,cy)
    cy -= pad*mm

    # ── Plans Ahead header ────────────────────────────────────────
    sf(c,DARK_JET); c.setFont('PB',14); c.drawCentredString(W/2,cy,'Plans Ahead')
    cy -= 6*mm
    sf(c,GRAY); c.setFont('P',8); c.drawCentredString(W/2,cy,"WHAT WE'RE DOING NEXT")
    cy -= 9*mm

    # Plans text
    cy = wrap(c, D.get('plans',''), ML, cy, TW, sz=10, lead=15)
    cy -= pad*mm + 2*mm

    # Footer logo
    draw_logo(c, W/2-15*mm, cy-14*mm, 30*mm, 12*mm, white=False)

    c.save(); buf.seek(0); return buf


# ── Flask routes ──────────────────────────────────────────────
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
            'client', 'client_name', 'workflow', 'week2_dates',
            'invited_w2', 'messaged_w2', 'pr_count_w2', 'mb_count_w2',
            'ar_w2', 'pr_w2', 'mbr_w2',
            'ar_pct', 'pr_pct', 'mbr_pct',
            'ar_sev', 'pr_sev', 'mbr_sev',
            'analysis', 'plans',
        ]
        miss = [f for f in required if f not in data]
        if miss:
            return jsonify({'error': f'Missing fields: {miss}'}), 400
        buf = generate_pdf(data)
        fn = f"CA_{data['client'].replace(' ','_')}_Report.pdf"
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=fn)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
