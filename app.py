from flask import Flask, request, jsonify, send_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io, os, re

app = Flask(__name__)
BASE = os.path.dirname(os.path.abspath(__file__))

# ── Page ─────────────────────────────────────────────────────────
W, H = letter                      # 612 x 792 pt, same as the design sample
ML = MR = 57
TW = W - ML - MR                   # 498 pt content width
BOTTOM = 60                        # lowest point text may reach (from bottom)

# ── Colours (sampled from the design) ────────────────────────────
def hx(h): h = h.lstrip('#'); return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))

INK       = hx('#0B0E0F')   # cover background, titles, "% of target"
MUTED     = hx('#67696A')   # body text, KPI labels
SOFT      = hx('#909292')   # "Target: x%", legend
TAUPE     = hx('#62594C')   # dates, section subtitles, italic highlights
DIVIDER   = hx('#D9D5CE')
WHITE     = (1, 1, 1)
COVER_DATE = hx('#CDBB9E')
COVER_NAME = hx('#A9AAAB')

GREEN = hx('#2F8659')       # on / above target
GOLD  = hx('#B5872A')       # 76-99% of target
RED   = hx('#B4453A')       # below 76% of target

# ── Fonts ────────────────────────────────────────────────────────
SERIF    = 'CG-Light'
SERIF_IT = 'CG-LightItalic'
SANS     = 'MS-Regular'
SANS_SB  = 'MS-SemiBold'

FONT_FILES = {
    SERIF:    'CormorantGaramond-Light.ttf',
    SERIF_IT: 'CormorantGaramond-LightItalic.ttf',
    SANS:     'Montserrat-Regular.ttf',
    SANS_SB:  'Montserrat-SemiBold.ttf',
}

def reg_fonts():
    for name, fname in FONT_FILES.items():
        if name in pdfmetrics.getRegisteredFontNames():
            continue
        path = os.path.join(BASE, fname)
        if not os.path.exists(path):
            raise FileNotFoundError(f'Font file missing from repo: {fname}')
        pdfmetrics.registerFont(TTFont(name, path))

reg_fonts()

# ── Small helpers ────────────────────────────────────────────────
def Y(top):
    """Convert a distance from the top of the page to a ReportLab y."""
    return H - top

def text_w(txt, font, size, cs=0):
    return pdfmetrics.stringWidth(txt, font, size) + cs * max(len(txt) - 1, 0)

def txt(c, s, x, top, font, size, col, cs=0, align='l'):
    """Draw text with optional letter spacing. `top` is the baseline, measured from the page top."""
    w = text_w(s, font, size, cs)
    if align == 'c': x -= w / 2
    elif align == 'r': x -= w
    c.setFillColorRGB(*col)
    c.setFont(font, size)
    c.drawString(x, Y(top), s, charSpace=cs)
    return w

def hline(c, x1, x2, top, col=DIVIDER, lw=0.75):
    c.setStrokeColorRGB(*col); c.setLineWidth(lw)
    c.line(x1, Y(top), x2, Y(top))

def vline(c, x, top1, top2, col=DIVIDER, lw=0.75):
    c.setStrokeColorRGB(*col); c.setLineWidth(lw)
    c.line(x, Y(top1), x, Y(top2))

def draw_logo(c, x, top, w, h, white=True):
    f = os.path.join(BASE, 'logo_white_transparent.png' if white else 'logo_dark_transparent.png')
    if os.path.exists(f):
        c.drawImage(f, x, Y(top) - h, width=w, height=h, preserveAspectRatio=True, mask='auto')

def cf(val):
    try: return float(str(val).replace('%', '').replace(',', '').strip() or 0)
    except: return 0.0

def ci(val):
    try: return int(round(float(str(val).replace('%', '').replace(',', '').strip() or 0)))
    except: return 0

def fmt_rate(v):
    s = f'{v:.2f}'.rstrip('0').rstrip('.')
    return f'{s}%'

# ── Severity ─────────────────────────────────────────────────────
SEV_LABELS = {
    'critical': 'Critical', 'severe': 'Severe', 'poor': 'Poor',
    'below target': 'Below Target', 'near miss': 'Near Miss',
    'on target': 'On Target', 'above target': 'Above Target', 'strong': 'Above Target',
    'excellent': 'Excellent', 'exceptional': 'Exceptional',
}
GREEN_SEV = {'on target', 'above target', 'strong', 'excellent', 'exceptional'}
RED_SEV   = {'critical', 'severe', 'poor', 'below target'}

def sev_label(s):
    return SEV_LABELS.get(str(s).strip().lower(), str(s).strip())

def sev_colour(s, pct):
    v = str(s).strip().lower()
    if v in GREEN_SEV: return GREEN
    if v == 'near miss': return GOLD
    if v in RED_SEV: return RED
    # Unknown label: fall back to % of target
    if pct >= 100: return GREEN
    if pct >= 76: return GOLD
    return RED

# ── Rich text (body paragraphs) ──────────────────────────────────
# Wrap a phrase in *asterisks* and it prints as the gold serif italic highlight.
BODY_SIZE, BODY_LEAD, PARA_GAP = 9.75, 15, 12
IT_SIZE = 12
IT_EXTRA = 2          # extra space under a line that holds an italic highlight
BODY_CS = -0.025      # tiny negative tracking so line breaks match the design

def para_words(para):
    """Split a paragraph into words. Each word is a list of (text, italic) chunks."""
    runs, pos = [], 0
    for m in re.finditer(r'\*{1,2}([^*]+?)\*{1,2}', para):
        if m.start() > pos: runs.append((para[pos:m.start()], False))
        runs.append((m.group(1), True))
        pos = m.end()
    if pos < len(para): runs.append((para[pos:], False))

    words, cur = [], []
    for text, it in runs:
        text = text.replace('*', '')
        for i, piece in enumerate(re.split(r'(\s+)', text)):
            if not piece: continue
            if piece.isspace():
                if cur: words.append(cur); cur = []
            else:
                cur.append((piece, it))
    if cur: words.append(cur)
    return words

def chunk_w(t, it):
    if it:
        return pdfmetrics.stringWidth(t, SERIF_IT, IT_SIZE)
    return pdfmetrics.stringWidth(t, SANS, BODY_SIZE) + BODY_CS * len(t)

def word_w(word):
    return sum(chunk_w(t, it) for t, it in word)

def space_w(prev, nxt):
    it = prev[-1][1] and nxt[0][1]
    return pdfmetrics.stringWidth(' ', SERIF_IT if it else SANS, IT_SIZE if it else BODY_SIZE)

def wrap_para(words, max_w):
    lines, line, lw = [], [], 0
    for w in words:
        ww = word_w(w)
        add = ww if not line else space_w(line[-1], w) + ww
        if line and lw + add > max_w:
            lines.append(line); line, lw = [w], ww
        else:
            line.append(w); lw += add
    if line: lines.append(line)
    return lines

def split_paras(text):
    text = str(text or '').replace('\\n', '\n').replace('\r', '').strip()
    paras = [p.replace('\n', ' ').strip() for p in re.split(r'\n\s*\n', text)]
    return [p for p in paras if p]

# ── Page flow (handles long text running onto a new page) ────────
class Flow:
    def __init__(self, c):
        self.c = c

    def new_page(self):
        self.c.showPage()
        self.c.setFillColorRGB(*WHITE); self.c.rect(0, 0, W, H, fill=1, stroke=0)
        draw_logo(self.c, W/2 - 23.25, 16.5, 46.5, 43.5, white=False)
        return 100   # first baseline on a continuation page

    def body(self, text, top):
        """Draw body paragraphs. `top` is the first baseline. Returns the last baseline."""
        c = self.c
        last = top
        first = True
        for para in split_paras(text):
            if not first: top += PARA_GAP
            for line in wrap_para(para_words(para), TW):
                if top > H - BOTTOM:
                    top = self.new_page()
                x = ML
                has_it = False
                for i, word in enumerate(line):
                    if i: x += space_w(line[i-1], word)
                    for t, it in word:
                        if it:
                            has_it = True
                            c.setFillColorRGB(*TAUPE); c.setFont(SERIF_IT, IT_SIZE)
                        else:
                            c.setFillColorRGB(*MUTED); c.setFont(SANS, BODY_SIZE)
                        c.drawString(x, Y(top), t, charSpace=0 if it else BODY_CS)
                        x += chunk_w(t, it)
                last = top
                top += BODY_LEAD + (IT_EXTRA if has_it else 0)
            first = False
        return last

    def section(self, title, subtitle, text, title_top):
        """Section header + body. Moves to a new page if the header would sit alone."""
        if title_top + 17.3 + 24.7 + BODY_LEAD * 2 > H - BOTTOM:
            title_top = self.new_page()
        txt(self.c, title, W/2, title_top, SERIF, 21, INK, cs=-0.35, align='c')
        txt(self.c, subtitle, W/2, title_top + 17.3, SANS_SB, 7.5, TAUPE, cs=1.8, align='c')
        return self.body(text, title_top + 17.3 + 24.7)

# ── PDF builder ──────────────────────────────────────────────────
def generate_pdf(D):
    dates = str(D.get('week2_dates', '')).strip()
    cname = str(D.get('client_name', '')).strip()

    kpis = []
    for label, vk, pk, sk, target in [
        ('Acceptance Rate',        'ar_w2',  'ar_pct',  'ar_sev',  '35%'),
        ('Positive Response Rate', 'pr_w2',  'pr_pct',  'pr_sev',  '5%'),
        ('Meeting Booked Rate',    'mbr_w2', 'mbr_pct', 'mbr_sev', '60%'),
    ]:
        pct = ci(D.get(pk, 0))
        sev = D.get(sk, '')
        kpis.append(dict(label=label, val=cf(D.get(vk, 0)), pct=pct,
                         sev=sev_label(sev), col=sev_colour(sev, pct), target=target))

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle(f'Weekly Report {cname}'.strip())

    # ── PAGE 1: COVER ────────────────────────────────────────────
    c.setFillColorRGB(*INK); c.rect(0, 0, W, H, fill=1, stroke=0)
    draw_logo(c, W/2 - 56.25, 225, 112.5, 105, white=True)
    txt(c, 'Weekly Report', W/2, 453, SERIF, 40.5, WHITE, cs=-0.9, align='c')
    txt(c, dates, W/2, 491.2, SANS, 11.25, COVER_DATE, cs=0.65, align='c')
    if cname:
        txt(c, cname.upper(), W/2, 533.2, SANS_SB, 9.75, COVER_NAME, cs=2.25, align='c')
    c.showPage()

    # ── PAGE 2: METRICS, ANALYSIS, PLANS ─────────────────────────
    c.setFillColorRGB(*WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    draw_logo(c, W/2 - 23.25, 16.5, 46.5, 43.5, white=False)

    txt(c, 'Metrics', W/2, 93.7, SERIF, 24, INK, cs=-0.4, align='c')
    txt(c, dates, W/2, 111, SANS_SB, 7.5, TAUPE, cs=1.75, align='c')

    # KPI columns
    col_w = TW / 3
    for i, k in enumerate(kpis):
        cx = ML + col_w * (i + 0.5)
        txt(c, k['label'].upper(), cx, 150, SANS_SB, 7.5, MUTED, cs=1.4, align='c')

        # Status pill
        pill = k['sev'].upper()
        pw = text_w(pill, SANS_SB, 6.75, 0.9) + 20
        c.setStrokeColorRGB(*k['col']); c.setLineWidth(0.75)
        c.roundRect(cx - pw/2, Y(174.4), pw, 15, 7.5, stroke=1, fill=0)
        txt(c, pill, cx, 169.5, SANS_SB, 6.75, k['col'], cs=0.9, align='c')

        txt(c, fmt_rate(k['val']), cx, 214.5, SERIF, 33, k['col'], align='c')
        txt(c, f"{k['pct']}% of target", cx, 239.2, SANS, 9, INK, align='c')
        txt(c, f"Target: {k['target']}", cx, 255.7, SANS, 7.5, SOFT, align='c')

    for i in (1, 2):
        vline(c, ML + col_w * i, 142.5, 258)

    # Legend (centred row)
    items = [(GREEN, 'ON / ABOVE TARGET'), (GOLD, 'BETWEEN 76-99% OF TARGET'), (RED, 'BELOW 76% OF TARGET')]
    DOT, DOT_GAP, ITEM_GAP, LCS = 6, 5.3, 33.7, 0.95
    widths = [DOT + DOT_GAP + text_w(t, SANS, 6.75, LCS) for _, t in items]
    lx = W/2 - (sum(widths) + ITEM_GAP * (len(items) - 1)) / 2
    for (col, t), iw in zip(items, widths):
        c.setFillColorRGB(*col)
        c.circle(lx + DOT/2, Y(268.5), DOT/2, stroke=0, fill=1)
        txt(c, t, lx + DOT + DOT_GAP, 270.7, SANS, 6.75, SOFT, cs=LCS)
        lx += iw + ITEM_GAP

    hline(c, ML, W - MR, 296.6)

    flow = Flow(c)
    last = flow.section('Analysis', 'FINDINGS THIS WEEK', D.get('analysis', ''), 341.2)
    flow.section('Plans Ahead', "WHAT WE'RE DOING NEXT", D.get('plans', ''), last + 52.5)

    c.save(); buf.seek(0)
    return buf

# ── Flask routes ─────────────────────────────────────────────────
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
        fn = f"CA_{str(data['client']).replace(' ', '_')}_Report.pdf"
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=fn)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
