// ── DOM refs ──────────────────────────────────────────────────────────────────
const chat    = document.getElementById('chat');
const widgets = document.getElementById('widgets');
const logOut  = document.getElementById('log-output');
const connEl  = document.getElementById('conn-status');
const processesList = document.getElementById('processes-list');

// ── i18n ──────────────────────────────────────────────────────────────────────
const TRANSLATIONS = {
  pl:{ chat:'💬 Chat', processes:'⚙️ Procesy', logs:'📋 Logi', copy:'📋 Kopiuj',
       connecting:'Łączenie...', connected:'Połączono', disconnected:'Rozłączono', sub:'Kreator konfiguracji' },
  en:{ chat:'💬 Chat', processes:'⚙️ Processes', logs:'📋 Logs', copy:'📋 Copy',
       connecting:'Connecting...', connected:'Connected', disconnected:'Disconnected', sub:'Setup Wizard' },
  de:{ chat:'💬 Chat', processes:'⚙️ Prozesse', logs:'📋 Protokolle', copy:'📋 Kopieren',
       connecting:'Verbinde...', connected:'Verbunden', disconnected:'Getrennt', sub:'Einrichtungsassistent' },
  fr:{ chat:'💬 Chat', processes:'⚙️ Processus', logs:'📋 Journaux', copy:'📋 Copier',
       connecting:'Connexion...', connected:'Connecté', disconnected:'Déconnecté', sub:'Assistant de configuration' },
  es:{ chat:'💬 Chat', processes:'⚙️ Procesos', logs:'📋 Registros', copy:'📋 Copiar',
       connecting:'Conectando...', connected:'Conectado', disconnected:'Desconectado', sub:'Asistente de configuración' },
  it:{ chat:'💬 Chat', processes:'⚙️ Processi', logs:'📋 Log', copy:'📋 Copia',
       connecting:'Connessione...', connected:'Connesso', disconnected:'Disconnesso', sub:'Procedura guidata' },
  pt:{ chat:'💬 Chat', processes:'⚙️ Processos', logs:'📋 Registos', copy:'📋 Copiar',
       connecting:'A ligar...', connected:'Ligado', disconnected:'Desligado', sub:'Assistente de configuração' },
  cs:{ chat:'💬 Chat', processes:'⚙️ Procesy', logs:'📋 Logy', copy:'📋 Kopírovat',
       connecting:'Připojování...', connected:'Připojeno', disconnected:'Odpojeno', sub:'Průvodce nastavením' },
  ro:{ chat:'💬 Chat', processes:'⚙️ Procese', logs:'📋 Jurnale', copy:'📋 Copiați',
       connecting:'Se conectează...', connected:'Conectat', disconnected:'Deconectat', sub:'Expert configurare' },
  nl:{ chat:'💬 Chat', processes:'⚙️ Processen', logs:'📋 Logboek', copy:'📋 Kopiëren',
       connecting:'Verbinden...', connected:'Verbonden', disconnected:'Verbroken', sub:'Installatiewizard' },
};
let _lang = localStorage.getItem('wizard_lang') || 'pl';
function t(k){ return (TRANSLATIONS[_lang]||TRANSLATIONS.pl)[k]||k; }
function applyLang(){
  document.documentElement.lang = _lang;
  const sel = document.getElementById('lang-select'); if(sel) sel.value = _lang;
  const sub = document.querySelector('.sub'); if(sub) sub.textContent = t('sub');
  const ch = document.querySelector('.chat-header span'); if(ch) ch.textContent = t('chat');
  const cpChat = document.getElementById('copy-chat'); if(cpChat) cpChat.textContent = t('copy');
  const prSpan = document.querySelector('.processes-panel h3 span'); if(prSpan) prSpan.textContent = t('processes');
  const cpProc = document.querySelector('.processes-panel h3 .copy-btn'); if(cpProc) cpProc.textContent = t('copy');
  const logH = document.querySelector('.log-panel h3'); if(logH) logH.firstChild.textContent = t('logs')+' ';
}
document.getElementById('lang-select').addEventListener('change', e => {
  _lang = e.target.value; localStorage.setItem('wizard_lang', _lang); applyLang();
});
applyLang();

// ── Socket ────────────────────────────────────────────────────────────────────
const socket = io({transports:['websocket','polling']});

socket.on('connect',    () => { connEl._state='connected';    connEl.textContent = t('connected'); loadLogs(); });
socket.on('disconnect', () => { connEl._state='disconnected'; connEl.textContent = t('disconnected'); });

// ── Markdown-lite renderer ────────────────────────────────────────────────────
function renderMd(text){
  // 1. Fenced code blocks  ```lang\n...\n```
  text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const escaped = code.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    return `<pre class="md-code"${lang?' data-lang="'+lang+'"':''}><code>${escaped.trimEnd()}</code></pre>`;
  });
  // 2. Block-level elements (must come before inline replacements)
  text = text
    .replace(/^# (.+)$/gm,   '<h1>$1</h1>')
    .replace(/^## (.+)$/gm,  '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^---+$/gm,     '<hr>');
  // 3. Inline elements
  text = text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,     '<em>$1</em>')
    .replace(/`([^`\n]+)`/g,   '<code>$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, (_, label, value) =>
      `<button class="inline-action" data-action="${value.replace(/"/g,'&quot;')}">${label}</button>`);
  // 4. Newlines — but not inside <pre> blocks
  const parts = text.split(/(<pre[\s\S]*?<\/pre>)/);
  text = parts.map((p, i) => i % 2 === 1 ? p : p.replace(/\n/g, '<br>')).join('');
  return text;
}

// Delegate inline-action clicks inside chat bubbles
chat.addEventListener('click', e => {
  const btn = e.target.closest('.inline-action');
  if(!btn) return;
  const value = btn.dataset.action;
  if(!value) return;
  const div = document.createElement('div');
  div.className = 'msg user';
  div.innerHTML = '<div class="avatar">\ud83d\udc64</div><div class="bubble">'+btn.textContent+'</div>';
  chat.appendChild(div); chat.scrollTop = chat.scrollHeight;
  socket.emit('action', {value, form: {}});
});

// ── Load logs from history ────────────────────────────────────────────────────
let _logTotal = 0;
function _appendLogLine(text) {
  if (!logOut || !text) return;
  const cls = typeof classifyLogLine === 'function' ? classifyLogLine(text) : '';
  const l = document.createElement('div');
  l.className = 'log-line' + (cls ? ' ' + cls : '');
  if (cls !== 'log-dim' && typeof highlightLogText === 'function') {
    l.innerHTML = highlightLogText(text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'));
  } else {
    l.textContent = text;
  }
  logOut.appendChild(l);
  while(logOut.children.length > 800) logOut.removeChild(logOut.firstChild);
  logOut.scrollTop = logOut.scrollHeight;
}
async function loadLogs() {
  if (!logOut) return;
  try {
    // Ask server how many new lines since our last fetch
    const want = _logTotal === 0 ? 200 : 50;
    const r = await fetch(`/api/logs/tail?n=${want}`);
    const d = await r.json();
    const total = d.total || 0;
    const lines = d.lines || [];
    if (total > _logTotal) {
      // How many new lines arrived since last poll
      const newCount = total - _logTotal;
      // Take last newCount lines from the returned batch
      const newLines = lines.slice(Math.max(0, lines.length - newCount));
      newLines.forEach(entry => {
        const text = typeof entry === 'string' ? entry : (entry.text || '');
        _appendLogLine(text);
      });
    }
    _logTotal = total;
  } catch(e) { /* ignore */ }
}
// Poll logs every 2s — reliable fallback for missed SocketIO events
setInterval(loadLogs, 2000);

// ── Ticket card renderer ──────────────────────────────────────────────────────
function tryRenderTickets(text) {
  // Match format_ticket output: "  ○ T-0001   🟡 Title → developer"
  // Also match: "○ T-0001 — Title" (legacy/inline format)
  const ticketRe = /([○◐◑●])\s+(T-\d{4,})\s+[🔴🟠🟡🟢⚪]?\s*(.+?)\s*(?:→\s*\w+)?$/gm;
  const tickets = [];
  let m;
  while ((m = ticketRe.exec(text)) !== null) {
    const title = m[3].replace(/→\s*\S+$/, '').trim();
    if (title) tickets.push({ icon: m[1], id: m[2], title });
  }
  // Also try legacy dash format: T-0001 — Title
  if (tickets.length === 0) {
    const legacyRe = /([○◐●]?)\s*(T-\d+)\s*[—\-]+\s*(.+)/g;
    while ((m = legacyRe.exec(text)) !== null) {
      tickets.push({ icon: m[1]||'○', id: m[2], title: m[3].trim() });
    }
  }
  if (tickets.length === 0) return null;
  const wrap = document.createElement('div');
  wrap.className = 'ticket-cards';
  tickets.forEach(tk => {
    const statusMap = {'○':'open','◐':'in_progress','◑':'review','●':'closed'};
    const status = statusMap[tk.icon] || 'open';
    const colorMap = {'open':'var(--accent)','in_progress':'var(--yellow)','review':'var(--cyan, #0ff)','closed':'var(--muted)'};
    const card = document.createElement('div');
    card.className = 'ticket-card';
    // Context-sensitive buttons based on status
    let actionsHtml = '';
    if (status === 'open') {
      actionsHtml = `
        <button class="ticket-btn" data-action="ssh_cmd::developer::ticket-work::${tk.id}" title="Uruchom pełny pipeline">▶ Pracuj</button>
        <button class="ticket-btn" data-action="show_ticket::${tk.id}" title="Szczegóły">👁️</button>`;
    } else if (status === 'in_progress') {
      actionsHtml = `
        <button class="ticket-btn" data-action="ssh_cmd::developer::ticket-work::${tk.id}" title="Kontynuuj pipeline">▶ Pracuj</button>
        <button class="ticket-btn" data-action="ssh_cmd::developer::implement::${tk.id}" title="AI implementacja">🤖</button>
        <button class="ticket-btn ticket-btn-diff" data-action="show_diff::${tk.id}" title="Pokaż diff kodu">📄 Diff</button>
        <button class="ticket-btn" data-action="show_ticket::${tk.id}" title="Szczegóły">👁️</button>`;
    } else if (status === 'review') {
      actionsHtml = `
        <button class="ticket-btn ticket-btn-done" data-action="manager_approve::${tk.id}" title="Zatwierdź">✅ Approve</button>
        <button class="ticket-btn" data-action="manager_reject::${tk.id}" title="Odrzuć">🔄 Reject</button>
        <button class="ticket-btn ticket-btn-diff" data-action="show_diff::${tk.id}" title="Pokaż diff kodu">📄 Diff</button>
        <button class="ticket-btn" data-action="show_ticket::${tk.id}" title="Szczegóły">👁️</button>`;
    } else {
      actionsHtml = `
        <button class="ticket-btn" data-action="show_ticket::${tk.id}" title="Szczegóły">👁️</button>
        <button class="ticket-btn ticket-btn-diff" data-action="show_diff::${tk.id}" title="Pokaż diff kodu">📄 Diff</button>
        <button class="ticket-btn" data-action="ssh_cmd::developer::ticket-work::${tk.id}" title="Otwórz ponownie">🔄 Reopen</button>`;
    }
    card.innerHTML = `
      <div class="ticket-card-header">
        <span class="ticket-id" style="color:${colorMap[status]}">${tk.icon} ${tk.id}</span>
        <span class="ticket-status">${status.replace('_',' ')}</span>
      </div>
      <div class="ticket-title">${tk.title}</div>
      <div class="ticket-actions">${actionsHtml}</div>`;
    wrap.appendChild(card);
  });
  // Async: fetch diff change counts for each ticket's diff button
  tickets.forEach(tk => {
    if (tk.icon === '○') return; // skip open tickets
    fetch(`/api/ticket-diff/${encodeURIComponent(tk.id)}`).then(r=>r.json()).then(d => {
      const count = (d.commits||[]).length;
      wrap.querySelectorAll(`.ticket-btn-diff[data-action="show_diff::${tk.id}"]`).forEach(btn => {
        btn.textContent = count > 0 ? `📄 ${count}` : '📄 0';
        if (count > 0) btn.classList.add('has-changes');
      });
    }).catch(() => {});
  });
  return wrap;
}

// ── Strip MOTD / box-drawing banners from command output ──────────────────────
function stripMotd(text) {
  const BOX_CHARS = /[\s╔╗╚╝╠╣║═─━│┌┐└┘├┤┬┴┼▀▄█▌▐░▒▓]/g;
  const lines = text.split('\n');
  const keep = [];
  let inBox = false;
  for (const l of lines) {
    const t = l.trim();
    // Detect box start (╔═══...═══╗ or ┌───...───┐)
    if (!inBox && /^[╔┌]/.test(t)) { inBox = true; continue; }
    // Detect box end (╚═══...═══╝ or └───...───┘)
    if (inBox && /^[╚└]/.test(t)) { inBox = false; continue; }
    // Skip all lines inside a detected box
    if (inBox) continue;
    // Skip orphaned box-side lines (║ ... ║ or ╠ ... ╣) regardless of box state
    if (/^[║╠╣│]/.test(t)) continue;
    // Skip purely decorative lines (only box-drawing chars)
    if (t.length > 0 && t.replace(BOX_CHARS, '').length === 0) continue;
    keep.push(l);
  }
  // Collapse runs of 3+ blank lines into 2
  const result = keep.join('\n').replace(/\n{3,}/g, '\n\n');
  return result.trim();
}

// ── Messages ──────────────────────────────────────────────────────────────────
socket.on('message', d => {
  if (d.id && document.querySelector(`[data-msg-id="${d.id}"]`)) return;
  const div = document.createElement('div');
  div.className = `msg ${d.role}`;
  if (d.id) div.setAttribute('data-msg-id', d.id);
  const text = d.role === 'bot' ? stripMotd(d.text) : d.text;
  const srcBadge = d.src === 'cli' ? '<span class="cli-badge" title="CLI shell">💻</span>' : '';
  // Try to render ticket cards for my-tickets output
  const ticketCards = d.role === 'bot' ? tryRenderTickets(text) : null;
  if (ticketCards) {
    div.innerHTML = `<div class="avatar">🤖</div><div class="bubble">${srcBadge}</div><div class="msg-copy" onclick="copyMessage(this)" title="Copy message">📋</div>`;
    div.querySelector('.bubble').appendChild(ticketCards);
  } else {
    div.innerHTML = `
      <div class="avatar">${d.role==='bot'?'🤖':'👤'}</div>
      <div class="bubble">${srcBadge}${renderMd(text)}</div>
      <div class="msg-copy" onclick="copyMessage(this)" title="Copy message">📋</div>`;
  }
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
});

// Delegate ticket card button clicks (in chat bubbles)
chat.addEventListener('click', e => {
  const btn = e.target.closest('.ticket-btn');
  if (!btn) return;
  const value = btn.dataset.action;
  if (!value) return;
  if (value.startsWith('show_ticket::')) {
    openDiffModal(value.split('::')[1]);
    return;
  }
  if (value.startsWith('show_diff::')) {
    openDiffModal(value.split('::')[1], true);
    return;
  }
  const card = btn.closest('.ticket-card');
  const tidEl = card && card.querySelector('.ticket-id');
  const label = (tidEl ? tidEl.textContent + ' — ' : '') + btn.textContent.trim();
  sendAction(value, label);
});

// Auto-refresh Stats tab when a ticket is created/updated
socket.on('message', d => {
  if (d.role === 'bot' && d.text && /Ticket (utworzony|zaktualizowany|zamknięty)/i.test(d.text)) {
    setTimeout(updateStats, 800);
  }
});

function copyMessage(button) {
  const bubble = button.closest('.msg').querySelector('.bubble');
  const text = bubble.textContent || bubble.innerText;
  navigator.clipboard.writeText(text).then(() => {
    const orig = button.textContent;
    button.textContent = '✅';
    button.style.background = 'var(--accent)';
    button.style.color = '#fff';
    setTimeout(() => { button.textContent = orig; button.style.background=''; button.style.color=''; }, 1500);
  }).catch(err => console.error('Failed to copy message:', err));
}

// ── Widgets ───────────────────────────────────────────────────────────────────
socket.on('clear_widgets', () => { widgets.innerHTML = ''; });

socket.on('widget', d => {
  if (d.type === 'buttons')         renderButtons(d);
  else if (d.type === 'input')      renderInput(d);
  else if (d.type === 'select')     renderSelect(d);
  else if (d.type === 'code')       renderCode(d);
  else if (d.type === 'status_row') renderStatus(d);
  else if (d.type === 'progress')   renderProgress(d);
  else if (d.type === 'action_grid') renderActionGrid(d);
});

function collectForm(){
  const form = {};
  widgets.querySelectorAll('input[data-name]').forEach(el => { form[el.dataset.name] = el.value; });
  widgets.querySelectorAll('select[data-name]').forEach(el => { form[el.dataset.name] = el.value; });
  return form;
}

function sendAction(value, label){
  const form = collectForm();
  const div = document.createElement('div');
  div.className = 'msg user';
  const display = label || value.replace(/^[^:]+::/,'');
  div.innerHTML = `<div class="avatar">👤</div><div class="bubble">${display}</div>`;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  socket.emit('action', {value, form});
}

function buildParamWidget(cmd, onRun){
  if(!cmd.params || cmd.params.length === 0) return null;
  const wrap = document.createElement('div');
  wrap.className = 'action-card-param';

  if(!cmd.options_endpoint){
    const inp = document.createElement('input');
    inp.type = 'text'; inp.className = 'action-card-input';
    inp.placeholder = cmd.placeholder || cmd.params.join(', ');
    inp.title = cmd.hint || '';
    inp.addEventListener('keydown', e => { if(e.key==='Enter'){ e.preventDefault(); onRun(); }});
    wrap.appendChild(inp);
    wrap._getValue = () => inp.value.trim();
    wrap._markRequired = () => { inp.focus(); inp.classList.add('input-required'); setTimeout(()=>inp.classList.remove('input-required'),1200); };
    return wrap;
  }

  // Async select
  const sel = document.createElement('select');
  sel.className = 'action-card-select';
  const loadOpt = document.createElement('option');
  loadOpt.value = ''; loadOpt.textContent = '⏳ Ładowanie…'; loadOpt.disabled = true; loadOpt.selected = true;
  sel.appendChild(loadOpt);

  const customInp = document.createElement('input');
  customInp.type = 'text'; customInp.className = 'action-card-input action-card-custom';
  customInp.placeholder = cmd.placeholder || cmd.params.join(', ');
  customInp.style.display = 'none';
  customInp.addEventListener('keydown', e => { if(e.key==='Enter'){ e.preventDefault(); onRun(); }});

  sel.addEventListener('change', () => {
    const isCustom = sel.value === '__custom__';
    customInp.style.display = isCustom ? '' : 'none';
    if(isCustom) customInp.focus();
  });

  wrap.appendChild(sel);
  wrap.appendChild(customInp);
  wrap._getValue = () => sel.value === '__custom__' ? customInp.value.trim() : sel.value;
  wrap._markRequired = () => {
    const el = sel.value === '__custom__' ? customInp : sel;
    el.classList.add('input-required');
    setTimeout(()=>el.classList.remove('input-required'),1200);
  };

  fetch(cmd.options_endpoint)
    .then(r => r.json())
    .then(d => {
      sel.innerHTML = '';
      if(!d.options || d.options.length === 0){
        sel.style.display = 'none'; customInp.style.display = '';
        wrap._getValue = () => customInp.value.trim();
        wrap._markRequired = () => { customInp.focus(); customInp.classList.add('input-required'); setTimeout(()=>customInp.classList.remove('input-required'),1200); };
        return;
      }
      const placeholder = document.createElement('option');
      placeholder.value = ''; placeholder.textContent = `— wybierz ${cmd.params[0]} —`; placeholder.disabled = true; placeholder.selected = true;
      sel.appendChild(placeholder);
      d.options.forEach(o => {
        const opt = document.createElement('option');
        opt.value = o.value; opt.textContent = o.label;
        sel.appendChild(opt);
      });
      const customOpt = document.createElement('option');
      customOpt.value = '__custom__'; customOpt.textContent = '✏️ Wpisz ręcznie…';
      sel.appendChild(customOpt);
    })
    .catch(() => {
      sel.style.display = 'none'; customInp.style.display = '';
      wrap._getValue = () => customInp.value.trim();
      wrap._markRequired = () => { customInp.focus(); customInp.classList.add('input-required'); setTimeout(()=>customInp.classList.remove('input-required'),1200); };
    });

  return wrap;
}

function renderActionGrid(d){
  const existing = widgets.querySelector('.w-action-grid');
  if(existing) existing.remove();
  const grid = document.createElement('div');
  grid.className = 'w-action-grid';
  if(d.label){ const lbl=document.createElement('div'); lbl.className='w-action-grid-label'; lbl.textContent=d.label; grid.appendChild(lbl); }
  d.commands.forEach(cmd => {
    const card = document.createElement('div');
    card.className = cmd.tty ? 'action-card action-card-tty' : 'action-card';
    const info = document.createElement('div');
    info.className = 'action-card-info';
    info.innerHTML = `<span class="action-card-cmd">${cmd.cmd}</span><span class="action-card-desc">${cmd.desc}</span>`;
    card.appendChild(info);

    const runBtn = document.createElement('button');
    runBtn.className = 'btn action-card-run';
    runBtn.textContent = '\u25b6';
    runBtn.title = cmd.desc;

    if(cmd.tty){
      const hint = document.createElement('span');
      hint.className = 'action-card-tty-hint';
      hint.textContent = '\ud83d\udda5\ufe0f';
      hint.title = 'Wymaga terminala SSH';
      card.appendChild(hint);
      runBtn.onclick = () => {
        const div = document.createElement('div');
        div.className = 'msg user';
        div.innerHTML = `<div class="avatar">\ud83d\udc64</div><div class="bubble">${cmd.cmd}</div>`;
        chat.appendChild(div); chat.scrollTop = chat.scrollHeight;
        socket.emit('action', {value: d.run_value, form: {ssh_cmd: cmd.cmd, ssh_arg: ''}});
      };
      card.appendChild(runBtn);
    } else {
      function runCard(){
        const arg = paramWidget ? paramWidget._getValue() : '';
        if(cmd.params && cmd.params.length > 0 && !arg){
          if(paramWidget) paramWidget._markRequired();
          return;
        }
        const display = arg ? `${cmd.cmd} ${arg}` : cmd.cmd;
        const div = document.createElement('div');
        div.className = 'msg user';
        div.innerHTML = `<div class="avatar">\ud83d\udc64</div><div class="bubble">${display}</div>`;
        chat.appendChild(div); chat.scrollTop = chat.scrollHeight;
        socket.emit('action', {value: d.run_value, form: {ssh_cmd: cmd.cmd, ssh_arg: arg}});
      }
      const paramWidget = buildParamWidget(cmd, runCard);
      if(paramWidget) card.appendChild(paramWidget);
      runBtn.onclick = runCard;
      card.appendChild(runBtn);
    }
    grid.appendChild(card);
  });
  widgets.appendChild(grid);
}

function renderButtons(d){
  const existing = widgets.querySelector('.w-buttons');
  if(existing) existing.remove();
  const wrap = document.createElement('div');
  wrap.className = 'w-buttons';
  if(d.label){ const l=document.createElement('div'); l.style.cssText='width:100%;color:var(--muted);font-size:.8rem;margin-bottom:4px'; l.textContent=d.label; wrap.appendChild(l); }
  d.items.forEach(item => {
    const b = document.createElement('button');
    b.className = 'btn';
    b.textContent = item.label;
    b.onclick = () => sendAction(item.value, item.label);
    wrap.appendChild(b);
  });
  widgets.appendChild(wrap);
}

// Group consecutive input/select widgets into a single form block
let _formBuf = null;
let _formTimer = null;

function flushForm(){
  if(!_formBuf) return;
  widgets.appendChild(_formBuf);
  _formBuf = null; _formTimer = null;
}

function getOrCreateForm(){
  if(!_formBuf){
    _formBuf = document.createElement('div');
    _formBuf.className = 'w-form';
  }
  clearTimeout(_formTimer);
  _formTimer = setTimeout(flushForm, 80);
  return _formBuf;
}

function buildFieldLabel(d, targetEl){
  const row = document.createElement('div');
  row.className = 'field-label-row';
  const lbl = document.createElement('label');
  lbl.htmlFor = 'field_'+d.name;
  lbl.textContent = d.label;
  row.appendChild(lbl);
  if(d.desc){
    const btn = document.createElement('button');
    btn.type='button'; btn.className='field-help-btn'; btn.innerHTML='&#x2139;&#xFE0F;';
    btn.title = d.desc;
    const descEl = document.createElement('div');
    descEl.className = 'field-desc';
    descEl.textContent = d.desc;
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const open = descEl.classList.toggle('open');
      btn.classList.toggle('active', open);
    });
    row.appendChild(btn);
    row._descEl = descEl;
  }
  if(d.help_url){
    const link = document.createElement('a');
    link.href = d.help_url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.className = 'field-help-link';
    link.innerHTML = '🔑';
    link.title = 'Pobierz API key →';
    row.appendChild(link);
  }
  if(d.autodetect){
    const ab = document.createElement('button');
    ab.type='button'; ab.className='field-detect-btn'; ab.innerHTML='&#x26A1;';
    ab.title='Wykryj automatycznie';
    ab.addEventListener('click', () => {
      ab.innerHTML='&#x23F3;'; ab.disabled=true;
      fetch('/api/detect/'+d.name)
        .then(r=>r.json())
        .then(res => {
          const inp = targetEl;
          if(res.value && inp){ inp.value=res.value; inp.dispatchEvent(new Event('input')); }
          if(res.options && inp && inp.tagName==='SELECT'){
            Array.from(inp.options).forEach(o=>{ o.selected=(o.value===res.value); });
          }
          if(res.options && inp && inp.tagName!=='SELECT'){
            const f = inp.closest('.field');
            let cr = f.querySelector('.field-chips-detect');
            if(!cr){ cr=document.createElement('div'); cr.className='field-chips field-chips-detect'; f.appendChild(cr); }
            cr.innerHTML='';
            res.options.forEach(o=>{
              const b=document.createElement('button'); b.type='button'; b.className='chip'; b.textContent=o.label;
              b.addEventListener('click',()=>{ inp.value=o.value; inp.dispatchEvent(new Event('input')); cr.querySelectorAll('.chip').forEach(x=>x.classList.remove('active')); b.classList.add('active'); });
              cr.appendChild(b);
            });
          }
          if(res.hint){
            const f = inp ? inp.closest('.field') : ab.closest('.field');
            let hd=f.querySelector('.field-hint-detect');
            if(!hd){ hd=document.createElement('div'); hd.className='field-hint field-hint-detect'; f.appendChild(hd); }
            hd.textContent=res.hint;
          }
          ab.innerHTML='&#x2714;'; ab.disabled=false;
          setTimeout(()=>{ ab.innerHTML='&#x26A1;'; },2000);
        })
        .catch(()=>{ ab.innerHTML='&#x26A1;'; ab.disabled=false; });
    });
    row.appendChild(ab);
  }
  return row;
}

function renderInput(d){
  const form = getOrCreateForm();
  const field = document.createElement('div');
  field.className = 'field';
  const inp = document.createElement('input');
  inp.type = d.secret ? 'password' : 'text';
  inp.placeholder = d.placeholder || '';
  inp.value = d.value || '';
  inp.dataset.name = d.name;
  inp.id = 'field_'+d.name;
  const _lrow = buildFieldLabel(d, inp);
  field.appendChild(_lrow);
  if(_lrow._descEl) field.appendChild(_lrow._descEl);
  // ── IP Picker modal button ────────────────────────────────────────────────
  if(d.modal_type === 'ip_picker'){
    const wrap = document.createElement('div');
    wrap.className = 'field-input-wrap';
    wrap.appendChild(inp);
    const pickBtn = document.createElement('button');
    pickBtn.type = 'button';
    pickBtn.className = 'eye-btn';
    pickBtn.innerHTML = '🔍';
    pickBtn.title = 'Wybierz z listy urządzeń';
    pickBtn.addEventListener('click', () => openIpPickerModal(inp));
    pickBtn.addEventListener('mousedown', e => e.preventDefault());
    wrap.appendChild(pickBtn);
    field.appendChild(wrap);
  }

  // ── Eye toggle for password fields ───────────────────────────────────────
  if(d.secret){
    const wrap = document.createElement('div');
    wrap.className = 'field-input-wrap';
    wrap.appendChild(inp);
    const eye = document.createElement('button');
    eye.type = 'button';
    eye.className = 'eye-btn';
    eye.innerHTML = '👁';
    eye.title = 'Pokaż/ukryj';
    let visible = false;
    eye.addEventListener('click', () => {
      visible = !visible;
      inp.type = visible ? 'text' : 'password';
      eye.classList.toggle('active', visible);
    });
    eye.addEventListener('mousedown', e => e.preventDefault()); // no focus steal
    wrap.appendChild(eye);
    field.appendChild(wrap);
  } else {
    field.appendChild(inp);
  }

  // ── Chips (clickable suggestions) ────────────────────────────────────────
  if(d.chips && d.chips.length){
    const row = document.createElement('div');
    row.className = 'field-chips';
    d.chips.forEach(chip => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chip';
      btn.textContent = chip.label;
      btn.title = chip.value !== chip.label ? chip.value : '';
      btn.addEventListener('click', () => {
        inp.value = chip.value;
        if(d.secret) inp.type = 'text'; // reveal password on select
        inp.dispatchEvent(new Event('input'));
        row.querySelectorAll('.chip').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      });
      row.appendChild(btn);
    });
    field.appendChild(row);
  }

  // ── Hint text ─────────────────────────────────────────────────────────────
  if(d.hint){
    const hint = document.createElement('div');
    hint.className = 'field-hint';
    hint.textContent = d.hint;
    field.appendChild(hint);
  }

  form.appendChild(field);
}

function renderSelect(d){
  const form = getOrCreateForm();
  const field = document.createElement('div');
  field.className = 'field';
  const sel = document.createElement('select');
  sel.dataset.name = d.name;
  sel.id = 'field_'+d.name;
  const _slrow = buildFieldLabel(d, sel);
  field.appendChild(_slrow);
  if(_slrow._descEl) field.appendChild(_slrow._descEl);
  d.options.forEach(o => {
    const opt = document.createElement('option');
    opt.value = o.value; opt.textContent = o.label;
    if(o.value === d.value) opt.selected = true;
    sel.appendChild(opt);
  });
  field.appendChild(sel);
  // Toggle custom model input visibility when LLM_MODEL changes
  if(d.name === 'LLM_MODEL'){
    sel.addEventListener('change', () => {
      const customField = document.getElementById('field_LLM_MODEL_CUSTOM');
      if(customField){
        const wrap = customField.closest('.field');
        if(wrap) wrap.style.display = sel.value === '__custom__' ? '' : 'none';
      }
    });
    // Initial state: hide custom if not __custom__
    setTimeout(() => {
      const customField = document.getElementById('field_LLM_MODEL_CUSTOM');
      if(customField){
        const wrap = customField.closest('.field');
        if(wrap) wrap.style.display = sel.value === '__custom__' ? '' : 'none';
      }
    }, 100);
  }
  // Dynamic hint + arg placeholder when hint_map is provided
  if(d.hint_map){
    const hint = document.createElement('div');
    hint.className = 'field-hint';
    hint.id = 'hint_'+d.name;
    hint.textContent = d.hint_map[sel.value] || '';
    field.appendChild(hint);
    sel.addEventListener('change', () => {
      hint.textContent = d.hint_map[sel.value] || '';
      if(d.arg_placeholder_map){
        const argEl = document.getElementById('field_ssh_arg');
        if(argEl){ argEl.placeholder = d.arg_placeholder_map[sel.value] || ''; argEl.value = ''; }
      }
    });
  }
  form.appendChild(field);
}

function renderCode(d){
  const pre = document.createElement('div');
  pre.className = 'w-code';
  pre.textContent = d.text;
  widgets.appendChild(pre);
}

function renderStatus(d){
  const wrap = document.createElement('div');
  wrap.className = 'w-status';
  d.items.forEach(item => {
    const row = document.createElement('div');
    row.className = 'status-item';
    row.innerHTML = `<div class="status-dot ${item.ok?'ok':'err'}"></div>
      <span class="status-name">${item.name}</span>
      <span class="status-detail">${item.detail||''}</span>`;
    wrap.appendChild(row);
  });
  widgets.appendChild(wrap);
}

function renderProgress(d){
  const key = 'proc-' + d.label.replace(/[^a-z0-9]/gi,'_');
  let item = processesList.querySelector(`[data-proc="${key}"]`);
  if (!item) {
    item = document.createElement('div');
    item.className = 'process-item';
    item.setAttribute('data-proc', key);
    processesList.appendChild(item);
  }
  const statusClass = d.done ? 'running' : d.error ? 'stopped' : 'unknown';
  const icon = d.done ? '✅' : d.error ? '❌' : '⏳';
  item.innerHTML = `
    <div class="process-status ${statusClass}"></div>
    <span class="process-name">${icon} ${d.label}</span>`;
  processesList.scrollTop = processesList.scrollHeight;
}

// ── Panel resizing ────────────────────────────────────────────────────────────
const resizeHandleChat = document.getElementById('resize-handle-chat');
const resizeHandleLogs = document.getElementById('resize-handle-logs');
const chatPanel        = document.getElementById('chat-panel');
const processesPanel   = document.getElementById('processes-panel');
const logPanel         = document.getElementById('log-panel');
const mainContainer    = document.querySelector('.main');
let isResizing = false, activeHandle = null, startX = 0, startWidths = {};

function setupResizeHandle(handle, leftPanel, rightPanel) {
  handle.addEventListener('mousedown', (e) => {
    isResizing = true; activeHandle = handle; startX = e.clientX;
    startWidths = { left: leftPanel.offsetWidth, right: rightPanel.offsetWidth };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    document.body.style.pointerEvents = 'none';
    handle.style.pointerEvents = 'auto';
    e.preventDefault();
  });
}
setupResizeHandle(resizeHandleChat, chatPanel, processesPanel);
setupResizeHandle(resizeHandleLogs, processesPanel, logPanel);

document.addEventListener('mousemove', (e) => {
  if (!isResizing || !activeHandle) return;
  const deltaX = e.clientX - startX;
  const min = 200;
  if (activeHandle === resizeHandleChat) {
    const nC = startWidths.left + deltaX, nP = startWidths.right - deltaX;
    if (nC >= min && nP >= min) { chatPanel.style.width = nC+'px'; processesPanel.style.width = nP+'px'; }
  } else if (activeHandle === resizeHandleLogs) {
    const nP = startWidths.left + deltaX, nL = startWidths.right - deltaX;
    if (nP >= min && nL >= min) { processesPanel.style.width = nP+'px'; logPanel.style.width = nL+'px'; }
  }
});

document.addEventListener('mouseup', () => {
  if (!isResizing) return;
  isResizing = false; activeHandle = null;
  document.body.style.cursor = ''; document.body.style.userSelect = ''; document.body.style.pointerEvents = '';
  localStorage.setItem('dockfra-chat-width',      chatPanel.offsetWidth);
  localStorage.setItem('dockfra-processes-width', processesPanel.offsetWidth);
  localStorage.setItem('dockfra-log-width',        logPanel.offsetWidth);
});

function restorePanelWidths() {
  const cw = localStorage.getItem('dockfra-chat-width');
  const pw = localStorage.getItem('dockfra-processes-width');
  const lw = localStorage.getItem('dockfra-log-width');
  if (cw && pw && lw) {
    chatPanel.style.width = cw+'px'; processesPanel.style.width = pw+'px'; logPanel.style.width = lw+'px';
  } else {
    chatPanel.style.width = '25%'; processesPanel.style.width = '20%'; logPanel.style.width = '55%';
  }
}
setTimeout(restorePanelWidths, 100);

// ── Processes panel ───────────────────────────────────────────────────────────
async function updateProcesses() {
  try {
    const processes = await fetch('/api/processes').then(r => r.json());
    processesList.innerHTML = '';
    processes.forEach(process => {
      const item = document.createElement('div');
      item.className = 'process-item';
      const statusClass = process.status === 'running' ? 'running' : process.status === 'stopped' ? 'stopped' : 'unknown';
      const actionsContainer = document.createElement('div');
      actionsContainer.className = 'process-actions';
      const stopBtn = document.createElement('button');
      stopBtn.className = 'process-icon-btn';
      stopBtn.innerHTML = '⏹<span class="tooltip">Stop</span>';
      stopBtn.onclick = async () => { await executeProcessAction('stop', process.name); setTimeout(updateProcesses, 2000); };
      const restartBtn = document.createElement('button');
      restartBtn.className = 'process-icon-btn';
      restartBtn.innerHTML = '🔄<span class="tooltip">Restart</span>';
      restartBtn.onclick = async () => { await executeProcessAction('restart', process.name); setTimeout(updateProcesses, 2000); };
      const portBtn = document.createElement('button');
      portBtn.className = 'process-icon-btn';
      portBtn.innerHTML = '🔧<span class="tooltip">Change Port</span>';
      portBtn.onclick = async () => {
        const newPort = prompt(`Enter new port for ${process.name}:`);
        if (newPort) { await executeProcessAction('change_port', process.name, { port: newPort }); setTimeout(updateProcesses, 2000); }
      };
      actionsContainer.append(stopBtn, restartBtn, portBtn);
      if (process.status === 'stopped') {
        const fixBtn = document.createElement('button');
        fixBtn.className = 'process-icon-btn fix-btn';
        fixBtn.innerHTML = '🔧<span class="tooltip">Napraw to</span>';
        fixBtn.onclick = () => {
          sendAction('fix_container::' + process.name, '🔧 Napraw: ' + process.name);
        };
        actionsContainer.appendChild(fixBtn);
      }
      item.innerHTML = `
        <div class="process-status ${statusClass}"></div>
        <span class="process-name">${process.name}</span>
        <span class="process-details">${process.details}</span>`;
      if (process.type === 'container') item.appendChild(actionsContainer);
      processesList.appendChild(item);
    });
    if (processes.length === 0)
      processesList.innerHTML = '<div style="color:var(--muted);font-size:.7rem;">No processes found</div>';
  } catch {
    processesList.innerHTML = '<div style="color:var(--red);font-size:.7rem;">Error loading processes</div>';
  }
}

async function executeProcessAction(action, processName, data = {}) {
  try {
    const result = await fetch(`/api/process/${action}/${processName}`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data)
    }).then(r => r.json());
    if (!result.success) alert(`Failed to ${action} ${processName}: ${result.message}`);
  } catch (error) {
    alert(`Error executing ${action} on ${processName}: ${error.message}`);
  }
}

setInterval(updateProcesses, 5000);
updateProcesses();

// ── Services tab ───────────────────────────────────────────────────────────────
const servicesList = document.getElementById('services-list');

async function updateServices() {
  if (!servicesList || servicesList.style.display === 'none') return;
  try {
    const containers = await fetch('/api/containers').then(r => r.json());
    servicesList.innerHTML = '';
    // App-stack containers: those NOT matching management role names
    const mgmtNames = ['manager','monitor','autopilot','desktop'];
    const appContainers = containers.filter(c => {
      const n = c.name.toLowerCase();
      return !mgmtNames.some(m => n.includes(m)) && !n.includes('wizard');
    });
    if (appContainers.length === 0) {
      servicesList.innerHTML = '<div style="color:var(--muted);font-size:.7rem;padding:8px 0">Brak uruchomionych serwisów app.<br>Kliknij 🔧 SSH Developer → Sklonuj i uruchom app.</div>';
      return;
    }
    appContainers.forEach(c => {
      const up = c.status && (c.status.includes('Up') || c.status.includes('healthy'));
      const icon = up ? '🟢' : '🔴';
      const item = document.createElement('div');
      item.className = 'service-item';
      const ports = (c.ports || '').replace(/0\.0\.0\.0:/g,'').replace(/:::/g,'') || '';
      item.innerHTML = `
        <span style="font-size:.8rem">${icon}</span>
        <span class="service-name" title="${c.name}">${c.name.replace(/^dockfra-/,'')}</span>
        <span class="service-ports">${ports.slice(0,20)}</span>
        <div class="service-actions">
          <button class="process-icon-btn" title="Logi" onclick="sendAction('logs::${c.name}','📋 Logi: ${c.name}')">📋</button>
          ${!up ? `<button class="process-icon-btn fix-btn" title="Napraw" onclick="sendAction('fix_container::${c.name}','🔧 Napraw: ${c.name}')">🔧</button>` : ''}
        </div>`;
      servicesList.appendChild(item);
    });
  } catch {
    servicesList.innerHTML = '<div style="color:var(--red);font-size:.7rem;">Błąd ładowania serwisów</div>';
  }
}

// ── Stats tab ──────────────────────────────────────────────────────────────────
const statsPanel = document.getElementById('stats-panel');

async function updateStats() {
  if (!statsPanel || statsPanel.style.display === 'none') return;
  try {
    const [s, tickets] = await Promise.all([
      fetch('/api/stats').then(r => r.json()),
      fetch('/api/tickets').then(r => r.json()),
    ]);
    let html = '';

    // ── Ticket list as cards ──────────────────────────────────────────────────
    html += '<div class="stats-section">';
    html += '<div class="stats-title-row"><span class="stats-title">🎫 Tickety</span>';
    html += `<button class="stats-action" onclick="sendAction('ticket_create_wizard','📝 Utwórz ticket')">+ Nowy</button></div>`;
    if (tickets.length === 0) {
      html += '<div class="stats-empty" style="padding:12px 0">Brak ticketów.<br>Kliknij <strong>+ Nowy</strong> aby dodać.</div>';
    } else {
      const statusIcon = {open:'○',in_progress:'◐',review:'◑',done:'●',closed:'●'};
      const statusCls  = {open:'badge-accent',in_progress:'badge-yellow',review:'badge-cyan',done:'badge-muted',closed:'badge-muted'};
      const prioIcon   = {critical:'🔴',high:'🟠',normal:'🟡',low:'🟢'};
      tickets.forEach(tk => {
        const si = statusIcon[tk.status]||'○';
        const sc = statusCls[tk.status]||'badge-muted';
        const pi = prioIcon[tk.priority]||'⚪';
        const ghLink = tk.github_issue_number
          ? `<a class="ticket-gh-link" href="https://github.com/${tk.github_repo||''}/issues/${tk.github_issue_number}" target="_blank" title="GitHub #${tk.github_issue_number}">🔗 GH#${tk.github_issue_number}</a>`
          : '';
        html += `<div class="stats-ticket-card" data-id="${tk.id}">
          <div class="stats-ticket-header">
            <span class="stats-ticket-id"><span class="stats-badge ${sc}">${si} ${tk.id}</span></span>
            <span class="stats-ticket-prio">${pi}</span>
            ${ghLink}
          </div>
          <div class="stats-ticket-title">${tk.title}</div>
          ${tk.description ? `<div class="stats-ticket-desc">${tk.description.slice(0,80)}${tk.description.length>80?'…':''}</div>` : ''}
          <div class="stats-ticket-actions">
            ${tk.status === 'open' ? `
              <button class="ticket-btn" data-action="ssh_cmd::developer::ticket-work::${tk.id}">▶ Pracuj</button>
              <button class="ticket-btn" data-action="show_ticket::${tk.id}">👁️</button>
            ` : tk.status === 'in_progress' ? `
              <button class="ticket-btn" data-action="ssh_cmd::developer::ticket-work::${tk.id}">▶ Pracuj</button>
              <button class="ticket-btn" data-action="ssh_cmd::developer::implement::${tk.id}">🤖</button>
              <button class="ticket-btn ticket-btn-diff" data-action="show_diff::${tk.id}">📄 Diff</button>
              <button class="ticket-btn" data-action="show_ticket::${tk.id}">👁️</button>
            ` : tk.status === 'review' ? `
              <button class="ticket-btn ticket-btn-done" data-action="manager_approve::${tk.id}">✅ Approve</button>
              <button class="ticket-btn" data-action="manager_reject::${tk.id}">🔄 Reject</button>
              <button class="ticket-btn ticket-btn-diff" data-action="show_diff::${tk.id}">📄 Diff</button>
              <button class="ticket-btn" data-action="show_ticket::${tk.id}">👁️</button>
            ` : `
              <button class="ticket-btn" data-action="show_ticket::${tk.id}">👁️</button>
              <button class="ticket-btn ticket-btn-diff" data-action="show_diff::${tk.id}">📄 Diff</button>
              <button class="ticket-btn" data-action="ssh_cmd::developer::ticket-work::${tk.id}">🔄 Reopen</button>
            `}
            ${!tk.github_issue_number ? `<button class="ticket-btn ticket-btn-gh" data-action="ticket_push_github::${tk.id}" title="Wypchnij do GitHub Issues">🔗</button>` : ''}
          </div>
        </div>`;
      });
    }
    html += '</div>';

    // ── Git ───────────────────────────────────────────────────────────────────
    const g = s.git || {};
    if (g.branch) {
      html += '<div class="stats-section"><div class="stats-title">📂 Git</div>';
      html += `<div class="stats-row"><code>${g.branch}</code> · ${g.commits_today||0} commitów dziś</div>`;
      if (g.last_commit) html += `<div class="stats-row stats-dim">${g.last_commit}</div>`;
      html += '</div>';
    }

    // ── Containers ────────────────────────────────────────────────────────────
    const ct = s.containers || {};
    html += '<div class="stats-section"><div class="stats-title">🐳 Kontenery</div><div class="stats-badges">';
    html += `<span class="stats-badge badge-green">✅ ${ct.running||0} OK</span>`;
    if (ct.failing > 0) html += `<span class="stats-badge badge-red">🔴 ${ct.failing} błędów</span>`;
    html += '</div></div>';

    // ── Integrations ──────────────────────────────────────────────────────────
    const intg = s.integrations || {};
    html += '<div class="stats-section"><div class="stats-title-row"><span class="stats-title">🔗 Integracje</span>';
    html += `<button class="stats-action" onclick="sendAction('integrations_setup','🔗 Integracje')">Konfiguruj</button></div><div class="stats-badges">`;
    let anyIntg = false;
    for (const [name, ok] of Object.entries(intg)) {
      if (ok) { html += `<span class="stats-badge badge-green">✅ ${name}</span>`; anyIntg = true; }
    }
    if (!anyIntg) html += `<span class="stats-badge badge-muted">⚠️ brak</span>`;
    html += '</div></div>';

    // ── Developer Health ──────────────────────────────────────────────────────
    html += '<div class="stats-section"><div class="stats-title-row"><span class="stats-title">🔧 SSH Developer</span>';
    html += `<button class="stats-action" onclick="sendAction('logs::dockfra-ssh-developer','📋 Developer logs')">Logi</button></div>`;
    html += '<div id="stats-dev-health" class="stats-badges"><span class="stats-badge badge-muted">⏳ sprawdzam...</span></div></div>';

    // ── LLM Engine Status ────────────────────────────────────────────────────
    html += '<div class="stats-section"><div class="stats-title-row"><span class="stats-title">🤖 Silniki LLM</span>';
    html += `<button class="stats-action" onclick="sendAction('engine_select','🔧 Silniki')">Konfiguruj</button></div>`;
    html += '<div id="stats-engine-status" class="stats-badges"><span class="stats-badge badge-muted">⏳ testuję...</span></div></div>';

    // ── Suggestions ───────────────────────────────────────────────────────────
    const sugg = s.suggestions || [];
    if (sugg.length > 0) {
      html += '<div class="stats-section"><div class="stats-title">💡 Propozycje</div>';
      sugg.forEach(sg => {
        html += `<button class="stats-suggestion" onclick="sendAction('${sg.action}','${sg.icon} ${sg.text.replace(/'/g,"\\'")}')">
          <span class="stats-sugg-icon">${sg.icon}</span>
          <span class="stats-sugg-text">${sg.text}</span>
        </button>`;
      });
      html += '</div>';
    }

    statsPanel.innerHTML = html;

    // ── Async: fetch developer health ─────────────────────────────────────
    fetch('/api/developer-health').then(r=>r.json()).then(dh => {
      const el = document.getElementById('stats-dev-health');
      if (!el) return;
      let badges = '';
      const ci = dh.container === 'running' ? 'badge-green' : 'badge-red';
      badges += `<span class="stats-badge ${ci}">${dh.container === 'running' ? '✅' : '🔴'} kontener</span>`;
      badges += `<span class="stats-badge ${dh.ssh === 'ok' ? 'badge-green' : 'badge-red'}">${dh.ssh === 'ok' ? '✅' : '🔴'} exec</span>`;
      badges += `<span class="stats-badge badge-accent">📂 git: ${dh.git||'?'}</span>`;
      badges += `<span class="stats-badge badge-muted">📜 ${dh.scripts||0} skryptów</span>`;
      const eng = dh.engines || {};
      if (eng.built_in) badges += `<span class="stats-badge badge-green">✅ built-in</span>`;
      if (eng.aider) badges += `<span class="stats-badge badge-green">✅ aider</span>`;
      if (eng.claude_code) badges += `<span class="stats-badge badge-green">✅ claude</span>`;
      el.innerHTML = badges;
    }).catch(() => {
      const el = document.getElementById('stats-dev-health');
      if (el) el.innerHTML = '<span class="stats-badge badge-red">🔴 niedostępny</span>';
    });

    // ── Async: fetch engine status ────────────────────────────────────────
    fetch('/api/engine-status').then(r=>r.json()).then(es => {
      const el = document.getElementById('stats-engine-status');
      if (!el) return;
      let badges = '';
      (es.engines||[]).forEach(e => {
        const ok = e.ok;
        const pref = e.id === es.preferred ? ' ★' : '';
        const cls = ok ? 'badge-green' : 'badge-red';
        const icon = ok ? '✅' : '🔴';
        badges += `<span class="stats-badge ${cls}" title="${e.message||''}">${icon} ${e.name}${pref}</span>`;
      });
      if (!badges) badges = '<span class="stats-badge badge-muted">⚠️ brak silników</span>';
      el.innerHTML = badges;
    }).catch(() => {
      const el = document.getElementById('stats-engine-status');
      if (el) el.innerHTML = '<span class="stats-badge badge-red">🔴 błąd testu</span>';
    });

    // ── Async: fetch diff change counts for ticket badges ─────────────────
    tickets.forEach(tk => {
      if (tk.status === 'open') return;
      fetch(`/api/ticket-diff/${encodeURIComponent(tk.id)}`).then(r=>r.json()).then(d => {
        const count = (d.commits||[]).length;
        // Find all diff buttons for this ticket and add count badge
        statsPanel.querySelectorAll(`.ticket-btn-diff[data-action="show_diff::${tk.id}"]`).forEach(btn => {
          btn.textContent = count > 0 ? `📄 ${count}` : '📄 0';
          if (count > 0) btn.classList.add('has-changes');
        });
      }).catch(() => {});
    });

    // Delegate ticket-btn clicks inside stats panel
    statsPanel.querySelectorAll('.ticket-btn[data-action]').forEach(btn => {
      btn.addEventListener('click', () => {
        const act = btn.dataset.action;
        if (act.startsWith('show_ticket::')) { openDiffModal(act.split('::')[1]); return; }
        if (act.startsWith('show_diff::')) { openDiffModal(act.split('::')[1], true); return; }
        sendAction(act, btn.textContent.trim());
      });
    });
  } catch(e) {
    statsPanel.innerHTML = '<div style="color:var(--red);font-size:.7rem;padding:8px">Błąd ładowania statystyk</div>';
  }
}

// ── Panel tab switching ────────────────────────────────────────────────────────
document.querySelectorAll('.panel-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const target = tab.dataset.tab;
    processesList.style.display = target === 'processes' ? '' : 'none';
    servicesList.style.display  = target === 'services'  ? '' : 'none';
    if (statsPanel) statsPanel.style.display = target === 'stats' ? '' : 'none';
    if (target === 'services') updateServices();
    if (target === 'stats') updateStats();
  });
});

setInterval(() => { if (servicesList.style.display !== 'none') updateServices(); }, 8000);
setInterval(() => { if (statsPanel && statsPanel.style.display !== 'none') updateStats(); }, 15000);

// ── Copy buttons ──────────────────────────────────────────────────────────────
function flashCopyBtn(btn, originalText) {
  btn.textContent = '✅ Copied!';
  btn.style.background = 'var(--accent)';
  btn.style.color = '#fff';
  setTimeout(() => { btn.textContent = originalText; btn.style.background = ''; btn.style.color = ''; }, 2000);
}

document.getElementById('copy-logs').addEventListener('click', () => {
  const text = Array.from(logOut.children).map(c => c.textContent).join('\n');
  navigator.clipboard.writeText(text.length > 45000 ? text.slice(-45000) : text)
    .then(() => flashCopyBtn(document.getElementById('copy-logs'), '📋 Copy'))
    .catch(() => { document.getElementById('copy-logs').textContent = '❌ Failed'; });
});

document.getElementById('copy-chat').addEventListener('click', () => {
  const text = Array.from(chat.children).map(d => {
    const role = d.classList.contains('bot') ? '🤖 Bot' : '👤 User';
    const bubble = d.querySelector('.bubble');
    return `${role}: ${bubble ? bubble.textContent : ''}`;
  }).join('\n\n');
  const clipped = text.length > 45000 ? text.slice(-45000) : text;
  navigator.clipboard.writeText(clipped)
    .then(() => flashCopyBtn(document.getElementById('copy-chat'), t('copy')))
    .catch(() => { document.getElementById('copy-chat').textContent = '❌ Failed'; });
});

document.getElementById('copy-processes').addEventListener('click', () => {
  const text = Array.from(processesList.children).map(d => {
    const st = d.querySelector('.process-status');
    const status = st ? (st.classList.contains('running') ? '🟢 Running' : st.classList.contains('stopped') ? '🔴 Stopped' : '⚪ Unknown') : '⚪';
    const name = d.querySelector('.process-name')?.textContent || '';
    const details = d.querySelector('.process-details')?.textContent || '';
    return `${status} | ${name} | ${details}`;
  }).join('\n');
  navigator.clipboard.writeText(text)
    .then(() => flashCopyBtn(document.getElementById('copy-processes'), t('copy')))
    .catch(() => { document.getElementById('copy-processes').textContent = '❌ Failed'; });
});

// ── IP Picker Modal ───────────────────────────────────────────────────────────
function openIpPickerModal(targetInput) {
  // Remove any existing modal
  const existing = document.getElementById('ip-modal-overlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.id = 'ip-modal-overlay';
  overlay.className = 'modal-overlay';
  overlay.addEventListener('click', e => { if(e.target === overlay) overlay.remove(); });

  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.innerHTML = `
    <div class="modal-header">
      <span>🔍 Wybierz IP urządzenia</span>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="modal-scan-btn" title="Skanuj całą podsieć (wolniej)">📡 Skanuj sieć</button>
        <button class="modal-refresh-btn" title="Odśwież ARP">🔄</button>
        <button class="modal-close-btn" title="Zamknij">✕</button>
      </div>
    </div>
    <div class="modal-body">
      <div class="modal-loading">⏳ Wykrywanie urządzeń…</div>
    </div>`;

  modal.querySelector('.modal-close-btn').addEventListener('click', () => overlay.remove());
  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  const body = modal.querySelector('.modal-body');

  async function loadIps(scan=false) {
    const msg = scan ? '⏳ Skanuję podsieć — może potrwać ~10s…' : '⏳ Wykrywanie urządzeń…';
    body.innerHTML = `<div class="modal-loading">${msg}</div>`;
    const url = scan ? '/api/device-ips?scan=1' : '/api/device-ips';
    try {
      const data = await fetch(url).then(r => r.json());
      renderIpModal(body, data, targetInput, overlay);
    } catch(e) {
      body.innerHTML = `<div class="modal-loading" style="color:var(--red)">❌ Błąd: ${e.message}</div>`;
    }
  }

  modal.querySelector('.modal-refresh-btn').addEventListener('click', () => loadIps(false));
  modal.querySelector('.modal-scan-btn').addEventListener('click',    () => loadIps(true));
  loadIps();
}

function renderIpModal(body, data, targetInput, overlay) {
  const stateIcon = { REACHABLE:'🟢', DELAY:'🟡', PROBE:'🟡', STALE:'🟠', FAILED:'🔴', UNKNOWN:'⚪' };
  const current = targetInput.value;
  body.innerHTML = '';

  function portLabel(p) {
    const names = {22:'SSH',80:'HTTP',443:'HTTPS',2200:'SSH-dev',2201:'SSH-mon',2202:'SSH-mgr',
      2203:'SSH-auto',2222:'SSH',3000:'dev',5000:'Flask',6080:'VNC',
      8000:'HTTP',8080:'HTTP',8081:'API',8082:'mobile',8100:'',8202:'',9000:''};
    return names[p] ? `${p}<small>/${names[p]}</small>` : `${p}`;
  }

  function makeRow(ip, mainHtml, d) {
    const row = document.createElement('div');
    row.className = 'modal-ip-row' + (ip === current ? ' selected' : '');

    // hostname
    const hostname = d.hostname
      ? `<span class="modal-hostname" title="hostname">${d.hostname}</span>` : '';

    // open ports (only show when no hostname or always for non-docker)
    const portsHtml = (d.open_ports||[]).map(p =>
      `<span class="modal-ports">${portLabel(p)}</span>`).join('');

    // used-in badge
    const usedBadge = (d.used_in||[]).length
      ? `<span class="modal-badge used" title="${d.used_in.join(', ')}">📌 ${d.used_in[0].split('/').slice(-1)[0]}</span>` : '';

    row.innerHTML = `
      <div class="modal-ip-col">
        <div class="modal-ip-main">${mainHtml}</div>
        <div class="modal-ip-sub">${hostname}${portsHtml}</div>
      </div>
      <div class="modal-ip-meta">${usedBadge}</div>`;

    row.addEventListener('click', () => {
      targetInput.value = ip;
      targetInput.dispatchEvent(new Event('input'));
      overlay.remove();
    });
    return row;
  }

  function makeCollapsibleSection(title, items, renderFn, startCollapsed=false) {
    const sec = document.createElement('div');
    sec.className = 'modal-section';
    const hdr = document.createElement('div');
    hdr.className = 'modal-section-title' + (items.length > 3 ? ' collapsible' : '');
    hdr.innerHTML = `<span>${title} (${items.length})</span>${items.length > 3 ? '<span class="modal-chevron">'+(startCollapsed?'▶':'▼')+'</span>' : ''}`;
    const inner = document.createElement('div');
    if (startCollapsed) inner.style.display = 'none';
    if (items.length > 3) {
      hdr.addEventListener('click', () => {
        const open = inner.style.display !== 'none';
        inner.style.display = open ? 'none' : '';
        hdr.querySelector('.modal-chevron').textContent = open ? '▶' : '▼';
      });
    }
    items.forEach(item => inner.appendChild(renderFn(item)));
    sec.appendChild(hdr);
    sec.appendChild(inner);
    return sec;
  }

  // ── Docker containers ──────────────────────────────────────────────────────
  if (data.docker && data.docker.length) {
    const sec = makeCollapsibleSection('🐋 Kontenery Docker', data.docker, c => {
      const dot = c.status === 'running' ? '🟢' : '🔴';
      const net = c.network ? `<span class="modal-net">${c.network}</span>` : '';
      const ports = c.ports ? c.ports.trim().split(/\s+/).map(p =>
        `<span class="modal-ports">${p}</span>`).join('') : '';
      const main = `${dot} <strong>${c.ip}</strong> <span class="modal-name">${c.name}</span> ${net}`;
      const d = {hostname: '', open_ports: [], used_in: c.used_in||[]};
      const row = makeRow(c.ip, main, d);
      // inject ports into sub line for docker
      const sub = row.querySelector('.modal-ip-sub');
      if (sub && ports) sub.innerHTML += ports;
      return row;
    });
    body.appendChild(sec);
  }

  // ── Separate ARP into real devices vs CNI pods ────────────────────────────
  const arpReal = (data.arp||[]).filter(d => !d.is_cni && !d.is_docker_internal);
  const arpCni  = (data.arp||[]).filter(d => d.is_cni);
  const arpInt  = (data.arp||[]).filter(d => !d.is_cni && d.is_docker_internal);

  if (arpReal.length) {
    const sec = makeCollapsibleSection('📡 Sieć lokalna – ARP', arpReal, d => {
      const icon = stateIcon[d.state] || '⚪';
      const iface = d.iface ? `<span class="modal-net">${d.iface}</span>` : '';
      const state = `<span class="modal-state ${d.state.toLowerCase()}">${d.state}</span>`;
      const main = `${icon} <strong>${d.ip}</strong> ${iface} ${state}`;
      return makeRow(d.ip, main, d);
    });
    body.appendChild(sec);
  }

  if (arpCni.length) {
    const sec = makeCollapsibleSection('☸️ Kubernetes / CNI pods', arpCni, d => {
      const icon = stateIcon[d.state] || '⚪';
      const state = `<span class="modal-state ${d.state.toLowerCase()}">${d.state}</span>`;
      const main = `${icon} <strong>${d.ip}</strong> <span class="modal-net">${d.iface||''}</span> ${state}`;
      return makeRow(d.ip, main, d);
    }, true /* start collapsed */);
    body.appendChild(sec);
  }

  if (arpInt.length) {
    const sec = makeCollapsibleSection('🐋 Docker-internal', arpInt, d => {
      const icon = stateIcon[d.state] || '⚪';
      const main = `${icon} <strong>${d.ip}</strong> <span class="modal-net">${d.iface||''}</span>`;
      return makeRow(d.ip, main, d);
    }, true);
    body.appendChild(sec);
  }

  if (!data.docker?.length && !arpReal.length && !arpCni.length) {
    body.innerHTML = '<div class="modal-loading">⚠️ Nie znaleziono żadnych urządzeń. Uruchom kontenery lub sprawdź sieć.</div>';
  }
}

// ── Log colorization ─────────────────────────────────────────────────────────
function classifyLogLine(text) {
  const t = text;
  // Docker build layer #N
  if (/^#\d+/.test(t)) {
    if (/\bDONE\b/.test(t))                                    return 'log-done';
    if (/error|failed/i.test(t))                               return 'log-err';
    if (/Downloading|Pulling|Fetching|Installing|COPY|RUN /i.test(t)) return 'log-pull';
    return 'log-build';
  }
  // Container lifecycle
  if (/Restart(ing)?\s*\(|\brestarting\b/i.test(t))           return 'log-restart';
  if (/🔴|\bStopped\b/.test(t))                               return 'log-restart';
  // Errors
  if (/\b(error|fatal|traceback|exception|failed|exit code [^0]|bind for|port is already|cannot|no such file|permission denied|connection refused|oci runtime|unhealthy)\b/i.test(t)) return 'log-err';
  // Warnings  
  if (/\b(warning|warn|deprecated|notice)\b/i.test(t))        return 'log-warn';
  // Success / healthy
  if (/\b(successfully|started|created|healthy|done|built|running|🟢|✅|up \d+)\b/i.test(t)) return 'log-ok';
  // Downloads
  if (/\b(downloading|pulling|fetching|━━)\b/i.test(t))       return 'log-pull';
  // pip noise (metadata, notice lines)
  if (/^\s*[#│]|\[notice\]|whl\.metadata|eta 0:00:00/.test(t)) return 'log-dim';
  return '';
}

function highlightLogText(text) {
  return text
    .replace(/\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b/g, '<span class="lh-ip">$1</span>')
    .replace(/:(\d{2,5})\b/g, ':<span class="lh-port">$1</span>')
    .replace(/\bdockfra-[\w-]+\b/g, s => `<span class="lh-svc">${s}</span>`)
    .replace(/(\/[\w.\-/]+\.(py|yml|yaml|json|env|sh|conf|log))/g, '<span class="lh-path">$1</span>');
}

// ── Log panel (streaming) ─────────────────────────────────────────────────────
socket.on('log_line', d => {
  _appendLogLine(d.text);
  _logTotal++;  // keep in sync so polling doesn't duplicate
});

// ── Chat input bar ────────────────────────────────────────────────────────────
const chatInput = document.getElementById('chat-input');
const chatSend  = document.getElementById('chat-send');
function submitChatInput() {
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = '';
  // Shortcut: "nowy ticket <title>" or "create ticket <title>" → ticket_create_do directly
  const ticketShortcut = text.match(/^(?:nowy ticket|create ticket|ticket|dodaj ticket)\s+(.+)/i);
  if (ticketShortcut) {
    const title = ticketShortcut[1].trim();
    const div = document.createElement('div');
    div.className = 'msg user';
    div.innerHTML = `<div class="avatar">👤</div><div class="bubble">📝 Nowy ticket: ${title}</div>`;
    chat.appendChild(div); chat.scrollTop = chat.scrollHeight;
    socket.emit('action', {value: 'ticket_create_do', form: {ticket_title: title, ticket_priority: 'normal', ticket_assigned: 'developer'}});
    return;
  }
  sendAction(text);
}
chatSend.addEventListener('click', submitChatInput);
chatInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitChatInput(); } });

// ── Ticket Diff Modal ─────────────────────────────────────────────────────────
let _diffModalData = null;

function _showDiffToast(tid, title) {
  // Show inline toast when there are zero code changes
  const toast = document.createElement('div');
  toast.className = 'diff-toast';
  toast.innerHTML = `<span class="diff-toast-icon">📄</span><div class="diff-toast-body"><strong>${escHtml(tid)}</strong> ${escHtml(title||'')}<br><span class="diff-toast-sub">Brak zmian w kodzie — commity muszą zawierać ID ticketu (np. <code>feat(${escHtml(tid)}): ...</code>)</span></div><button class="diff-toast-close" onclick="this.parentElement.remove()" title="Zamknij">✕</button>`;
  const chat = document.getElementById('chat');
  if (chat) { chat.appendChild(toast); chat.scrollTop = chat.scrollHeight; }
  setTimeout(() => { if (toast.parentElement) toast.remove(); }, 8000);
}

function openDiffModal(tid, forceModal) {
  const modal = document.getElementById('diff-modal');
  if (!modal) return;

  // Pre-flight: fetch diff first, decide whether to open modal or show toast
  fetch(`/api/ticket-diff/${encodeURIComponent(tid)}`)
    .then(r => r.json())
    .then(d => {
      _diffModalData = d;
      const hasDiff = d.diff && d.diff.trim();
      const hasCommits = d.commits && d.commits.length > 0;

      // If zero changes and not forced — show inline toast, skip modal
      if (!hasDiff && !hasCommits && !forceModal) {
        _showDiffToast(tid, d.title);
        return;
      }

      // Otherwise open the full modal
      document.getElementById('diff-modal-tid').textContent = tid;
      document.getElementById('diff-modal-title-text').textContent = d.title || '';
      const statusEl = document.getElementById('diff-modal-status');
      statusEl.textContent = d.status || '';
      const statusCls = {open:'badge-accent',in_progress:'badge-yellow',review:'badge-cyan',done:'badge-muted',closed:'badge-muted'};
      statusEl.className = 'diff-status-badge ' + (statusCls[d.status] || 'badge-muted');
      document.getElementById('diff-loading').style.display = 'none';
      document.getElementById('diff-content').style.display = 'none';
      document.getElementById('diff-empty').style.display = 'none';
      document.getElementById('diff-commits-list').innerHTML = '';
      document.getElementById('diff-ticket-detail').innerHTML = '';
      switchDiffTab('diff');
      modal.style.display = 'flex';
      document.body.style.overflow = 'hidden';

      // Render diff tab
      if (hasDiff) {
        const pre = document.getElementById('diff-content');
        pre.innerHTML = renderDiffText(d.diff);
        pre.style.display = '';
      } else {
        document.getElementById('diff-empty').style.display = '';
      }

      // Render commits tab
      const commitsList = document.getElementById('diff-commits-list');
      if (hasCommits) {
        commitsList.innerHTML = d.commits.map(c => `
          <div class="diff-commit-row">
            <code class="diff-commit-hash">${c.hash}</code>
            <span class="diff-commit-repo">[${c.repo}]</span>
            <span class="diff-commit-subject">${escHtml(c.subject)}</span>
          </div>`).join('');
      } else {
        commitsList.innerHTML = '<div class="diff-empty">Brak commitów dla tego ticketu.</div>';
      }

      // Render ticket detail tab
      fetch(`/api/tickets/${encodeURIComponent(tid)}`)
        .then(r => r.json())
        .then(tk => {
          const det = document.getElementById('diff-ticket-detail');
          const pi = {critical:'🔴',high:'🟠',normal:'🟡',low:'🟢'}[tk.priority||'normal']||'⚪';
          const comments = (tk.comments||[]).slice(-20).map(c => {
            const ts = (c.timestamp||'').slice(0,16).replace('T',' ');
            return `<div class="diff-comment"><strong>${escHtml(c.author||'?')}</strong> <span class="diff-comment-ts">${ts}</span><br>${escHtml(c.text||'')}</div>`;
          }).join('');
          det.innerHTML = `
            <div class="diff-ticket-meta">
              <span class="diff-tid">${tid}</span>
              <span class="diff-status-badge ${statusCls[tk.status]||'badge-muted'}">${tk.status||''}</span>
              <span>${pi} ${tk.priority||'normal'}</span>
              <span class="diff-meta-sep">→</span>
              <span>${escHtml(tk.assigned_to||'?')}</span>
            </div>
            <div class="diff-ticket-title">${escHtml(tk.title||'')}</div>
            ${tk.description ? `<div class="diff-ticket-desc">${escHtml(tk.description)}</div>` : ''}
            ${comments ? `<div class="diff-comments-section"><div class="diff-comments-label">💬 Komentarze</div>${comments}</div>` : ''}`;
        }).catch(() => {});
    })
    .catch(e => {
      _showDiffToast(tid, `❌ Błąd: ${e}`);
    });
}

function closeDiffModal() {
  const modal = document.getElementById('diff-modal');
  if (modal) modal.style.display = 'none';
  document.body.style.overflow = '';
  _diffModalData = null;
}

function switchDiffTab(tab) {
  ['diff','commits','ticket'].forEach(t => {
    document.getElementById(`diff-tab-${t}`).style.display = t === tab ? '' : 'none';
    document.querySelectorAll('.diff-tab-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.tab === tab);
    });
  });
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDiffModal(); });

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderDiffText(raw) {
  return raw.split('\n').map(line => {
    const e = escHtml(line);
    if (line.startsWith('+++') || line.startsWith('---'))
      return `<span class="diff-file">${e}</span>`;
    if (line.startsWith('@@'))
      return `<span class="diff-hunk">${e}</span>`;
    if (line.startsWith('+'))
      return `<span class="diff-add">${e}</span>`;
    if (line.startsWith('-'))
      return `<span class="diff-del">${e}</span>`;
    if (line.startsWith('commit ') || line.startsWith('Author:') || line.startsWith('Date:'))
      return `<span class="diff-meta">${e}</span>`;
    return `<span class="diff-ctx">${e}</span>`;
  }).join('\n');
}

// Intercept show_ticket:: and show_diff:: clicks globally — open diff modal client-side
document.addEventListener('click', e => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;
  const action = btn.dataset.action;
  if (action && action.startsWith('show_ticket::')) {
    e.preventDefault(); e.stopImmediatePropagation();
    openDiffModal(action.split('::')[1]);
  } else if (action && action.startsWith('show_diff::')) {
    e.preventDefault(); e.stopImmediatePropagation();
    openDiffModal(action.split('::')[1], true); // forceModal=true
  }
}, true); // capture phase — fires before delegated handlers
