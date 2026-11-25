// "Report a problem" (English + Hindi). Everything here is user-triggered; see report.py for what is removed from the text.
(() => {
  const css = `
  #rp-btn{position:fixed;right:14px;bottom:14px;z-index:60;background:var(--panel,#171320);color:var(--white,#fbf6ff);border:1px solid var(--line,#30263e);border-radius:999px;padding:9px 14px;font:600 13px system-ui,sans-serif;cursor:pointer;box-shadow:0 4px 18px #0008}
  #rp-btn:hover{border-color:var(--pink,#ff4ba5)}
  #rp-dlg{width:min(720px,94vw);max-height:90vh;overflow:auto;background:var(--panel,#171320);color:var(--white,#fbf6ff);border:1px solid var(--pink,#ff4ba5);border-radius:16px;padding:20px 22px;font:14px/1.5 system-ui,sans-serif}
  #rp-dlg::backdrop{background:#000a}
  #rp-dlg h2{margin:0 0 4px;font-size:20px}
  #rp-dlg .rp-hi{color:var(--cyan,#58e8f7)}
  #rp-dlg .rp-card{border:1px solid var(--line,#30263e);border-radius:12px;padding:12px 14px;margin:10px 0}
  #rp-dlg .rp-card b{display:block;margin-bottom:2px}
  #rp-dlg .rp-safe{border-color:var(--lime,#d4fb58)}
  #rp-dlg p{margin:4px 0;color:var(--muted,#a99db7)}
  #rp-dlg textarea{width:100%;box-sizing:border-box;background:#0b0912;color:var(--white,#fbf6ff);border:1px solid var(--line,#30263e);border-radius:8px;padding:8px;font:12px/1.4 ui-monospace,Consolas,monospace}
  #rp-dlg button,#rp-dlg a.rp-a{background:var(--pink,#ff4ba5);color:#14081a;border:0;border-radius:8px;padding:8px 14px;font:700 13px system-ui,sans-serif;cursor:pointer;text-decoration:none;display:inline-block;margin-top:6px}
  #rp-dlg button[disabled]{opacity:.4;cursor:not-allowed}
  #rp-dlg .rp-x{background:transparent;color:var(--muted,#a99db7);border:1px solid var(--line,#30263e)}
  #rp-dlg label.rp-c{display:flex;gap:8px;align-items:flex-start;margin-top:6px;color:var(--white,#fbf6ff)}
  #rp-msg{margin-top:6px;color:var(--lime,#d4fb58)}`;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  const el = (tag, props = {}, ...kids) => {
    const n = Object.assign(document.createElement(tag), props);
    kids.forEach(k => n.append(k)); return n;
  };
  const en = t => el('p', { textContent: t });
  const hi = t => el('p', { textContent: t, className: 'rp-hi', lang: 'hi' });

  const btn = el('button', { id: 'rp-btn', type: 'button', textContent: '⚑ Report a problem · समस्या बताएँ' });
  const dlg = el('dialog', { id: 'rp-dlg' });
  const note = el('textarea', { rows: 2, placeholder: 'What went wrong? / क्या दिक्कत आई? (optional)' });
  const diag = el('textarea', { rows: 9, readOnly: true });
  const consent = el('input', { type: 'checkbox', id: 'rp-consent' });
  const sendBtn = el('button', { type: 'button', textContent: 'Send directly · सीधे भेजें', disabled: true });
  const issueA = el('a', { className: 'rp-a', target: '_blank', rel: 'noopener', textContent: 'Open GitHub issue · GitHub पर बताएँ' });
  const dlA = el('a', { className: 'rp-a', textContent: 'Download diagnostics · फ़ाइल डाउनलोड करें' });
  const msg = el('div', { id: 'rp-msg' });
  let canSend = false, timer = 0;

  const card = (cls, title, titleHi, ...body) => el('div', { className: 'rp-card ' + cls },
    el('b', { textContent: title }), el('b', { textContent: titleHi, className: 'rp-hi', lang: 'hi' }), ...body);

  const ghCard = card('rp-safe', 'GitHub issue (optional)', 'GitHub पर रिपोर्ट (वैकल्पिक)',
      en('Only shown when a BloomClipping issues repo is configured. Never opens the upstream NeonClipping project.'),
      hi('सिर्फ़ तब दिखता है जब BloomClipping का अपना issues repo सेट हो। NeonClipping पर नहीं खुलता।'),
      issueA);
  ghCard.hidden = true;

  dlg.append(
    el('h2', { textContent: 'Report a problem · समस्या की रिपोर्ट' }),
    en('Something broke? Download the diagnostics file and share it yourself. Nothing is sent unless you press a button.'),
    hi('कुछ ठीक से नहीं चला? डायग्नोस्टिक फ़ाइल डाउनलोड करें और खुद शेयर करें। बटन दबाए बिना कुछ नहीं भेजा जाता।'),
    note,
    card('rp-safe', '1 · Download diagnostics (recommended)', '1 · डायग्नोस्टिक फ़ाइल डाउनलोड करें (सुझाया गया)',
      en('Saves a redacted text file on your computer. Share it however you like. Your log stays local until you send it.'),
      hi('एक सुरक्षित टेक्स्ट फ़ाइल सेव होती है। जब तक आप शेयर नहीं करते, लॉग आपके कंप्यूटर पर ही रहता है।'),
      dlA),
    ghCard,
    card('', '2 · Send directly (optional)', '2 · सीधे भेजें (वैकल्पिक)',
      en('Only if a report collector is configured. Technical details only — no videos, no personal links.'),
      hi('सिर्फ़ अगर collector सेट हो। सिर्फ़ तकनीकी जानकारी — कोई वीडियो या निजी लिंक नहीं।'),
      diag,
      el('label', { className: 'rp-c' }, consent, el('span', { textContent: 'I have read this text and allow sending it. / मैंने यह टेक्स्ट पढ़ लिया है और भेजने की अनुमति देता/देती हूँ।' })),
      sendBtn, msg),
    el('button', { className: 'rp-x', type: 'button', textContent: 'Close · बंद करें', onclick: () => dlg.close() }));
  document.body.append(btn, dlg);

  const refresh = async () => {
    try {
      const r = await fetch('/report/info?note=' + encodeURIComponent(note.value));
      const j = await r.json();
      diag.value = j.diagnostics;
      const url = (j.issue_url || '').trim();
      const okGh = url.startsWith('https://github.com/') && !/neonclipping|iamajmeena/i.test(url);
      ghCard.hidden = !okGh;
      issueA.href = okGh ? url : '#';
      issueA.style.pointerEvents = okGh ? '' : 'none';
      dlA.href = '/report/download?note=' + encodeURIComponent(note.value); dlA.download = 'bloomclipping-diagnostics.txt';
      canSend = !!j.can_send;
      if (!canSend) msg.textContent = 'Direct sending is not set up. Use Download diagnostics. / सीधा भेजना चालू नहीं है — डायग्नोस्टिक डाउनलोड करें।';
      sendBtn.disabled = !(consent.checked && canSend);
    } catch (e) { diag.value = 'Could not read diagnostics: ' + e.message; }
  };
  btn.onclick = () => { msg.textContent = ''; dlg.showModal(); refresh(); };
  note.oninput = () => { clearTimeout(timer); timer = setTimeout(refresh, 400); };
  consent.onchange = () => { sendBtn.disabled = !(consent.checked && canSend); };
  sendBtn.onclick = async () => {
    sendBtn.disabled = true; msg.textContent = '…';
    try {
      const r = await fetch('/report/send', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ consent: consent.checked, note: note.value }) });
      const j = await r.json();
      msg.textContent = j.message || j.detail || 'Done';
    } catch (e) { msg.textContent = 'Could not send: ' + e.message; }
    sendBtn.disabled = !(consent.checked && canSend);
  };

  // Errors the page itself catches are written to the local log (server removes links/paths). Never loops on its own failures.
  let logging = false;
  const logErr = (stage, error) => {
    if (logging) return; logging = true;
    fetch('/report/log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ stage, error: String(error).slice(0, 600) }) })
      .catch(() => {}).finally(() => { logging = false; });
  };
  addEventListener('unhandledrejection', e => logErr('page', (e.reason && e.reason.message) || e.reason));
  addEventListener('error', e => logErr('page', e.message));
})();
