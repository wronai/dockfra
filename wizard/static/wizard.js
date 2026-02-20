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

socket.on('connect',    () => { connEl._state='connected';    connEl.textContent = t('connected'); });
socket.on('disconnect', () => { connEl._state='disconnected'; connEl.textContent = t('disconnected'); });

// ── Markdown-lite renderer ────────────────────────────────────────────────────
function renderMd(text){
  return text
    .replace(/^# (.+)$/gm,  '<h1>$1</h1>')
    .replace(/^## (.+)$/gm, '<h2>$2</h2>')
    .replace(/^### (.+)$/gm,'<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g,  '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

// ── Load logs from history ────────────────────────────────────────────────────
async function loadLogs() {
  try {
    const r = await fetch('/api/history');
    const d = await r.json();
    d.logs.forEach(log => {
      if(log.id && document.querySelector(`[data-log-id="${log.id}"]`)) return;
      const l = document.createElement('div');
      l.className = 'log-line' + (/error|Error/.test(log.text)||log.text.startsWith('E ')?' err':'');
      l.setAttribute('data-log-id', log.id);
      l.textContent = log.text;
      logOut.appendChild(l);
    });
    logOut.scrollTop = logOut.scrollHeight;
  } catch(e) { console.warn('loadLogs:', e); }
}

// ── Messages ──────────────────────────────────────────────────────────────────
socket.on('message', d => {
  if (d.id && document.querySelector(`[data-msg-id="${d.id}"]`)) return;
  const div = document.createElement('div');
  div.className = `msg ${d.role}`;
  if (d.id) div.setAttribute('data-msg-id', d.id);
  div.innerHTML = `
    <div class="avatar">${d.role==='bot'?'🤖':'👤'}</div>
    <div class="bubble">${renderMd(d.text)}</div>
    <div class="msg-copy" onclick="copyMessage(this)" title="Copy message">📋</div>`;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
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
});

function collectForm(){
  const form = {};
  widgets.querySelectorAll('input[data-name]').forEach(el => { form[el.dataset.name] = el.value; });
  widgets.querySelectorAll('select[data-name]').forEach(el => { form[el.dataset.name] = el.value; });
  return form;
}

function sendAction(value){
  const form = collectForm();
  const div = document.createElement('div');
  div.className = 'msg user';
  const label = value.replace(/^[^:]+::/,'');
  div.innerHTML = `<div class="avatar">👤</div><div class="bubble">${label}</div>`;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  socket.emit('action', {value, form});
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
    b.onclick = () => sendAction(item.value);
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

function renderInput(d){
  const form = getOrCreateForm();
  const field = document.createElement('div');
  field.className = 'field';
  field.innerHTML = `<label>${d.label}</label>`;
  const inp = document.createElement('input');
  inp.type = d.secret ? 'password' : 'text';
  inp.placeholder = d.placeholder || '';
  inp.value = d.value || '';
  inp.dataset.name = d.name;
  inp.id = 'field_'+d.name;
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
  field.innerHTML = `<label>${d.label}</label>`;
  const sel = document.createElement('select');
  sel.dataset.name = d.name;
  sel.id = 'field_'+d.name;
  d.options.forEach(o => {
    const opt = document.createElement('option');
    opt.value = o.value; opt.textContent = o.label;
    if(o.value === d.value) opt.selected = true;
    sel.appendChild(opt);
  });
  field.appendChild(sel);
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

// ── Copy buttons ──────────────────────────────────────────────────────────────
function flashCopyBtn(btn, originalText) {
  btn.textContent = '✅ Copied!';
  btn.style.background = 'var(--accent)';
  btn.style.color = '#fff';
  setTimeout(() => { btn.textContent = originalText; btn.style.background = ''; btn.style.color = ''; }, 2000);
}

document.getElementById('copy-logs').addEventListener('click', () => {
  const text = Array.from(logOut.children).map(c => c.textContent).join('\n');
  navigator.clipboard.writeText(text.length > 5000 ? text.slice(-5000) : text)
    .then(() => flashCopyBtn(document.getElementById('copy-logs'), '📋 Copy'))
    .catch(() => { document.getElementById('copy-logs').textContent = '❌ Failed'; });
});

document.getElementById('copy-chat').addEventListener('click', () => {
  const text = Array.from(chat.children).map(d => {
    const role = d.classList.contains('bot') ? '🤖 Bot' : '👤 User';
    const bubble = d.querySelector('.bubble');
    return `${role}: ${bubble ? bubble.textContent : ''}`;
  }).join('\n\n');
  navigator.clipboard.writeText(text)
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

// ── Log panel (streaming) ─────────────────────────────────────────────────────
socket.on('log_line', d => {
  if (d.id && document.querySelector(`[data-log-id="${d.id}"]`)) return;
  const l = document.createElement('div');
  l.className = 'log-line' + (d.text.includes('Error')||d.text.includes('error')||d.text.startsWith('E ')?' err':'');
  if (d.id) l.setAttribute('data-log-id', d.id);
  l.textContent = d.text;
  logOut.appendChild(l);
  logOut.scrollTop = logOut.scrollHeight;
  while(logOut.children.length > 500) logOut.removeChild(logOut.firstChild);
});
