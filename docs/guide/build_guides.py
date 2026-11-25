"""Builds the two BloomClipping guides (English + Hindi PDF) from one content file, with the annotated screenshots in img/.

Steps to rebuild (the screens change, so do this after UI changes):
  1. Start a CLEAN instance (own empty data folder, never your real one):
       set BLOOMCLIPPING_DATA_DIR=D:\\guide_shots_data & set BLOOMCLIPPING_PORT=8791 & python app.py
     copy any 16:9 mp4 named guidedemo0001.mp4 into that folder, export one demo clip from it, note the clip id.
  2. python docs/guide/make_shots.py <demo-clip-id>        (needs playwright + pillow + Chrome)
  3. python docs/guide/build_guides.py                      (writes ../BloomClipping-Guide-English.pdf and ../BloomClipping-Guide-Hindi.pdf)
Every text exists in English and Hindi side by side in this file (function t(en, hi)) so the two guides cannot drift apart.
"""
import html
import json
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
DOCS = HERE.parent
IMG = HERE / 'img'
SHOTS = json.loads((IMG / 'shots.json').read_text(encoding='utf-8'))
GH = 'github.com/bloomclipping'
SITE = 'bloom.github.io/bloomclipping'
try:
    SHA = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, cwd=HERE).stdout.strip() or 'main'
except Exception:
    SHA = 'main'

CSS = """
@page { size: A4; margin: 14mm 13mm 16mm 13mm; }
* { box-sizing: border-box; }
html { font-family: %(font)s; color: #1c1c28; font-size: 10.6pt; line-height: 1.5; }
body { margin: 0; }
h1,h2,h3,h4 { margin: 0; line-height: 1.2; }
.cover { height: 262mm; border-radius: 22px; padding: 22mm 18mm; color: #fff; display: flex; flex-direction: column; justify-content: space-between;
  background: radial-gradient(circle at 80%% 15%%, #ff3d6e 0, transparent 38%%), radial-gradient(circle at 10%% 90%%, #6a3093 0, transparent 45%%), #0e0e16; page-break-after: always; }
.cover .brand { font-weight: 800; letter-spacing: .12em; font-size: 12pt; color: #ffb3c6; }
.cover h1 { font-size: 40pt; font-weight: 800; }
.cover h1 em { color: #ff6b93; font-style: normal; }
.cover p { font-size: 13pt; color: #e8e8f2; max-width: 150mm; }
.cover .chips span { display: inline-block; margin: 0 6px 6px 0; padding: 4px 12px; border-radius: 99px; background: #ffffff22; font-size: 10pt; }
.cover small { color: #b9b9cc; }
.toc { page-break-after: always; }
.toc h2 { font-size: 22pt; margin-bottom: 8mm; }
.toc li { margin: 0 0 3.2mm 0; font-size: 12pt; }
.toc li small { color: #6b6b80; display: block; font-size: 9.5pt; }
.part { page-break-before: always; margin-bottom: 6mm; }
.part .no { display: inline-block; background: #ff3d6e; color: #fff; font-weight: 800; border-radius: 10px; padding: 2px 12px; font-size: 11pt; }
.part h2 { font-size: 25pt; margin: 3mm 0 2mm; }
.part p.lead { color: #55556a; font-size: 12pt; margin: 0; }
h3 { font-size: 14.5pt; margin: 7mm 0 2.5mm; color: #14141f; }
h3::before { content: ""; display: inline-block; width: 5px; height: 15px; background: #ff3d6e; border-radius: 3px; margin-right: 8px; vertical-align: -2px; }
h4 { font-size: 11pt; margin: 4mm 0 1.5mm; color: #3a3a50; }
p { margin: 0 0 2.5mm; }
.step { display: flex; gap: 10px; margin: 0 0 3.2mm; break-inside: avoid; }
.step .n { flex: none; width: 24px; height: 24px; border-radius: 50%%; background: #ff3d6e; color: #fff; font-weight: 800; text-align: center; line-height: 24px; font-size: 10.5pt; margin-top: 1px; }
.step .b { flex: 1; }
.step .b > b:first-child { display: block; }
.callout { border-radius: 12px; padding: 3mm 4mm; margin: 3mm 0; break-inside: avoid; border: 1px solid; }
.callout.tip { background: #eefbf3; border-color: #9fe0b5; }
.callout.warn { background: #fff6e8; border-color: #f2c37c; }
.callout.info { background: #eef4ff; border-color: #a9c4f5; }
.callout b:first-child { margin-right: 4px; }
code, .cmd { font-family: Consolas, "Cascadia Mono", monospace; }
code { background: #f0f0f6; padding: 0 4px; border-radius: 4px; font-size: 9.6pt; }
.cmd { background: #14141f; color: #e9e9f5; border-radius: 10px; padding: 3mm 4mm; margin: 2mm 0 3mm; font-size: 9.6pt; white-space: pre-wrap; break-inside: avoid; }
.cmd i { color: #ff8fb0; font-style: normal; }
.shot { margin: 4mm 0 5mm; break-inside: avoid; }
.shot img { width: 100%%; border-radius: 12px; border: 1px solid #d9d9e6; display: block; }
.legend { margin: 2.5mm 0 0; padding: 0; list-style: none; display: grid; grid-template-columns: 1fr 1fr; gap: 1.5mm 6mm; }
.legend li { display: flex; gap: 7px; font-size: 9.6pt; align-items: flex-start; }
.legend li i { flex: none; width: 18px; height: 18px; border-radius: 50%%; background: #ff3d6e; color: #fff; font-style: normal; font-weight: 800; font-size: 8.8pt; text-align: center; line-height: 18px; margin-top: 1px; }
.cards { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4mm; margin: 3mm 0; }
.card { border: 1px solid #dcdce8; border-radius: 12px; padding: 3.5mm; background: #fafaff; break-inside: avoid; }
.card b { display: block; margin-bottom: 1mm; color: #ff3d6e; }
.card small { color: #55556a; font-size: 9.4pt; line-height: 1.4; display: block; }
.card small b { display: inline; margin: 0; color: #2a2a3a; }
table { border-collapse: collapse; width: 100%%; margin: 3mm 0; font-size: 9.8pt; break-inside: avoid; }
th, td { border: 1px solid #dcdce8; padding: 2mm 3mm; text-align: left; vertical-align: top; }
th { background: #f3f3fa; }
.qa { break-inside: avoid; margin: 0 0 3.4mm; padding: 3mm 4mm; border-left: 4px solid #ff3d6e; background: #fafaff; border-radius: 0 10px 10px 0; }
.qa b { display: block; margin-bottom: 1mm; }
.kbd { display: inline-block; border: 1px solid #c9c9da; border-bottom-width: 2px; border-radius: 5px; padding: 0 6px; font-family: Consolas, monospace; font-size: 9.4pt; background: #fff; }
.flow { display: flex; align-items: stretch; gap: 3mm; margin: 4mm 0; }
.flow > div { flex: 1; border: 1px solid #dcdce8; border-radius: 12px; padding: 3mm; background: #fafaff; text-align: center; font-size: 9.8pt; }
.flow > span { align-self: center; font-size: 18pt; color: #ff3d6e; font-weight: 800; }
.flow b { display: block; color: #ff3d6e; font-size: 16pt; }
"""


def build(lang):
    hi = lang == 'hi'

    def t(en, hindi):
        return hindi if hi else en

    def esc(s):
        return html.escape(s, quote=False)

    # ---------- small building blocks
    def step(n, title, body=''):
        return f'<div class="step"><div class="n">{n}</div><div class="b"><b>{title}</b>{body}</div></div>'

    def callout(kind, label, body):
        return f'<div class="callout {kind}"><b>{label}</b>{body}</div>'

    def cmd(text):
        return f'<div class="cmd">{esc(text)}</div>'

    def shot(name, legend):
        """legend: {selector: (en, hi)}; markers appear in the order make_shots.py listed them (only those that existed)."""
        used = SHOTS.get(name, [])
        items = ''.join(f'<li><i>{i}</i><span>{t(*legend[s])}</span></li>' for i, s in enumerate(used, 1) if s in legend)
        return f'<div class="shot"><img src="img/{name}.jpg" alt=""><ul class="legend">{items}</ul></div>'

    def qa(q, a):
        return f'<div class="qa"><b>{q}</b>{a}</div>'

    def part(no, title, lead):
        return f'<section class="part"><span class="no">{no}</span><h2>{title}</h2><p class="lead">{lead}</p></section>'

    out = []
    # ---------- cover + contents
    out.append(f"""<div class="cover"><div><div class="brand">BLOOMCLIPPING</div></div>
<div><h1>{t('The complete <em>guide</em>', 'पूरी <em>गाइड</em>')}</h1>
<p>{t('Install it, update it, and use every part of it. Step by step, with pictures and arrows.', 'इंस्टॉल करें, अपडेट करें और हर हिस्सा इस्तेमाल करें। एक-एक कदम, तस्वीरों और तीरों के साथ।')}</p></div>
<div><div class="chips"><span>{t('Free', 'फ्री')}</span><span>{t('Runs on your PC', 'आपके PC पर चलता है')}</span><span>{t('Open-source', 'ओपन-सोर्स')}</span><span>9:16 Shorts · Reels · TikTok</span></div>
<small>{t('Made by Bloom', 'अजय के मीणा द्वारा')} · {GH} · {t('version', 'वर्ज़न')} {SHA}</small></div></div>""")
    out.append(f"""<div class="toc"><h2>{t('What is inside', 'इसमें क्या है')}</h2><ol>
<li>{t('Install it', 'इंस्टॉल करना')}<small>{t('Windows in two clicks, Mac / Linux, or let an AI agent do it', 'Windows पर दो क्लिक में, Mac / Linux, या AI एजेंट से')}</small></li>
<li>{t('Update it', 'अपडेट करना')}<small>{t('If you installed it before: what is new and how to update safely', 'अगर पहले इंस्टॉल किया था: क्या नया है और सुरक्षित अपडेट कैसे करें')}</small></li>
<li>{t('Use it', 'इस्तेमाल करना')}<small>{t('Make clips, captions, layouts, the Editor, My clips, Storage, live streams', 'क्लिप बनाना, कैप्शन, लेआउट, एडिटर, My clips, स्टोरेज, लाइव स्ट्रीम')}</small></li>
<li>{t('Questions and fixes', 'सवाल और समाधान')}<small>{t('The things people ask most, and what to do when something goes wrong', 'लोग सबसे ज़्यादा क्या पूछते हैं, और कुछ गड़बड़ हो तो क्या करें')}</small></li>
<li>{t('Cheat sheet', 'चीट शीट')}<small>{t('Keys and tips on one page', 'एक पन्ने पर कीज़ और टिप्स')}</small></li></ol></div>""")

    # ================= PART 1: INSTALL
    out.append(part('1', t('Install it', 'इंस्टॉल करना'), t('Pick the way that fits you. Windows is the easiest.', 'अपने हिसाब का तरीका चुनें। Windows सबसे आसान है।')))
    out.append(f"""<h3>{t('What you need', 'क्या चाहिए')}</h3>
<div class="cards">
<div class="card"><b>{t('A computer', 'एक कंप्यूटर')}</b><small>{t('Windows 10/11 (easiest), Mac or Linux. About 10 GB free disk space.', 'Windows 10/11 (सबसे आसान), Mac या Linux। करीब 10 GB खाली जगह।')}</small></div>
<div class="card"><b>{t('Internet (once)', 'इंटरनेट (एक बार)')}</b><small>{t('To download the program and its helpers. After that, clipping itself runs on your PC.', 'प्रोग्राम और उसके सहायक डाउनलोड करने के लिए। उसके बाद क्लिपिंग आपके PC पर ही चलती है।')}</small></div>
<div class="card"><b>{t('Optional extras', 'ऑप्शनल चीज़ें')}</b><small>{t('An NVIDIA graphics card makes it faster. Ollama (a free local AI) writes smarter titles. Neither is required.', 'NVIDIA ग्राफिक्स कार्ड से तेज़ चलता है। Ollama (फ्री लोकल AI) बेहतर टाइटल लिखता है। दोनों ज़रूरी नहीं।')}</small></div></div>""")
    out.append(f"""<h3>{t('Way 1 · Windows, two clicks (recommended)', 'तरीका 1 · Windows, दो क्लिक (सुझाया गया)')}</h3>
<div class="flow"><div><b>1</b>{t('Download <code>BloomClipping-Setup.bat</code>', '<code>BloomClipping-Setup.bat</code> डाउनलोड करें')}</div><span>→</span><div><b>2</b>{t('Double-click it', 'उस पर डबल-क्लिक करें')}</div><span>→</span><div><b>3</b>{t('Wait, the app opens by itself', 'रुकें, ऐप अपने आप खुल जाएगा')}</div></div>""")
    out.append(step(1, t(f'Open the website <code>{SITE}</code> and press the download button', f'वेबसाइट <code>{SITE}</code> खोलें और डाउनलोड बटन दबाएँ'),
                     t('You can also take <code>BloomClipping-Setup.bat</code> from the Releases page on GitHub.', 'आप GitHub के Releases पेज से भी <code>BloomClipping-Setup.bat</code> ले सकते हैं।')))
    out.append(step(2, t('Double-click <code>BloomClipping-Setup.bat</code>', '<code>BloomClipping-Setup.bat</code> पर डबल-क्लिक करें'),
                    t('A black window opens and prints what it is doing. It only runs one installer file (<code>install.ps1</code>); you can open the .bat in Notepad first if you want to read it. If Windows shows a blue warning for a downloaded file, you can choose <b>More info</b> and then <b>Run anyway</b>.',
                      'एक काली विंडो खुलकर बताती है कि वो क्या कर रही है। ये सिर्फ एक इंस्टॉलर फाइल (<code>install.ps1</code>) चलाती है; चाहें तो पहले .bat को Notepad में खोलकर पढ़ लें। अगर Windows डाउनलोड की फाइल पर नीली चेतावनी दिखाए, तो <b>More info</b> और फिर <b>Run anyway</b> चुन सकते हैं।')))
    out.append(step(3, t('Let it finish (a few minutes)', 'उसे पूरा होने दें (कुछ मिनट)'),
                    t('It checks your PC, installs <b>Python</b> and <b>FFmpeg</b> if they are missing, puts BloomClipping in <code>%LOCALAPPDATA%\\BloomClipping</code>, makes a <b>Desktop shortcut</b> and opens the app.',
                      'ये आपका PC जाँचती है, <b>Python</b> और <b>FFmpeg</b> न हों तो इंस्टॉल करती है, BloomClipping को <code>%LOCALAPPDATA%\\BloomClipping</code> में रखती है, <b>Desktop शॉर्टकट</b> बनाती है और ऐप खोल देती है।')))
    out.append(step(4, t('Next time, use the Desktop shortcut', 'अगली बार Desktop शॉर्टकट से खोलें'),
                    t(f'The app lives at <code>http://127.0.0.1:8770</code> in your browser. If that address is busy, it picks 8771 (or set <code>BLOOMCLIPPING_PORT</code>).',
                      f'ऐप आपके ब्राउज़र में <code>http://127.0.0.1:8770</code> पर चलता है। अगर वो पता बिज़ी हो तो 8771 चुन लेता है (या <code>BLOOMCLIPPING_PORT</code> सेट करें)।')))
    out.append(callout('tip', t('Good to know', 'जानने लायक'), t('Everything lives in one folder. To remove BloomClipping later, delete that folder and the Desktop shortcut. Your clips are inside it (in <code>data</code>), so copy them out first.',
                                                                'सब कुछ एक ही फोल्डर में रहता है। बाद में हटाना हो तो वो फोल्डर और Desktop शॉर्टकट डिलीट करें। आपके क्लिप उसी के अंदर (<code>data</code> में) हैं, इसलिए पहले उन्हें कॉपी कर लें।')))
    out.append(f"""<h3>{t('Way 2 · Mac or Linux', 'तरीका 2 · Mac या Linux')}</h3>
<p>{t('Open Terminal and run these lines one by one:', 'Terminal खोलें और ये लाइनें एक-एक करके चलाएँ:')}</p>""")
    out.append(cmd('git clone #\ncd bloomclipping\n./install.sh'))
    out.append(f"<p>{t('Start it later with <code>./run.sh</code>, then open <code>http://127.0.0.1:8770</code> in your browser. The video encoder is chosen by what works on your computer (NVIDIA, Apple VideoToolbox, or the CPU).', 'बाद में <code>./run.sh</code> से चलाएँ, फिर ब्राउज़र में <code>http://127.0.0.1:8770</code> खोलें। वीडियो एन्कोडर वही चुना जाता है जो आपके कंप्यूटर पर चलता है (NVIDIA, Apple VideoToolbox या CPU)।')}</p>")
    out.append(f"""<h3>{t('Way 3 · Let an AI agent install it', 'तरीका 3 · AI एजेंट से इंस्टॉल करवाएँ')}</h3>
<p>{t('If you use Claude Code, Codex or a similar agent that can run commands, give it the file <code>docs/BLOOMCLIPPING-AGENT-SETUP-PROMPT.txt</code> from the repository. It checks your PC, installs only what is missing, asks before any big download and opens the app in Chrome.',
      'अगर आप Claude Code, Codex या ऐसा कोई एजेंट इस्तेमाल करते हैं जो कमांड चला सके, तो उसे रिपॉज़िटरी की फाइल <code>docs/BLOOMCLIPPING-AGENT-SETUP-PROMPT.txt</code> दें। वो आपका PC जाँचता है, सिर्फ वही इंस्टॉल करता है जो कम है, बड़े डाउनलोड से पहले पूछता है और ऐप को Chrome में खोल देता है।')}</p>""")
    out.append(f"""<h3>{t('Way 4 · Developers (git)', 'तरीका 4 · डेवलपर्स (git)')}</h3>""")
    out.append(cmd('git clone #\ncd bloomclipping\n./run.ps1        # Windows\n./run.sh         # Mac / Linux'))
    out.append(f"""<h3>{t('First run: what to expect', 'पहली बार: क्या होगा')}</h3>
{step(1, t('The page opens with a status line', 'पेज एक स्टेटस लाइन के साथ खुलता है'), t('It shows FFmpeg, the video encoder (for example NVIDIA GPU), YouTube support, the AI model and free disk. Green ticks mean ready.', 'उसमें FFmpeg, वीडियो एन्कोडर (जैसे NVIDIA GPU), YouTube सपोर्ट, AI मॉडल और खाली डिस्क दिखती है। हरे टिक का मतलब तैयार।'))}
{step(2, t('The first clip downloads a speech model once (about 1.6 GB)', 'पहली क्लिप पर स्पीच मॉडल एक बार डाउनलोड होता है (करीब 1.6 GB)'), t('This is only used when a video has no YouTube captions. It is saved and never downloaded again.', 'ये सिर्फ तब काम आता है जब वीडियो में YouTube कैप्शन न हों। ये सेव रहता है और दोबारा डाउनलोड नहीं होता।'))}
{step(3, t('Optional: install Ollama for smarter titles', 'ऑप्शनल: बेहतर टाइटल के लिए Ollama इंस्टॉल करें'), t('Install Ollama from ollama.com, then run <code>ollama pull llama3.2:3b</code> once. Without it clips are still picked, using the audio and motion score.', 'ollama.com से Ollama इंस्टॉल करें, फिर एक बार <code>ollama pull llama3.2:3b</code> चलाएँ। इसके बिना भी क्लिप चुने जाते हैं, ऑडियो और मोशन स्कोर से।'))}""")

    # ================= PART 2: UPDATE
    out.append(part('2', t('Update it', 'अपडेट करना'), t('Already installed an older version? You keep your clips and settings.', 'पहले से पुराना वर्ज़न इंस्टॉल है? आपके क्लिप और सेटिंग्स बनी रहती हैं।')))
    out.append(f"""<h3>{t('What is new in this version', 'इस वर्ज़न में क्या नया है')}</h3>
<div class="cards">
<div class="card"><b>{t('Editor', 'एडिटर')}</b><small>{t('Live 9:16 preview of your cut, a thumbnail timeline you drag, split / duplicate / reorder pieces, drag the camera and game boxes on the real frame, drag the captions.', 'आपके कट का लाइव 9:16 प्रीव्यू, थंबनेल टाइमलाइन जिसे आप ड्रैग करते हैं, पीस को स्प्लिट / डुप्लिकेट / रीऑर्डर करना, असली फ्रेम पर कैमरा और गेम बॉक्स ड्रैग करना, कैप्शन ड्रैग करना।')}</small></div>
<div class="card"><b>{t('Live Preview panel', 'लाइव प्रीव्यू पैनल')}</b><small>{t('A right-side panel shows the real clip with the chosen caption, layout and heading. It also has a Make clips button and live progress bars with percentages.', 'दाईं तरफ का पैनल असली क्लिप को चुने हुए कैप्शन, लेआउट और हेडिंग के साथ दिखाता है। उसमें Make clips बटन और प्रतिशत वाली लाइव प्रोग्रेस बार भी है।')}</small></div>
<div class="card"><b>{t('13 caption styles', '13 कैप्शन स्टाइल')}</b><small>{t('Karaoke (default), TikTok, Pill, One word, Cinematic, Boxed, Outlined, Comic and more, each drawn the way it looks on the finished clip.', 'Karaoke (डिफ़ॉल्ट), TikTok, Pill, One word, Cinematic, Boxed, Outlined, Comic और भी, हर एक वैसा ही दिखता है जैसा तैयार क्लिप पर।')}</small></div>
<div class="card"><b>{t('Simpler screen', 'आसान स्क्रीन')}</b><small>{t('One Advanced area with tabs, an Activity list, smart defaults (1080p, 9:16, captions on, facecam found for you) and your choices remembered.', 'एक Advanced एरिया टैब के साथ, Activity लिस्ट, स्मार्ट डिफ़ॉल्ट (1080p, 9:16, कैप्शन ऑन, फेसकैम अपने आप) और आपकी पसंद याद रहती है।')}</small></div>
<div class="card"><b>{t('Storage, delete, updates', 'स्टोरेज, डिलीट, अपडेट')}</b><small>{t('A Storage card to free space or choose another folder, a trash button and Select mode in My clips, and an Updates card.', 'जगह खाली करने या दूसरा फोल्डर चुनने के लिए Storage कार्ड, My clips में ट्रैश बटन और Select मोड, और Updates कार्ड।')}</small></div>
<div class="card"><b>{t('Better scores and words', 'बेहतर स्कोर और शब्द')}</b><small>{t('Hook / engagement / value / shareability scores, export presets for Shorts, TikTok and Reels, caption font, size and colours, volume, and English words like “police” spelled correctly in Hinglish.', 'हुक / एंगेजमेंट / वैल्यू / शेयरबिलिटी स्कोर, Shorts, TikTok और Reels के एक्सपोर्ट प्रीसेट, कैप्शन फॉन्ट, साइज़ और रंग, वॉल्यूम, और Hinglish में “police” जैसे अंग्रेज़ी शब्द सही स्पेलिंग में।')}</small></div></div>""")
    out.append(f"""<h3>{t('Update, the easy way (inside the app)', 'अपडेट, आसान तरीका (ऐप के अंदर)')}</h3>
{shot('updates', {'#side-version': ('The Updates card in the sidebar says “New version ready” when one exists.', 'साइडबार का Updates कार्ड नया वर्ज़न होने पर “New version ready” लिखता है।'),
                  '#update-bar': ('A green bar at the top: press <b>Update now</b>, or wait and it updates by itself when nothing is running.', 'ऊपर हरी बार: <b>Update now</b> दबाएँ, या रुकें, जब कुछ नहीं चल रहा होगा तब अपने आप अपडेट हो जाएगा।'),
                  '#side-storage': ('Your clips, settings and downloaded models are kept.', 'आपके क्लिप, सेटिंग्स और डाउनलोड किए मॉडल सुरक्षित रहते हैं।')})}
{step(1, t('Open BloomClipping as usual', 'BloomClipping हमेशा की तरह खोलें'), t('The app checks GitHub for a newer version (one small request). Nothing else is sent.', 'ऐप GitHub पर नया वर्ज़न देखता है (एक छोटा रिक्वेस्ट)। और कुछ नहीं भेजा जाता।'))}
{step(2, t('Press <b>Update now</b> in the green bar', 'हरी बार में <b>Update now</b> दबाएँ'), t('It downloads the new files, replaces the program, keeps <code>data</code>, <code>models</code>, your settings and caches, and keeps one backup of the old files in <code>.update-backup</code>.', 'ये नई फाइलें डाउनलोड करता है, प्रोग्राम बदलता है, <code>data</code>, <code>models</code>, आपकी सेटिंग्स और कैश को रखता है, और पुरानी फाइलों का एक बैकअप <code>.update-backup</code> में रखता है।'))}
{step(3, t('Wait for the restart', 'रीस्टार्ट का इंतज़ार करें'), t('The app restarts by itself and the page reloads. Done.', 'ऐप अपने आप रीस्टार्ट होता है और पेज रीलोड हो जाता है। बस।'))}
{callout('warn', t('Installed a very old version?', 'बहुत पुराना वर्ज़न इंस्टॉल है?'), t('Versions from before the in-app updater do not have the green bar. Run <code>BloomClipping-Setup.bat</code> <b>once more</b> (same file as the install). It updates in place and keeps your data. After that, updates come from inside the app.', 'इन-ऐप अपडेटर से पहले के वर्ज़न में हरी बार नहीं होती। <code>BloomClipping-Setup.bat</code> <b>एक बार फिर</b> चलाएँ (वही फाइल जो इंस्टॉल में थी)। ये उसी जगह अपडेट करती है और आपका डेटा रखती है। उसके बाद अपडेट ऐप के अंदर से आएँगे।'))}
<h3>{t('If you installed with git', 'अगर आपने git से इंस्टॉल किया था')}</h3>
<p>{t('The in-app updater never touches a git copy. Update it yourself:', 'इन-ऐप अपडेटर git वाली कॉपी को कभी नहीं छूता। उसे खुद अपडेट करें:')}</p>""")
    out.append(cmd('cd bloomclipping\ngit pull\n.venv/Scripts/pip install -r requirements.txt   # Windows; use .venv/bin/pip on Mac / Linux'))
    out.append(f"""<h3>{t('After an update: quick check', 'अपडेट के बाद: जल्दी जाँच')}</h3>
{step(1, t('Hard-refresh the page', 'पेज को हार्ड-रिफ्रेश करें'), t('Press <span class="kbd">Ctrl</span> + <span class="kbd">F5</span> so the browser loads the new screen.', '<span class="kbd">Ctrl</span> + <span class="kbd">F5</span> दबाएँ ताकि ब्राउज़र नई स्क्रीन लोड करे।'))}
{step(2, t('Look at the status line', 'स्टेटस लाइन देखें'), t('FFmpeg, encoder and AI model should show green ticks.', 'FFmpeg, एन्कोडर और AI मॉडल पर हरे टिक होने चाहिए।'))}
{step(3, t('Open <b>My clips</b>', '<b>My clips</b> खोलें'), t('Your old clips are still there. Press <b>Edit</b> on one to try the new Editor.', 'आपके पुराने क्लिप वहीं हैं। नया एडिटर आज़माने के लिए किसी पर <b>Edit</b> दबाएँ।'))}
{callout('info', t('If an update goes wrong', 'अगर अपडेट में गड़बड़ हो'), t('Your data is not touched. The replaced program files are in <code>.update-backup</code>. Running <code>BloomClipping-Setup.bat</code> again repairs the install.', 'आपका डेटा नहीं छुआ जाता। बदली गई प्रोग्राम फाइलें <code>.update-backup</code> में हैं। <code>BloomClipping-Setup.bat</code> दोबारा चलाने से इंस्टॉल ठीक हो जाता है।'))}""")

    # ================= PART 3: USE
    out.append(part('3', t('Use it', 'इस्तेमाल करना'), t('From a link to finished clips. Every picture has numbered arrows that match the list under it.', 'लिंक से तैयार क्लिप तक। हर तस्वीर में नंबर वाले तीर हैं जो उसके नीचे की लिस्ट से मिलते हैं।')))
    out.append(f"""<h3>{t('The screen at a glance', 'स्क्रीन एक नज़र में')}</h3>
{shot('home', {'[data-view=editor]': ('<b>Create clips</b>: make new clips from a link or a file.', '<b>Create clips</b>: लिंक या फाइल से नए क्लिप बनाएँ।'),
               '[data-view=library]': ('<b>My clips</b>: everything you made. Download, edit or delete.', '<b>My clips</b>: आपके बनाए सारे क्लिप। डाउनलोड, एडिट या डिलीट करें।'),
               '#nav-clip-editor': ('<b>Editor</b>: polish a finished clip with a live preview.', '<b>Editor</b>: लाइव प्रीव्यू के साथ तैयार क्लिप को निखारें।'),
               '#url': ('Paste a YouTube, Twitch or Kick link here (or press <b>Upload video</b>).', 'यहाँ YouTube, Twitch या Kick का लिंक पेस्ट करें (या <b>Upload video</b> दबाएँ)।'),
               '#srcq': ('Download quality. Default 1080p; choose 4K here if you want it.', 'डाउनलोड क्वालिटी। डिफ़ॉल्ट 1080p; चाहें तो यहाँ 4K चुनें।'),
               '#link': ('<b>Get preview</b>: load frames first, set the camera area, then make clips.', '<b>Get preview</b>: पहले फ्रेम लोड करें, कैमरा एरिया सेट करें, फिर क्लिप बनाएँ।'),
               '#make': ('<b>Make clips</b>: one click, everything automatic.', '<b>Make clips</b>: एक क्लिक, सब कुछ अपने आप।'),
               '#rb-make': ('The same Make clips button, in the Live Preview panel, with progress bars below it.', 'वही Make clips बटन, Live Preview पैनल में, नीचे प्रोग्रेस बार के साथ।')})}""")
    out.append(f"""<h3>{t('Make clips in one click', 'एक क्लिक में क्लिप बनाएँ')}</h3>
{step(1, t('Paste the link', 'लिंक पेस्ट करें'), t('A YouTube video, a Twitch or Kick replay, or press <b>Upload video</b> for your own MP4. For a very long video you can pick the part you want.', 'YouTube वीडियो, Twitch या Kick रीप्ले, या अपनी MP4 के लिए <b>Upload video</b> दबाएँ। बहुत लंबे वीडियो में आप अपना हिस्सा चुन सकते हैं।'))}
{step(2, t('Press <b>Make clips</b>', '<b>Make clips</b> दबाएँ'), t('BloomClipping downloads, finds the best moments, writes a title and a hook for each, adds captions and renders vertical 9:16 clips. About two minutes for a normal video.', 'BloomClipping डाउनलोड करता है, सबसे अच्छे पल ढूँढता है, हर एक का टाइटल और हुक लिखता है, कैप्शन जोड़ता है और वर्टिकल 9:16 क्लिप बनाता है। आम वीडियो में करीब दो मिनट।'))}
{step(3, t('Watch the progress', 'प्रोग्रेस देखें'), t('The <b>Activity</b> list and the <b>Now making</b> box in the right panel show a bar with a percentage and a short line about what is happening (downloading, reading moments, rendering clip 2 of 3).', '<b>Activity</b> लिस्ट और दाएँ पैनल का <b>Now making</b> बॉक्स प्रतिशत वाली बार और एक छोटी लाइन दिखाते हैं कि क्या हो रहा है (डाउनलोड, पल पढ़ना, क्लिप 2/3 बनाना)।'))}
{step(4, t('Collect your clips', 'अपने क्लिप लें'), t('They appear under the button and in <b>My clips</b>. Each has a score ring, a title and Download / Edit buttons.', 'वो बटन के नीचे और <b>My clips</b> में दिखते हैं। हर एक पर स्कोर रिंग, टाइटल और Download / Edit बटन होते हैं।'))}
{callout('tip', t('Want it to wait?', 'इंतज़ार करवाना है?'), t('Use <b>Add to queue instead</b> under the box. Links in the queue run one after another; you can pause or cancel them.', 'बॉक्स के नीचे <b>Add to queue instead</b> इस्तेमाल करें। क्यू के लिंक एक के बाद एक चलते हैं; आप उन्हें रोक या कैंसल कर सकते हैं।'))}""")
    out.append(f"""<h3>{t('Preview first and frame your moment', 'पहले प्रीव्यू और फ्रेमिंग')}</h3>
<p>{t('Press <b>Get preview</b> instead of Make clips when you want control. Frames arrive first, then you draw the areas. Open <b>Advanced</b> and the <b>Frame &amp; layout</b> tab.', 'कंट्रोल चाहिए तो Make clips की जगह <b>Get preview</b> दबाएँ। पहले फ्रेम आते हैं, फिर आप एरिया बनाते हैं। <b>Advanced</b> खोलकर <b>Frame &amp; layout</b> टैब पर जाएँ।')}</p>
{shot('frame', {'#source': ('Draw the <b>facecam area</b> (pink) and the <b>gameplay area</b> (cyan) on the real frame. BloomClipping also finds the facecam for you.', 'असली फ्रेम पर <b>फेसकैम एरिया</b> (गुलाबी) और <b>गेमप्ले एरिया</b> (सियान) बनाएँ। BloomClipping फेसकैम अपने आप भी ढूँढता है।'),
                '#top': ('How tall the face part is in the vertical clip.', 'वर्टिकल क्लिप में चेहरे वाला हिस्सा कितना ऊँचा हो।')})}
<p>{t('The right side shows <b>your vertical cut</b> live. Eleven layouts are available: face + game, game + face, blurred, fill, game only, four corner cameras, circle camera and side by side.', 'दाईं तरफ <b>आपका वर्टिकल कट</b> लाइव दिखता है। ग्यारह लेआउट हैं: face + game, game + face, blurred, fill, game only, चार कोनों वाले कैमरे, circle camera और side by side।')}</p>""")
    out.append(f"""<h3>{t('Captions and the opening heading', 'कैप्शन और ओपनिंग हेडिंग')}</h3>
<p>{t('Open the <b>Captions &amp; heading</b> tab. Pick a style tile, switch captions on or off, choose the language and write your own opening line. If you leave the language on Auto, Hindi speech becomes Hinglish; English words such as “police” keep their English spelling.', '<b>Captions &amp; heading</b> टैब खोलें। स्टाइल टाइल चुनें, कैप्शन ऑन/ऑफ करें, भाषा चुनें और अपनी ओपनिंग लाइन लिखें। भाषा Auto रखने पर हिंदी बोली Hinglish बनती है; “police” जैसे अंग्रेज़ी शब्द अंग्रेज़ी स्पेलिंग में ही रहते हैं।')}</p>
{shot('captions', {'.caption-styles': ('13 caption styles. The active word is highlighted; Karaoke is the default.', '13 कैप्शन स्टाइल। बोला जा रहा शब्द हाइलाइट होता है; Karaoke डिफ़ॉल्ट है।'),
                   '#captions': ('Burn captions into the clip on or off (off is faster).', 'क्लिप में कैप्शन जलाना ऑन/ऑफ (ऑफ तेज़ है)।'),
                   '#language': ('Language. Auto turns Hindi into Hinglish.', 'भाषा। Auto हिंदी को Hinglish बना देता है।'),
                   '#hook': ('Your own opening heading. Leave it empty and the AI writes one.', 'आपकी अपनी ओपनिंग हेडिंग। खाली छोड़ें तो AI लिख देता है।')})}""")
    out.append(f"""<h3>{t('The Live Preview panel (right side)', 'लाइव प्रीव्यू पैनल (दाईं तरफ)')}</h3>
<p>{t('This panel mirrors the real preview, so what you pick is what you see: caption style, layout and heading drawn on your clip. Open or close it with the small arrow button on the edge.', 'ये पैनल असली प्रीव्यू को दोहराता है, इसलिए जो चुनते हैं वही दिखता है: आपके क्लिप पर कैप्शन स्टाइल, लेआउट और हेडिंग। किनारे के छोटे तीर वाले बटन से इसे खोलें या बंद करें।')}</p>
{shot('live', {'#rb-canvas': ('The live 9:16 preview of your clip, with the chosen caption and heading.', 'आपके क्लिप का लाइव 9:16 प्रीव्यू, चुने हुए कैप्शन और हेडिंग के साथ।'),
               '#rb-make': ('<b>Make clips</b> from here, then watch the bar and the percentage under it.', 'यहीं से <b>Make clips</b>, फिर उसके नीचे बार और प्रतिशत देखें।'),
               '#rb-tabs': ('Four tabs: <b>Caption</b>, <b>Layout</b>, <b>Heading</b> and <b>Output</b> (shape, quality, number of clips).', 'चार टैब: <b>Caption</b>, <b>Layout</b>, <b>Heading</b> और <b>Output</b> (शेप, क्वालिटी, क्लिप की संख्या)।'),
               '.rb-styles': ('Every caption style drawn the way it looks. Press one to use it.', 'हर कैप्शन स्टाइल वैसा ही बना है जैसा दिखता है। चुनने के लिए दबाएँ।')})}""")
    out.append(f"""<h3>{t('My clips: download, edit, delete', 'My clips: डाउनलोड, एडिट, डिलीट')}</h3>
{shot('library', {'#lib-select': ('<b>Select clips</b>: tick many clips and delete them together (you are asked to confirm).', '<b>Select clips</b>: कई क्लिप चुनकर एक साथ डिलीट करें (पहले पुष्टि पूछी जाती है)।'),
                  '.clip-card': ('A finished clip. Play it, then press <b>Download</b> or <b>Edit</b>.', 'तैयार क्लिप। चलाकर देखें, फिर <b>Download</b> या <b>Edit</b> दबाएँ।'),
                  '.clip-card .trash': ('The trash button removes just this clip (and asks first). Download what you want to keep.', 'ट्रैश बटन सिर्फ यही क्लिप हटाता है (पहले पूछता है)। जो रखना है उसे डाउनलोड कर लें।')})}
<p>{t('Deleting cannot be undone. You can also tick <b>Also delete the source videos</b> to free more space.', 'डिलीट वापस नहीं होता। ज़्यादा जगह चाहिए तो <b>Also delete the source videos</b> भी टिक कर सकते हैं।')}</p>""")
    out.append(f"""<h3>{t('The Editor', 'एडिटर')}</h3>
<p>{t('Open the <b>Editor</b> from the sidebar (or press <b>Edit</b> on a clip). It plays your cut live in 9:16, so every change shows at once. Press <b>Export changes</b> when you are happy; the new version replaces the old one.', 'साइडबार से <b>Editor</b> खोलें (या किसी क्लिप पर <b>Edit</b> दबाएँ)। ये आपके कट को लाइव 9:16 में चलाता है, इसलिए हर बदलाव तुरंत दिखता है। संतुष्ट हों तो <b>Export changes</b> दबाएँ; नया वर्ज़न पुराने की जगह ले लेता है।')}</p>
{shot('editor', {'#ed-list': ('All your clips. Pick one to edit; sort by newest or best score.', 'आपके सारे क्लिप। एडिट के लिए एक चुनें; नए या बेस्ट स्कोर से सॉर्ट करें।'),
                 '#ed-stage': ('Live preview. Play with <span class="kbd">Space</span>. Drag the captions up or down right here.', 'लाइव प्रीव्यू। <span class="kbd">Space</span> से चलाएँ। कैप्शन को यहीं ऊपर-नीचे ड्रैग करें।'),
                 '#ed-lane': ('The timeline: thumbnails of your clip. Click to move the playhead; drag a piece edge to trim.', 'टाइमलाइन: आपके क्लिप के थंबनेल। प्लेहेड हिलाने के लिए क्लिक करें; ट्रिम के लिए पीस का किनारा ड्रैग करें।'),
                 '#ed-tabs': ('Tabs: <b>Captions</b>, <b>Framing</b>, <b>Audio</b>, <b>Effects</b>. Every choice is a picture, a colour or a button.', 'टैब: <b>Captions</b>, <b>Framing</b>, <b>Audio</b>, <b>Effects</b>। हर चुनाव एक तस्वीर, रंग या बटन है।'),
                 '#ed-export': ('<b>Export changes</b> renders the new version. Undo / redo are above the preview.', '<b>Export changes</b> नया वर्ज़न बनाता है। Undo / redo प्रीव्यू के ऊपर हैं।')})}""")
    out.append(f"""<h4>{t('Framing: drag the boxes on the real frame', 'फ्रेमिंग: असली फ्रेम पर बॉक्स ड्रैग करें')}</h4>
{shot('editor_frame', {'.ed-lays': ('Layout pictures: press one to switch. The preview changes at once.', 'लेआउट की तस्वीरें: बदलने के लिए एक दबाएँ। प्रीव्यू तुरंत बदलता है।'),
                       '#ed-frame': ('The original frame with a <b>CAM</b> box and a <b>GAME</b> box. Drag a box to move it, drag its corner to resize.', 'ओरिजिनल फ्रेम में एक <b>CAM</b> बॉक्स और एक <b>GAME</b> बॉक्स। बॉक्स हिलाने के लिए ड्रैग करें, साइज़ बदलने के लिए उसका कोना ड्रैग करें।')})}
<h4>{t('Cut your clip: split, remove, duplicate, reorder', 'क्लिप काटें: स्प्लिट, रिमूव, डुप्लिकेट, रीऑर्डर')}</h4>
{shot('editor_split', {'#ed-split': ('<b>Split</b> cuts the clip in two at the playhead (shortcut <span class="kbd">S</span>). Then <b>Remove</b> a piece, <b>Duplicate</b> it, or move it with the arrows.', '<b>Split</b> प्लेहेड पर क्लिप को दो हिस्सों में काटता है (शॉर्टकट <span class="kbd">S</span>)। फिर किसी पीस को <b>Remove</b> करें, <b>Duplicate</b> करें, या तीरों से हिलाएँ।'),
                       '#ed-lane': ('Each piece shows its length. A pink edge appears on the selected piece: drag it to trim.', 'हर पीस पर उसकी लंबाई दिखती है। चुने हुए पीस पर गुलाबी किनारा आता है: उसे ड्रैग करके ट्रिम करें।'),
                       '#ed-capl': ('The caption words along the timeline. Edit or remove a word in the Transcript box below.', 'टाइमलाइन के साथ कैप्शन के शब्द। नीचे Transcript बॉक्स में शब्द बदलें या हटाएँ।')})}
{callout('info', t('Good to know', 'जानने लायक'), t('The preview is a close picture of the result, built from your camera and game boxes. The finished video can differ slightly, so check it after you export. A clip must stay between 3 and 180 seconds. Transcript edits and cutting work on one clip at a time; look changes (style, layout) can be applied to all clips of a video.', 'प्रीव्यू नतीजे की करीबी तस्वीर है, जो आपके कैमरा और गेम बॉक्स से बनती है। तैयार वीडियो थोड़ा अलग हो सकता है, इसलिए एक्सपोर्ट के बाद देख लें। क्लिप 3 से 180 सेकंड के बीच रहना चाहिए। ट्रांसक्रिप्ट एडिट और कटिंग एक बार में एक क्लिप पर चलती है; लुक बदलाव (स्टाइल, लेआउट) एक वीडियो के सभी क्लिप पर लग सकते हैं।'))}
<h4>{t('Export presets', 'एक्सपोर्ट प्रीसेट')}</h4>
<p>{t('In the <b>Framing</b> tab, press <b>YouTube Shorts</b>, <b>TikTok</b> or <b>Instagram Reels</b>. It sets 9:16, 1080p and 30 fps and warns you if the clip is longer than that platform allows (Shorts 180 s, TikTok 600 s, Reels 90 s).', '<b>Framing</b> टैब में <b>YouTube Shorts</b>, <b>TikTok</b> या <b>Instagram Reels</b> दबाएँ। ये 9:16, 1080p और 30 fps सेट करता है और क्लिप उस प्लेटफ़ॉर्म की सीमा से लंबी हो तो चेतावनी देता है (Shorts 180 s, TikTok 600 s, Reels 90 s)।')}</p>""")
    out.append(f"""<h3>{t('Storage: when the disk gets full', 'स्टोरेज: डिस्क भर जाए तो')}</h3>
{shot('storage', {'#storage-dialog .sd-summary': ('How much space BloomClipping uses, how much is free, and how many clips you have.', 'BloomClipping कितनी जगह लेता है, कितनी खाली है, और कितने क्लिप हैं।'),
                  '#storage-dialog [data-clean]': ('Safe clean-ups with the size you will free: temporary files, old live recordings, unused source videos.', 'सुरक्षित सफाई, कितनी जगह मिलेगी उसके साथ: अस्थायी फाइलें, पुरानी लाइव रिकॉर्डिंग, इस्तेमाल न होने वाले सोर्स वीडियो।'),
                  '#sd-open': ('<b>Open folder</b> shows your clips in the file explorer.', '<b>Open folder</b> आपके क्लिप फाइल एक्सप्लोरर में दिखाता है।')})}
<p>{t('Press the <b>Storage</b> card in the sidebar. Nothing is deleted without a question first. You can also choose another drive for BloomClipping’s files (BloomClipping restarts to use it).', 'साइडबार का <b>Storage</b> कार्ड दबाएँ। बिना पूछे कुछ डिलीट नहीं होता। BloomClipping की फाइलों के लिए आप दूसरी ड्राइव भी चुन सकते हैं (उसे इस्तेमाल करने के लिए BloomClipping रीस्टार्ट होता है)।')}</p>""")
    out.append(f"""<h3>{t('Live streams, creators and your phone', 'लाइव स्ट्रीम, क्रिएटर और आपका फोन')}</h3>
<div class="cards">
<div class="card"><b>{t('Live clipping', 'लाइव क्लिपिंग')}</b><small>{t('Open Advanced, then <b>Streams &amp; tools</b>. Paste a Twitch channel or YouTube Live link and press Start. BloomClipping records the stream, watches the chat and cuts a clip around every chat spike.', 'Advanced खोलें, फिर <b>Streams &amp; tools</b>। Twitch चैनल या YouTube Live का लिंक पेस्ट करके Start दबाएँ। BloomClipping स्ट्रीम रिकॉर्ड करता है, चैट देखता है और हर चैट उछाल के आसपास क्लिप काटता है।')}</small></div>
<div class="card"><b>{t('Creators', 'क्रिएटर')}</b><small>{t('Add a streamer in the <b>Creators</b> panel. When they go live, BloomClipping clips them with your layout and caption style. Keep BloomClipping open; it needs 8 GB free disk.', '<b>Creators</b> पैनल में स्ट्रीमर जोड़ें। जब वो लाइव आएँ, BloomClipping आपके लेआउट और कैप्शन स्टाइल से क्लिप बनाता है। BloomClipping खुला रखें; 8 GB खाली डिस्क चाहिए।')}</small></div>
<div class="card"><b>{t('Phone remote', 'फोन रिमोट')}</b><small>{t('Start with the <b>BloomClipping (phone access)</b> shortcut. A Wi-Fi address and a 6-digit PIN appear under Live clipping. Open that address on a phone on the same Wi-Fi and enter the PIN.', '<b>BloomClipping (phone access)</b> शॉर्टकट से शुरू करें। Live clipping के नीचे Wi-Fi पता और 6 अंकों का PIN दिखता है। उसी Wi-Fi पर फोन में वो पता खोलें और PIN डालें।')}</small></div></div>
<h3>{t('Fast, Balanced or Best', 'Fast, Balanced या Best')}</h3>
<p>{t('Under the link box pick a mode. <b>Fast</b> works on every PC and already has most features. <b>Balanced</b> adds the AI spelling fix and lets the AI read the whole talk. <b>Best</b> scans the full video and compares clips twice. Open <b>What runs</b> to switch any single feature on or off (each tile says Light, Medium or Heavy).', 'लिंक बॉक्स के नीचे मोड चुनें। <b>Fast</b> हर PC पर चलता है और इसमें ज़्यादातर फीचर पहले से हैं। <b>Balanced</b> में AI स्पेलिंग ठीक करता है और पूरी बातचीत पढ़ता है। <b>Best</b> पूरा वीडियो स्कैन करता है और क्लिप दो बार मिलाता है। <b>What runs</b> खोलकर कोई भी फीचर अलग से on/off करें (हर टाइल पर Light, Medium या Heavy लिखा है)।')}</p>
<h3>{t('A free AI key makes a slow PC fast', 'फ्री AI की से धीमा PC भी तेज़')}</h3>
<p>{t('Without any AI, clips are still chosen by sound, motion and chat. With <b>Ollama</b> (free, on your PC) or a <b>free online AI key</b>, BloomClipping also writes hooks and titles and picks smarter moments. An online key is the better choice on a slow PC or a laptop: the thinking happens on the provider’s computers. Only the <b>text</b> of a clip is sent; your video and audio stay on your PC.', 'बिना AI के भी क्लिप आवाज़, मूवमेंट और चैट से चुने जाते हैं। <b>Ollama</b> (फ्री, आपके PC पर) या <b>फ्री ऑनलाइन AI की</b> से BloomClipping हुक और टाइटल भी लिखता है और बेहतर पल चुनता है। धीमे PC या लैपटॉप पर ऑनलाइन की बेहतर है: सोचने का काम प्रोवाइडर के कंप्यूटर करते हैं। सिर्फ क्लिप का <b>टेक्स्ट</b> भेजा जाता है; आपका वीडियो और ऑडियो आपके PC पर ही रहता है।')}</p>
<div class="cards">
<div class="card"><b>Groq</b><small>{t('console.groq.com/keys. Free tier, no card, very fast. Daily limits per model (your console shows them).', 'console.groq.com/keys। फ्री टियर, कार्ड नहीं चाहिए, बहुत तेज़। हर मॉडल की रोज़ की लिमिट (कंसोल में दिखती है)।')}</small></div>
<div class="card"><b>Google Gemini</b><small>{t('aistudio.google.com/apikey. Free tier with daily limits; Google changes them often, AI Studio shows yours.', 'aistudio.google.com/apikey। रोज़ की लिमिट के साथ फ्री टियर; Google इन्हें अक्सर बदलता है, AI Studio में आपकी लिमिट दिखती है।')}</small></div>
<div class="card"><b>NVIDIA</b><small>{t('build.nvidia.com. Verify the account to get free trial credits (about 1,000 to start, reported 40 requests a minute).', 'build.nvidia.com। अकाउंट वेरीफाई करने पर फ्री ट्रायल क्रेडिट (शुरू में लगभग 1,000, लगभग 40 रिक्वेस्ट प्रति मिनट)।')}</small></div>
<div class="card"><b>xAI Grok</b><small>{t('console.x.ai. New accounts have received free trial credits; the console shows the current offer.', 'console.x.ai। नए अकाउंट को फ्री ट्रायल क्रेडिट मिलते रहे हैं; कंसोल में मौजूदा ऑफर दिखता है।')}</small></div></div>
{step(1, t('Open Settings', 'Settings खोलें'), t('Left sidebar, <b>⚙ Settings</b>, tab <b>AI key (free)</b>.', 'बाईं साइडबार में <b>⚙ Settings</b>, टैब <b>AI key (free)</b>।'))}
{step(2, t('Pick a provider and get the key', 'प्रोवाइडर चुनें और की लें'), t('Tap Groq or Google Gemini, press <b>Open</b>, sign in, create an API key and copy it.', 'Groq या Google Gemini चुनें, <b>Open</b> दबाएँ, साइन इन करें, API key बनाकर कॉपी करें।'))}
{step(3, t('Paste, then Save and test', 'पेस्ट करें, फिर Save and test'), t('Paste the key, press <b>Find models</b> if the model box is empty, then <b>Save and test</b>. A green tick means every new clip uses it. Free limits reset every day.', 'की पेस्ट करें, मॉडल बॉक्स खाली हो तो <b>Find models</b> दबाएँ, फिर <b>Save and test</b>। हरा टिक मतलब हर नई क्लिप इसका इस्तेमाल करेगी। फ्री लिमिट रोज़ रीसेट होती है।'))}
{callout('tip', t('Phone?', 'फोन?'), t('An online key moves the thinking off your PC, but downloading, cutting and rendering the video still happen on the computer. From a phone you use the <b>phone remote</b> (above) to control the PC on the same Wi-Fi.', 'ऑनलाइन की से सोचने का काम PC से हट जाता है, लेकिन वीडियो डाउनलोड, कटिंग और रेंडर अभी भी कंप्यूटर पर ही होते हैं। फोन से आप <b>फोन रिमोट</b> (ऊपर) से उसी Wi-Fi पर PC को कंट्रोल करते हैं।'))}
<h3>{t('Come back in one click', 'एक क्लिक में वापस आएँ')}</h3>
<p>{t('<b>⚙ Settings → Shortcut</b>: <b>Desktop + Start Menu</b> makes an icon that opens BloomClipping (and starts it if it is closed). <b>Install as an app</b> gives it its own window from Chrome or Edge.', '<b>⚙ Settings → Shortcut</b>: <b>Desktop + Start Menu</b> एक आइकन बनाता है जो BloomClipping खोलता है (और बंद हो तो चालू करता है)। <b>Install as an app</b> से Chrome या Edge में इसकी अपनी विंडो बनती है।')}</p>
<h3>{t('Report a problem, supporters, donate', 'समस्या बताएँ, सपोर्टर, डोनेट')}</h3>
<p>{t('<b>Report a problem</b> (sidebar and bottom corner) writes a clear report you can read before anything is sent. BloomClipping stays free because of supporters; the <b>Supporters</b> list in the sidebar shows them with masked names. The <b>Donate</b> button is optional.', '<b>Report a problem</b> (साइडबार और नीचे के कोने में) एक साफ रिपोर्ट बनाता है जिसे कुछ भी भेजने से पहले आप पढ़ सकते हैं। BloomClipping सपोर्टरों की वजह से फ्री है; साइडबार की <b>Supporters</b> लिस्ट उन्हें छिपे नामों के साथ दिखाती है। <b>Donate</b> बटन ऑप्शनल है।')}</p>""")

    # ================= PART 4: FAQ
    out.append(part('4', t('Questions and fixes', 'सवाल और समाधान'), t('The things people ask most, including the ones you may not think to ask.', 'लोग सबसे ज़्यादा जो पूछते हैं, उनमें वो भी जो आप शायद पूछना न सोचें।')))
    faq = [
        ('Is it really free? Do I need an account?', 'क्या ये सच में फ्री है? क्या अकाउंट चाहिए?', 'Yes, it is free and open-source. There is no account, no credits and no subscription.', 'हाँ, ये फ्री और ओपन-सोर्स है। कोई अकाउंट, क्रेडिट या सब्सक्रिप्शन नहीं।'),
        ('Are my videos uploaded anywhere?', 'क्या मेरे वीडियो कहीं अपलोड होते हैं?', 'No. Downloading, finding moments, captions and rendering all run on your computer. Only the download itself touches the internet, plus the optional Cloud AI if you turn it on yourself.', 'नहीं। डाउनलोड, पल ढूँढना, कैप्शन और रेंडर सब आपके कंप्यूटर पर चलते हैं। सिर्फ डाउनलोड इंटरनेट से होता है, और ऑप्शनल Cloud AI अगर आप खुद ऑन करें।'),
        ('Do I need a graphics card?', 'क्या ग्राफिक्स कार्ड चाहिए?', 'No. An NVIDIA card makes encoding and speech faster, but the CPU works too. Task Manager shows the work under <b>Video Encode</b> and <b>Video Decode</b>, not under 3D, so low “3D” use is normal.', 'नहीं। NVIDIA कार्ड एन्कोडिंग और स्पीच तेज़ करता है, पर CPU से भी चलता है। Task Manager काम को <b>Video Encode</b> और <b>Video Decode</b> में दिखाता है, 3D में नहीं, इसलिए कम “3D” इस्तेमाल सामान्य है।'),
        ('How long does it take?', 'कितना समय लगता है?', 'About two minutes for a normal video in Fast mode. Very long streams stay quick because only the audio is read first; Deep mode is slower but looks at motion too. 4K downloads take longer.', 'आम वीडियो में Fast मोड में करीब दो मिनट। बहुत लंबी स्ट्रीम भी तेज़ रहती हैं क्योंकि पहले सिर्फ ऑडियो पढ़ा जाता है; Deep मोड धीमा है पर मोशन भी देखता है। 4K डाउनलोड में ज़्यादा समय लगता है।'),
        ('How do I get 4K?', '4K कैसे मिलेगा?', 'Pick <b>4K</b> in the <b>Download quality</b> box next to <b>Get preview</b> (or the Output tab of the right panel). The default is 1080p.', '<b>Get preview</b> के बगल वाले <b>Download quality</b> बॉक्स में <b>4K</b> चुनें (या दाएँ पैनल के Output टैब में)। डिफ़ॉल्ट 1080p है।'),
        ('YouTube says “Sign in to confirm you are not a bot”.', 'YouTube कहता है “Sign in to confirm you are not a bot”।', 'Open <b>Advanced → Clip options</b>, find the YouTube login box, choose the browser you are signed in to and save. BloomClipping only reads cookies when you set this. A spare Google account is safer than your main one. Updating also helps, because the downloader (yt-dlp) refreshes itself once a day.', '<b>Advanced → Clip options</b> खोलें, YouTube login बॉक्स में वो ब्राउज़र चुनें जिसमें आप साइन-इन हैं और सेव करें। कुकी तभी पढ़ी जाती हैं जब आप ये सेट करें। अपने मुख्य अकाउंट की जगह एक अतिरिक्त Google अकाउंट सुरक्षित है। अपडेट भी मदद करता है क्योंकि डाउनलोडर (yt-dlp) दिन में एक बार खुद अपडेट होता है।'),
        ('A Twitch or Kick link does not work.', 'Twitch या Kick का लिंक नहीं चल रहा।', 'Use a replay (VOD) or clip link. A stream that is live right now goes into <b>Live clipping</b> instead.', 'रीप्ले (VOD) या क्लिप का लिंक इस्तेमाल करें। जो स्ट्रीम अभी लाइव है उसे <b>Live clipping</b> में डालें।'),
        ('The captions are wrong or a word is misspelled.', 'कैप्शन गलत हैं या किसी शब्द की स्पेलिंग गलत है।', 'Open the clip in the <b>Editor</b>, change or remove the word in the <b>Transcript</b> box and press <b>Export changes</b>. For Hindi you can also choose the slower “Best Hindi” accuracy before making clips.', 'क्लिप को <b>Editor</b> में खोलें, <b>Transcript</b> बॉक्स में शब्द बदलें या हटाएँ और <b>Export changes</b> दबाएँ। हिंदी के लिए क्लिप बनाने से पहले धीमा “Best Hindi” एक्यूरेसी भी चुन सकते हैं।'),
        ('The preview in the Editor looks a little different from the exported clip.', 'एडिटर का प्रीव्यू एक्सपोर्ट किए क्लिप से थोड़ा अलग दिखता है।', 'The preview is a fast picture made in your browser. The final clip is rendered by FFmpeg, so fonts and edges can differ slightly. Check the exported clip in <b>My clips</b>.', 'प्रीव्यू आपके ब्राउज़र में बनी तेज़ तस्वीर है। फाइनल क्लिप FFmpeg से रेंडर होता है, इसलिए फॉन्ट और किनारे थोड़े अलग हो सकते हैं। एक्सपोर्ट किया क्लिप <b>My clips</b> में देखें।'),
        ('My disk is full. What can I delete safely?', 'मेरी डिस्क भर गई। क्या सुरक्षित रूप से हटा सकता हूँ?', 'Press the <b>Storage</b> card. The first three clean-ups (temporary files, live recordings, unused sources) only remove things you can get again. Deleting clips is permanent, so download what you want first. You can also move BloomClipping’s data to a bigger drive there.', '<b>Storage</b> कार्ड दबाएँ। पहली तीन सफाइयाँ (अस्थायी फाइलें, लाइव रिकॉर्डिंग, इस्तेमाल न होने वाले सोर्स) सिर्फ वही हटाती हैं जो दोबारा मिल सकती हैं। क्लिप डिलीट हमेशा के लिए है, इसलिए पहले जो रखना है डाउनलोड कर लें। वहीं से आप डेटा बड़ी ड्राइव पर भी ले जा सकते हैं।'),
        ('The page does not open or says the address is busy.', 'पेज नहीं खुलता या कहता है पता बिज़ी है।', 'Open it from the Desktop shortcut. If another copy is already running, close it first. If port 8770 is taken, BloomClipping uses 8771; or set <code>BLOOMCLIPPING_PORT</code> to any free number.', 'Desktop शॉर्टकट से खोलें। कोई दूसरी कॉपी चल रही हो तो पहले उसे बंद करें। पोर्ट 8770 लिया हुआ हो तो BloomClipping 8771 लेता है; या <code>BLOOMCLIPPING_PORT</code> में कोई भी खाली नंबर डालें।'),
        ('FFmpeg is missing or the status line shows a red mark.', 'FFmpeg नहीं है या स्टेटस लाइन में लाल निशान है।', 'Run <code>BloomClipping-Setup.bat</code> again; it installs what is missing. Mac / Linux: install FFmpeg with your package manager (for example <code>brew install ffmpeg</code>).', '<code>BloomClipping-Setup.bat</code> दोबारा चलाएँ; जो कम है वो इंस्टॉल हो जाता है। Mac / Linux: अपने पैकेज मैनेजर से FFmpeg इंस्टॉल करें (जैसे <code>brew install ffmpeg</code>)।'),
        ('Can I use it from my phone?', 'क्या फोन से इस्तेमाल कर सकता हूँ?', 'Yes, for live clipping. Start with the phone-access shortcut and use the address and PIN it shows. Phone access is off unless you start it that way, and nothing outside your PC works without the PIN.', 'हाँ, लाइव क्लिपिंग के लिए। फोन-एक्सेस शॉर्टकट से शुरू करें और जो पता और PIN दिखे वो इस्तेमाल करें। फोन एक्सेस तभी चालू होता है जब आप उसे ऐसे शुरू करें, और PIN के बिना PC के बाहर कुछ नहीं चलता।'),
        ('Where are my clips saved?', 'मेरे क्लिप कहाँ सेव होते हैं?', 'In the <code>data</code> folder of the BloomClipping folder (on Windows installs: <code>%LOCALAPPDATA%\\BloomClipping</code>). The Storage card has an <b>Open folder</b> button.', 'BloomClipping फोल्डर के <code>data</code> फोल्डर में (Windows इंस्टॉल में: <code>%LOCALAPPDATA%\\BloomClipping</code>)। Storage कार्ड में <b>Open folder</b> बटन है।'),
        ('How do I remove BloomClipping?', 'BloomClipping कैसे हटाऊँ?', 'Close it, copy out any clips you want from <code>data</code>, then delete the BloomClipping folder and the Desktop shortcut.', 'इसे बंद करें, <code>data</code> से जो क्लिप चाहिए कॉपी करें, फिर BloomClipping फोल्डर और Desktop शॉर्टकट डिलीट करें।'),
        ('Something is broken. How do I tell you?', 'कुछ टूट गया है। आपको कैसे बताऊँ?', 'Press <b>Report a problem</b>. It prepares a report you can read first, so you decide what is shared. You can also open an issue on GitHub.', '<b>Report a problem</b> दबाएँ। ये एक रिपोर्ट बनाता है जिसे आप पहले पढ़ सकते हैं, इसलिए क्या शेयर हो ये आप तय करते हैं। आप GitHub पर issue भी खोल सकते हैं।'),
        ('Does the update erase my clips or settings?', 'क्या अपडेट मेरे क्लिप या सेटिंग्स मिटा देता है?', 'No. <code>data</code>, <code>models</code>, your settings and caches are kept. One backup of the replaced program files stays in <code>.update-backup</code>.', 'नहीं। <code>data</code>, <code>models</code>, आपकी सेटिंग्स और कैश बने रहते हैं। बदली गई प्रोग्राम फाइलों का एक बैकअप <code>.update-backup</code> में रहता है।'),
        ('Is there a difference between “Make clips” and “Get preview”?', '“Make clips” और “Get preview” में क्या फर्क है?', '<b>Make clips</b> does everything in one click. <b>Get preview</b> loads frames first so you can set the camera and game areas yourself, then you make the clips.', '<b>Make clips</b> एक क्लिक में सब करता है। <b>Get preview</b> पहले फ्रेम लोड करता है ताकि आप कैमरा और गेम एरिया खुद सेट कर सकें, फिर क्लिप बनाएँ।'),
    ]
    out.append(''.join(qa(t(q, qh), t(a, ah)) for q, qh, a, ah in faq))

    # ================= PART 5: CHEAT SHEET
    out.append(part('5', t('Cheat sheet', 'चीट शीट'), t('Keep this page handy.', 'ये पन्ना पास रखें।')))
    rows = [('Space', 'Play / pause in the Editor', 'एडिटर में चलाएँ / रोकें'), ('S', 'Split the clip at the playhead', 'प्लेहेड पर क्लिप स्प्लिट करें'),
            ('← / →', 'Move the playhead 0.1 s (hold Shift: 1 s)', 'प्लेहेड 0.1 s हिलाएँ (Shift के साथ: 1 s)'), ('Ctrl + Z', 'Undo', 'Undo'), ('Ctrl + Shift + Z or Ctrl + Y', 'Redo', 'Redo'),
            ('Ctrl + F5', 'Hard-refresh after an update', 'अपडेट के बाद हार्ड-रिफ्रेश')]
    out.append(f"<table><tr><th>{t('Key', 'की')}</th><th>{t('What it does', 'क्या करती है')}</th></tr>" + ''.join(f'<tr><td><span class="kbd">{k}</span></td><td>{t(e, h)}</td></tr>' for k, e, h in rows) + '</table>')
    out.append(f"""<h3>{t('Five habits that give better clips', 'बेहतर क्लिप के लिए पाँच आदतें')}</h3>
{step(1, t('Use Get preview for gaming', 'गेमिंग के लिए Get preview इस्तेमाल करें'), t('Check that the CAM and GAME boxes sit where they should.', 'देखें कि CAM और GAME बॉक्स सही जगह हैं।'))}
{step(2, t('Pick the style while you watch the Live Preview', 'Live Preview देखते हुए स्टाइल चुनें'), t('What you see there is what the clip gets.', 'वहाँ जो दिखता है वही क्लिप को मिलता है।'))}
{step(3, t('Write your own opening heading when you can', 'हो सके तो अपनी ओपनिंग हेडिंग लिखें'), t('A short, specific line stops the scroll better than a generic one.', 'छोटी, खास लाइन आम लाइन से बेहतर रोकती है।'))}
{step(4, t('Finish in the Editor', 'एडिटर में पूरा करें'), t('Trim the first second, fix a word, then export once.', 'पहला सेकंड ट्रिम करें, शब्द ठीक करें, फिर एक बार एक्सपोर्ट करें।'))}
{step(5, t('Keep an eye on Storage', 'Storage पर नज़र रखें'), t('Downloaded sources are the biggest files. Clean up after a big session.', 'डाउनलोड किए सोर्स सबसे बड़ी फाइलें हैं। बड़े सेशन के बाद सफाई करें।'))}
<p style="margin-top:8mm;color:#6b6b80">{t('BloomClipping is made by Bloom. Star the project and read the latest guide at', 'BloomClipping अजय के मीणा ने बनाया है। प्रोजेक्ट को स्टार करें और ताज़ा गाइड यहाँ पढ़ें')} <b>{GH}</b>.</p>""")

    font = '"Nirmala UI", "Mangal", "Segoe UI", sans-serif' if hi else '"Segoe UI", "Helvetica Neue", Arial, sans-serif'
    return f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>BloomClipping {t("Guide", "गाइड")}</title><style>{CSS % {"font": font}}</style></head><body>{"".join(out)}</body></html>'


def main():
    names = {'en': 'BloomClipping-Guide-English', 'hi': 'BloomClipping-Guide-Hindi'}
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        for lang, name in names.items():
            page = HERE / f'_{lang}.html'
            page.write_text(build(lang), encoding='utf-8')
            pg = br.new_page()
            pg.goto(page.as_uri())
            pg.wait_for_timeout(1500)
            footer = ('<div style="width:100%;font-size:8px;color:#8a8a9a;padding:0 13mm;display:flex;justify-content:space-between;font-family:Segoe UI,Nirmala UI,sans-serif">'
                      f'<span>BloomClipping · {GH}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
            pg.pdf(path=str(DOCS / (name + '.pdf')), format='A4', print_background=True, display_header_footer=True, header_template='<div></div>', footer_template=footer,
                   margin={'top': '14mm', 'bottom': '16mm', 'left': '13mm', 'right': '13mm'})
            pg.close()
            page.unlink()
            print('wrote', DOCS / (name + '.pdf'))
        br.close()


if __name__ == '__main__':
    sys.exit(main())
