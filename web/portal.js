'use strict';
// ส่วนเสริมของแอป: เข้าสู่ระบบและเมนูตามบทบาท กระดานราคา หลังบ้านของผู้ดูแล คู่ค้า คาร์บอน และแผนที่นำทางของคนขับ
// ใช้ตัวช่วยและสถานะจาก app.js ($, esc, num, api, toast, S, view, ...)

// ---------- บทบาทและเมนู ----------
const ROLE_LABEL = { user: 'สมาชิก', driver: 'คนขับรถรับของ', admin: 'ผู้ดูแลระบบ', partner: 'คู่ค้า' };
const TAB_ICON = {
  member: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c1-4 4-5.5 7-5.5s6 1.5 7 5.5"/>',
  dispatch: '<path d="M9 5 4 7v12l5-2 6 2 5-2V5l-5 2z"/><path d="M9 5v12M15 7v12"/>',
  driver: '<path d="M3 7h11v9H3zM14 10h4l3 3v3h-7z"/><circle cx="7.5" cy="17.5" r="1.8"/><circle cx="17.5" cy="17.5" r="1.8"/>',
  records: '<path d="M8 7h11M8 12h11M8 17h11M4.5 7h.01M4.5 12h.01M4.5 17h.01"/>',
  prices: '<path d="M4 19h16M5 15l4-5 4 3 6-8"/><path d="M15 5h4v4"/>',
  settings: '<path d="M5 7h9M18 7h1M5 17h3M12 17h7"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
  partners: '<path d="M4 20V9l5-3v14M9 20V4l11 4v12M3 20h18M13 11h3M13 15h3"/>',
  carbon: '<path d="M5 19c0-8 5-13 14-14 0 9-5 14-13 14zM5 19l7-7"/>',
  portal: '<path d="M4 10l1.5-5h13L20 10M5 10v9h14v-9M4 10h16M10 19v-5h4v5"/>',
};
const TABS = {
  user: [{ id: 'member', label: 'แจ้งรับ' }, { id: 'prices', label: 'ราคา' }, { id: 'carbon', label: 'ลดคาร์บอน' }],
  driver: [{ id: 'driver', label: 'งานของฉัน' }, { id: 'prices', label: 'ราคา' }],
  admin: [{ id: 'dispatch', label: 'แดชบอร์ด' }, { id: 'settings', label: 'เกณฑ์รับของ' }, { id: 'prices', label: 'ราคา' },
    { id: 'partners', label: 'คู่ค้า' }, { id: 'carbon', label: 'คาร์บอน' }, { id: 'records', label: 'บันทึก' }],
  partner: [{ id: 'portal', label: 'พอร์ทัล' }, { id: 'prices', label: 'ราคา' }],
};
let entered = false;   // เข้าสู่ระบบและแสดงแอปแล้ว
let shellKey = '';

function renderShell() {
  const key = `${S.me.id}:${view}`;
  if (key === shellKey) return;
  shellKey = key;
  const tabs = TABS[S.me.role];
  $('#tabs').style.setProperty('--tab-count', tabs.length);
  $('#tabs').innerHTML = tabs.map((t) => `<button type="button" data-view="${t.id}" class="${t.id === view ? 'active' : ''}" ${t.id === view ? 'aria-current="page"' : ''}>
    <svg viewBox="0 0 24 24" aria-hidden="true">${TAB_ICON[t.id]}</svg><span>${t.label}</span></button>`).join('');
  document.body.className = `role-${S.me.role}`;   // ธีมและการจัดวางต่างกันตามบทบาท (ผู้ดูแลใช้ธีมแดชบอร์ดสีเข้ม)
  $('#who-name').textContent = S.me.name;
  $('#who-role').textContent = ROLE_LABEL[S.me.role];
}

// renderAll ของ app.js ถูกเรียกหลังดึงข้อมูลทุกครั้ง จึงให้ทำงานเฉพาะเมื่อเข้าแอปแล้ว
const renderAllBase = renderAll;
renderAll = function () { if (entered && S) renderAllBase(); };

async function showLogin() {
  entered = false; S = null; lastJson = ''; shellKey = '';
  // ล้างสิ่งที่ค้างจากบัญชีก่อนหน้า
  draftBags = []; draftPhotos = []; slot = null; priceData = null; carbonData = null; settingsShown = ''; drvSel = null; drvFit = '';
  for (const k of Object.keys(tickets)) delete tickets[k];
  openTickets.clear();
  $('#topbar').hidden = true; $('#main').hidden = true; $('#view-login').hidden = false;
  document.body.className = '';
  closeNav(true);
  let accounts = [];
  try { accounts = await (await fetch('/api/demo-accounts')).json(); } catch { /* แสดงเฉพาะฟอร์มรหัสผ่าน */ }
  const groups = Object.keys(ROLE_LABEL).map((role) => ({ role, list: accounts.filter((a) => a.role === role) })).filter((g) => g.list.length);
  $('#quick-login').innerHTML = groups.length ? groups.map((g) => `<div class="quick-group"><h3><svg class="ic" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">${TAB_ICON[{ user: 'member', driver: 'driver', admin: 'settings', partner: 'partners' }[g.role]]}</svg>${ROLE_LABEL[g.role]}</h3>
      ${g.list.map((a) => `<button type="button" class="quick" data-quick="${a.id}"><strong>${esc(a.name)}</strong><small>${esc(a.username)}</small></button>`).join('')}</div>`).join('')
    : '<p class="muted">ปิดการเข้าใช้งานด่วนไว้ ใช้ชื่อผู้ใช้และรหัสผ่านด้านล่าง</p>';
}

async function enterApp() {
  await refresh();
  if (!S) return;
  entered = true;
  $('#view-login').hidden = true; $('#topbar').hidden = false; $('#main').hidden = false;
  show(location.hash.slice(1));
  if (S.me.role === 'user') {  // หมุดเริ่มที่ที่อยู่ของสมาชิกที่เพิ่งเข้าสู่ระบบ
    setPin(S.me.member.lat, S.me.member.lng);
    renderBags();
    document.querySelectorAll('#slot-chips button').forEach((c) => c.classList.remove('active'));
    $('#submit-result').innerHTML = '';
  }
}

async function doLogin(path, body) {
  const err = $('#login-error');
  err.hidden = true;
  try {
    await api(path, body);
    history.replaceState(null, '', location.pathname);
    await enterApp();
  } catch (e) { err.textContent = e.message; err.hidden = false; }
}
$('#quick-login').addEventListener('click', (e) => { const b = e.target.closest('[data-quick]'); if (b) doLogin('/login/quick', { user_id: Number(b.dataset.quick) }); });
$('#login-form').addEventListener('submit', (e) => { e.preventDefault(); doLogin('/login', { username: $('#login-user').value, password: $('#login-pass').value }); });
$('#logout').addEventListener('click', async () => { try { await api('/logout', {}); } catch { /* ออกจากหน้าจออยู่ดี */ } history.replaceState(null, '', location.pathname); showLogin(); });

// ---------- แดชบอร์ดของผู้ดูแล ----------
// สีของประเภทวัสดุในวงแหวน: ลำดับคงที่ ผ่านการตรวจการแยกแยะสีบนพื้นเข้มแล้ว และมีป้ายชื่อกับตัวเลขกำกับทุกส่วน
const TYPE_COLOR = { plastic: '#3987e5', paper: '#d95926', metal: '#199e70', glass: '#c98500' };
const TYPE_NAME = { plastic: 'พลาสติก', paper: 'กระดาษ', metal: 'โลหะ', glass: 'แก้ว' };

function donut(parts, total) {
  const R = 42, C = 2 * Math.PI * R, gap = parts.length > 1 ? 2.5 : 0;
  let acc = 0;
  const arcs = parts.map((p) => {
    const len = (p.value / total) * C, seg = `<circle r="${R}" cx="60" cy="60" fill="none" stroke="${p.color}" stroke-width="14" stroke-dasharray="${Math.max(0.5, len - gap)} ${C}" stroke-dashoffset="${-acc}"><title>${p.label} ${num(p.value, 1)} กก.</title></circle>`;
    acc += len;
    return seg;
  }).join('');
  return `<svg class="donut" viewBox="0 0 120 120" role="img" aria-label="สัดส่วนน้ำหนักของวัสดุที่รอรับ"><g transform="rotate(-90 60 60)">${arcs}</g>
    <text x="60" y="58" text-anchor="middle" class="donut-num">${num(total, 1)}</text><text x="60" y="74" text-anchor="middle" class="donut-unit">กก. รอรับ</text></svg>`;
}

function renderDashWidgets(plan, pending, stops) {
  const kg = {};
  for (const r of pending) for (const m of r.materials) { const t = S.config.materials[m.material]?.factory; if (t) kg[t] = (kg[t] || 0) + m.share * r.est_kg; }
  const parts = Object.keys(TYPE_COLOR).filter((t) => kg[t] > 0).map((t) => ({ label: TYPE_NAME[t], value: kg[t], color: TYPE_COLOR[t] }));
  const total = parts.reduce((a, p) => a + p.value, 0);
  const routeOf = Object.fromEntries(plan.routes.map((r) => [r.vehicle_id, r]));
  const byId = Object.fromEntries(S.requests.map((r) => [r.id, r]));
  const flagged = S.requests.filter((r) => r.flags.length).length, waiting = S.notices.filter((n) => !n.ack_at).length;
  $('#dash-widgets').innerHTML = `
    <section class="card widget"><h2>งานวันนี้</h2>
      <p class="big-num">${num(stops)}<small>/${num(pending.length)} จุดที่จัดลงรถ</small></p>
      <div class="mini-stats"><div><b>${num(plan.total_km, 1)}</b><span>กม. รวม</span></div><div><b>${plan.baseline_km > 0 ? num(plan.saving_pct) + '%' : '–'}</b><span>สั้นกว่าลำดับแจ้ง</span></div>
        <div><b>${num(pending.reduce((a, r) => a + r.bags.length, 0))}</b><span>ถุงรอรับ</span></div></div></section>
    <section class="card widget"><h2>วัสดุที่รอรับ</h2>
      ${total ? `<div class="donut-wrap">${donut(parts, total)}<ul class="legend-list">${parts.map((p) => `<li><span class="sw" style="background:${p.color}"></span>${p.label} ${num((p.value / total) * 100)}%<b>${num(p.value, 1)} กก.</b></li>`).join('')}</ul></div>`
        : '<p class="muted">ไม่มีงานรอรับ</p>'}</section>
    <section class="card widget"><h2>รถ</h2>
      ${S.vehicles.map((v) => {
        const r = routeOf[v.id], n = r ? r.stops.length : 0, done = r ? r.stops.filter((s) => byId[s.request_id] && isDone(byId[s.request_id])).length : 0;
        return `<div class="veh"><div class="row between"><strong><span class="veh-dot" style="background:${esc(v.color)};display:inline-block"></span> ${esc(v.name)}</strong>${v.active ? `<span class="muted">${r && n ? `กลับ ${hhmm(r.back_at)}` : 'ไม่มีงาน'}</span>` : '<span class="badge warn">หยุดใช้งาน</span>'}</div>
          <div class="pbar" title="ใช้พื้นที่ ${num(r?.load_units)}/${num(v.capacity_units)} ถุง"><span style="width:${r ? Math.round((r.load_units / v.capacity_units) * 100) : 0}%;background:${esc(v.color)}"></span></div>
          <div class="pbar-label"><span>พื้นที่ ${num(r?.load_units)}/${num(v.capacity_units)} ถุง</span><span>รับแล้ว ${num(done)}/${num(n)} จุด</span></div></div>`;
      }).join('')}</section>
    <section class="card widget"><h2>ต้องดูแล</h2>
      <ul class="status-list">
        <li><span class="st ${flagged ? 'warn' : 'ok'}"></span>กรณีผ่อนปรนหรือต้องตรวจ<b>${num(flagged)}</b></li>
        <li><span class="st ${plan.unassigned.length ? 'warn' : 'ok'}"></span>จุดที่จัดรถไม่ลง<b>${num(plan.unassigned.length)}</b></li>
        <li><span class="st ${waiting ? 'warn' : 'ok'}"></span>ข้อความที่คู่ค้ายังไม่รับทราบ<b>${num(waiting)}</b></li>
        <li><span class="st ${S.ai_mode === 'claude' ? 'ok' : 'warn'}"></span>AI<b>${S.ai_mode === 'claude' ? 'พร้อมใช้' : 'โหมดจำลอง'}</b></li>
      </ul></section>`;
  drawWeekly();
}

function drawWeekly() {
  const rows = S.weekly, v = rows.map((r) => r.kg);
  const W = 900, H = 230, L = 46, R = 24, T = 18, B = 30, hi = Math.max(...v, 1) * 1.15;
  const x = (i) => L + (i / (rows.length - 1)) * (W - L - R), y = (p) => T + ((hi - p) / hi) * (H - T - B);
  const line = rows.map((r, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(r.kg).toFixed(1)}`).join('');
  const wk = (iso) => thDay(iso);
  const sum = v.reduce((a, b) => a + b, 0);
  $('#dash-weekly').innerHTML = `<div class="row between"><h2>น้ำหนักที่รับจริงรายสัปดาห์ (กก.)</h2><span class="muted">${rows.length} สัปดาห์ล่าสุด รวม ${num(sum, 1)} กก.</span></div>
    <div class="chart" id="weekly-chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="กราฟน้ำหนักที่รับจริงรายสัปดาห์">
      ${niceTicks(0, hi).map((t) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}"/><text class="axis" x="${L - 8}" y="${y(t) + 4}" text-anchor="end">${num(t)}</text>`).join('')}
      ${rows.map((r, i) => `<text class="axis" x="${x(i)}" y="${H - 9}" text-anchor="middle">${wk(r.week)}</text>`).join('')}
      <path class="area" d="${line}L${x(rows.length - 1)} ${H - B}L${L} ${H - B}Z"/><path class="line" d="${line}"/>
      ${rows.map((r, i) => `<circle class="end" cx="${x(i)}" cy="${y(r.kg)}" r="4"/>`).join('')}
      <line class="cross" id="wk-cross" y1="${T}" y2="${H - B}" visibility="hidden"/>
      <rect id="wk-hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent"/>
    </svg><div class="chart-tip" id="wk-tip" hidden></div></div>
    <details class="data-table"><summary>ดูเป็นตาราง</summary><div class="table-wrap"><table><thead><tr><th>สัปดาห์ที่เริ่ม</th><th>น้ำหนัก (กก.)</th><th>จำนวนครั้งที่รับ</th></tr></thead><tbody>
      ${rows.map((r) => `<tr><td>${wk(r.week)}</td><td class="num">${num(r.kg, 1)}</td><td class="num">${num(r.pickups)}</td></tr>`).join('')}</tbody></table></div></details>`;
  const svg = $('#weekly-chart svg'), tip = $('#wk-tip'), cross = $('#wk-cross');
  const move = (e) => {
    const box = svg.getBoundingClientRect(), px = ((e.clientX - box.left) / box.width) * W;
    const i = Math.max(0, Math.min(rows.length - 1, Math.round(((px - L) / (W - L - R)) * (rows.length - 1))));
    cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i)); cross.setAttribute('visibility', 'visible');
    tip.hidden = false;
    tip.replaceChildren(Object.assign(document.createElement('strong'), { textContent: `${num(rows[i].kg, 1)} กก.` }), Object.assign(document.createElement('span'), { textContent: `สัปดาห์ ${wk(rows[i].week)} · ${num(rows[i].pickups)} ครั้ง` }));
    const left = (x(i) / W) * box.width;
    tip.style.left = `${Math.min(box.width - 150, Math.max(0, left + (left > box.width / 2 ? -160 : 12)))}px`;
    tip.style.top = `${(y(rows[i].kg) / H) * box.height - 10}px`;
  };
  $('#wk-hit').addEventListener('pointermove', move);
  $('#wk-hit').addEventListener('pointerdown', move);
  $('#wk-hit').addEventListener('pointerleave', () => { tip.hidden = true; cross.setAttribute('visibility', 'hidden'); });
}

// ---------- กระดานราคา ----------
let priceData = null, priceAt = 0, priceDays = 30, priceSel = null;
const thDay = (iso) => new Date(iso + 'T00:00:00').toLocaleDateString('th-TH', { day: 'numeric', month: 'short' });

function priceDelta(series, back = 1) {
  const a = series.at(-1).price, b = series.at(-1 - back)?.price ?? series[0].price;
  const pct = b ? ((a - b) / b) * 100 : 0;
  return { now: a, pct, dir: pct > 0.05 ? 'up' : pct < -0.05 ? 'down' : 'flat' };
}
// ทิศทางราคาบอกด้วยสัญลักษณ์และคำ ไม่ได้ใช้สีอย่างเดียว
const deltaBadge = (d) => `<span class="delta ${d.dir}">${d.dir === 'up' ? '▲ ขึ้น' : d.dir === 'down' ? '▼ ลง' : '– คงที่'} ${num(Math.abs(d.pct), 1)}%</span>`;

function sparkline(series) {
  const w = 96, h = 28, v = series.map((p) => p.price), lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
  const pt = (p, i) => `${(i / (v.length - 1)) * (w - 6) + 3},${h - 4 - ((p - lo) / span) * (h - 8)}`;
  const last = pt(v.at(-1), v.length - 1).split(',');
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true"><polyline points="${v.map(pt).join(' ')}"/><circle cx="${last[0]}" cy="${last[1]}" r="2.6"/></svg>`;
}

async function renderPrices() {
  if (!priceData || Date.now() - priceAt > 30000) {
    try { priceData = await api('/prices?days=60'); priceAt = Date.now(); } catch (e) { return toast(e.message); }
  }
  const mats = priceData.materials.map((m) => ({ ...m, view: m.series.slice(-priceDays) }));
  if (!mats.some((m) => m.key === priceSel)) priceSel = mats[0]?.key;
  $('#ticker').innerHTML = mats.map((m) => { const d = priceDelta(m.series); return `<span class="tick"><b>${esc(m.label)}</b> ${num(d.now, 2)} ${deltaBadge(d)}</span>`; }).join('');
  $('#price-cards').innerHTML = mats.map((m) => {
    const d = priceDelta(m.series);
    return `<button type="button" class="price-card ${m.key === priceSel ? 'active' : ''}" data-mat="${m.key}">
      <span class="pc-name"><span class="dot mat-${m.key}"></span>${esc(m.label)}</span>
      <span class="pc-price">${num(d.now, 2)}<small> บาท/กก.</small></span>
      <span class="pc-foot">${deltaBadge(d)}${sparkline(m.view)}</span></button>`;
  }).join('');
  drawPriceDetail(mats.find((m) => m.key === priceSel));
}

function niceTicks(lo, hi, n = 4) {
  const raw = (hi - lo) / n, mag = 10 ** Math.floor(Math.log10(raw)), step = [1, 2, 2.5, 5, 10].find((s) => s * mag >= raw) * mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Number(v.toFixed(4)));
  return out;
}

function drawPriceDetail(m) {
  if (!m) return;
  const s = m.view, v = s.map((p) => p.price);
  const W = 680, H = 260, L = 46, R = 58, T = 14, B = 28;
  // กรอบราคาอ้างอิงจากแหล่งภายนอก (รายการแรกที่เป็นราคาต่อกิโลกรัม) แสดงเป็นแถบบนกราฟถ้ามี
  const band = m.refs.find((r) => priceData.sources[r.source].unit === 'บาท/กก.');
  const all = band ? [...v, band.low, band.high] : v;
  const pad = (Math.max(...all) - Math.min(...all)) * 0.12 || 0.5, lo = Math.min(...all) - pad, hi = Math.max(...all) + pad;
  const x = (i) => L + (i / (s.length - 1)) * (W - L - R), y = (p) => T + ((hi - p) / (hi - lo)) * (H - T - B);
  const line = s.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(p.price).toFixed(1)}`).join('');
  const ticks = niceTicks(lo, hi);
  const xl = [0, Math.floor((s.length - 1) / 2), s.length - 1];
  const day = priceDelta(m.series), range = priceDelta(s, s.length - 1);
  const dec = ticks.some((t) => t % 1) ? 2 : 0;
  $('#price-detail').innerHTML = `
    <div class="pd-head"><div><h2><span class="dot mat-${m.key}"></span>${esc(m.label)}</h2>
      <p class="pd-price">${num(day.now, 2)} <small>บาท/กก.</small></p></div>
      <div class="pd-deltas"><span>เทียบเมื่อวาน ${deltaBadge(day)}</span><span>ใน ${s.length} วัน ${deltaBadge(range)}</span></div></div>
    <div class="chart" id="price-chart">
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="กราฟราคารับซื้อสูงสุดของ${esc(m.label)} ย้อนหลัง ${s.length} วัน">
        ${ticks.map((t) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}"/><text class="axis" x="${L - 8}" y="${y(t) + 4}" text-anchor="end">${num(t, dec)}</text>`).join('')}
        ${xl.map((i, n) => `<text class="axis" x="${x(i)}" y="${H - 8}" text-anchor="${n === 0 ? 'start' : n === 2 ? 'end' : 'middle'}">${thDay(s[i].day)}</text>`).join('')}
        ${band ? `<rect class="band" x="${L}" width="${W - L - R}" y="${y(band.high)}" height="${Math.max(2, y(band.low) - y(band.high))}"/>
          <text class="axis" x="${L + 6}" y="${y(band.high) - 5}">ช่วงราคาอ้างอิง ${num(band.low, 2)}–${num(band.high, 2)} (${esc(priceData.sources[band.source].name)})</text>` : ''}
        <path class="area" d="${line}L${x(s.length - 1)} ${H - B}L${L} ${H - B}Z"/>
        <path class="line" d="${line}"/>
        <line class="cross" id="pc-cross" y1="${T}" y2="${H - B}" visibility="hidden"/>
        <circle class="end" cx="${x(s.length - 1)}" cy="${y(v.at(-1))}" r="4.5"/>
        <text class="endlabel" x="${x(s.length - 1) + 9}" y="${y(v.at(-1)) + 4}">${num(v.at(-1), 2)}</text>
        <circle class="end" id="pc-dot" r="4.5" visibility="hidden"/>
        <rect id="pc-hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent"/>
      </svg>
      <div class="chart-tip" id="pc-tip" hidden></div>
    </div>
    <p class="muted">เส้นคือราคารับซื้อสูงสุดจากคู่ค้าทุกรายในแต่ละวัน ราคาที่ระบบใช้ประเมินให้สมาชิกตอนนี้คือ ${num(m.member_price, 2)} บาท/กก.${m.accepted ? '' : ' (เกณฑ์ปัจจุบันไม่รับวัสดุนี้)'}</p>
    <h3>ราคาล่าสุดของคู่ค้าแต่ละราย</h3>
    <div class="table-wrap"><table><thead><tr><th>คู่ค้า</th><th>ประเภท</th><th>ราคา (บาท/กก.)</th><th>ส่วนต่างจากราคาที่ให้สมาชิก</th><th>ที่มาของราคานี้</th></tr></thead><tbody>
      ${m.offers.map((o) => `<tr><td>${esc(o.name)}</td><td>${o.kind === 'factory' ? 'โรงงาน' : 'ร้านรับซื้อ'}</td><td class="num">${num(o.price, 2)}</td><td class="num">${o.price - m.member_price >= 0 ? '+' : '−'}${num(Math.abs(o.price - m.member_price), 2)}</td>
        <td>${o.entered_at ? `<span class="badge">คู่ค้าบันทึกเอง</span> ${thDay(o.day)} ${timeText(o.entered_at)}` : '<span class="badge gray">ข้อมูลจำลอง</span>'}</td></tr>`).join('')}
    </tbody></table></div>
    <h3>ที่มาอ้างอิงของราคา</h3>
    <p class="muted">ราคาในกราฟและราคาที่ติดป้าย “ข้อมูลจำลอง” ถูกสุ่มขึ้นให้อยู่ในช่วงของแหล่งอ้างอิงแรกในตาราง ราคาที่ติดป้าย “คู่ค้าบันทึกเอง” มาจากคู่ค้าในระบบ ราคาอ้างอิงด้านล่างเป็นราคาในอดีตตามวันที่ของแต่ละแหล่ง ไม่ใช่ราคาวันนี้</p>
    ${m.refs.length ? `<div class="table-wrap"><table><thead><tr><th>รายการตามต้นฉบับ</th><th>ราคา</th><th>หน่วย</th><th>แหล่งที่มา</th></tr></thead><tbody>
      ${m.refs.map((r) => { const src = priceData.sources[r.source]; return `<tr><td>${esc(r.item)}</td><td class="num">${r.low === r.high ? num(r.low, 2) : `${num(r.low, 2)}–${num(r.high, 2)}`}</td><td>${esc(src.unit)}</td>
        <td><a href="${esc(src.url)}" target="_blank" rel="noopener">${esc(src.name)}</a><br><span class="muted">${esc(src.published)} · ${esc(src.basis)}</span></td></tr>`; }).join('')}
    </tbody></table></div>` : '<p class="muted">ยังไม่พบแหล่งอ้างอิงภายนอกของวัสดุนี้</p>'}
    <details class="data-table"><summary>ดูราคารายวันเป็นตาราง</summary><div class="table-wrap"><table><thead><tr><th>วันที่</th><th>ราคาสูงสุด (บาท/กก.)</th></tr></thead><tbody>
      ${[...s].reverse().map((p) => `<tr><td>${thDay(p.day)}</td><td class="num">${num(p.price, 2)}</td></tr>`).join('')}</tbody></table></div></details>`;

  // เส้นเล็งตามตัวชี้: หาวันที่ใกล้ที่สุด แล้วแสดงค่าของวันนั้น
  const svg = $('#price-chart svg'), tip = $('#pc-tip'), cross = $('#pc-cross'), dot = $('#pc-dot');
  const move = (e) => {
    const box = svg.getBoundingClientRect(), px = ((e.clientX - box.left) / box.width) * W;
    const i = Math.max(0, Math.min(s.length - 1, Math.round(((px - L) / (W - L - R)) * (s.length - 1))));
    cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i)); cross.setAttribute('visibility', 'visible');
    dot.setAttribute('cx', x(i)); dot.setAttribute('cy', y(v[i])); dot.setAttribute('visibility', 'visible');
    tip.hidden = false;
    tip.replaceChildren(Object.assign(document.createElement('strong'), { textContent: `${num(v[i], 2)} บาท/กก.` }), Object.assign(document.createElement('span'), { textContent: thDay(s[i].day) }));
    const left = (x(i) / W) * box.width;
    tip.style.left = `${Math.min(box.width - 130, Math.max(0, left + (left > box.width / 2 ? -140 : 12)))}px`;
    tip.style.top = `${(y(v[i]) / H) * box.height - 10}px`;
  };
  $('#pc-hit').addEventListener('pointermove', move);
  $('#pc-hit').addEventListener('pointerdown', move);
  $('#pc-hit').addEventListener('pointerleave', () => { tip.hidden = true; cross.setAttribute('visibility', 'hidden'); dot.setAttribute('visibility', 'hidden'); });
}
$('#price-cards').addEventListener('click', (e) => { const b = e.target.closest('[data-mat]'); if (b) { priceSel = b.dataset.mat; renderPrices(); } });
$('#price-range').addEventListener('click', (e) => {
  if (!e.target.dataset.days) return;
  priceDays = Number(e.target.dataset.days);
  document.querySelectorAll('#price-range button').forEach((b) => b.classList.toggle('active', b === e.target));
  renderPrices();
});

// ---------- เกณฑ์การรับของ (ผู้ดูแล) ----------
let settingsShown = '';
const POLICY_TEXT = {
  below_min_policy: { block: 'ไม่รับ ให้สมาชิกรวมของเพิ่มก่อน', allow_flag: 'ผ่อนปรนให้รับ และติดธงให้ผู้ดูแลเห็น' },
  mixed_policy: { accept: 'รับตามปกติ', warn: 'รับ แต่ติดธงให้ผู้ดูแลเห็น', reject: 'ไม่รับ ให้สมาชิกแยกก่อนส่ง' },
  scan_far_policy: { block: 'ไม่ให้ยืนยันจุด', allow_flag: 'ผ่อนปรนให้ยืนยันได้ และติดธงให้ผู้ดูแลเห็น' },
};
const selectHtml = (key, cur) => `<select data-key="${key}">${Object.entries(POLICY_TEXT[key]).map(([v, t]) => `<option value="${v}" ${v === cur ? 'selected' : ''}>${t}</option>`).join('')}</select>`;
const numHtml = (key, cur, unit, step = 1) => `<span class="unit"><input type="number" min="0" step="${step}" data-key="${key}" value="${cur}"><small>${unit}</small></span>`;
const switchHtml = (key, on, label) => `<label class="switch"><input type="checkbox" data-key="${key}" ${on ? 'checked' : ''}><span>${label}</span></label>`;

function renderSettings() {
  const cfg = S.settings, raw = JSON.stringify(cfg);
  if (raw === settingsShown || $('#settings-form').contains(document.activeElement)) return;  // ไม่ทับค่าที่กำลังแก้
  settingsShown = raw;
  const mats = S.config.materials;
  $('#settings-form').innerHTML = `
    <div class="card"><h2>วัสดุที่รับ ราคา และน้ำหนักต่อชิ้น</h2>
      <p class="muted">ปิดสวิตช์เพื่อหยุดรับวัสดุนั้น ของชนิดนั้นจะขึ้นป้าย “ไม่รับ” ให้สมาชิกเห็นและไม่ถูกนับ</p>
      <div class="table-wrap"><table class="set-table"><thead><tr><th>วัสดุ</th><th>รับ</th><th>ราคาที่ให้สมาชิก</th><th>น้ำหนักต่อชิ้น</th></tr></thead><tbody>
      ${Object.entries(cfg.materials).map(([k, m]) => `<tr><td><span class="dot mat-${k}"></span> ${esc(mats[k].label)}</td>
        <td><label class="switch"><input type="checkbox" data-mat="${k}" data-field="accepted" ${m.accepted ? 'checked' : ''} aria-label="รับ${esc(mats[k].label)}"></label></td>
        <td><span class="unit"><input type="number" min="0" step="0.5" data-mat="${k}" data-field="price" value="${m.price}" aria-label="ราคา${esc(mats[k].label)}"><small>บาท/กก.</small></span></td>
        <td><span class="unit"><input type="number" min="0.001" step="0.005" data-mat="${k}" data-field="unit_kg" value="${m.unit_kg}" aria-label="น้ำหนักต่อชิ้น${esc(mats[k].label)}"><small>กก.</small></span></td></tr>`).join('')}
      </tbody></table></div></div>
    <div class="card"><h2>ตอนแจ้งรับ</h2>
      <div class="set-row"><div><strong>น้ำหนักรวมขั้นต่ำต่อคำขอ</strong><p class="muted">คิดจากน้ำหนักโดยประมาณของทุกถุง</p></div>${numHtml('min_request_kg', cfg.min_request_kg, 'กก.', 0.1)}</div>
      <div class="set-row"><div><strong>ถ้าต่ำกว่าขั้นต่ำ</strong></div>${selectHtml('below_min_policy', cfg.below_min_policy)}</div>
      <div class="set-row"><div><strong>ถุงที่ของปนกัน</strong><p class="muted">AI ระบุว่าถุงนั้นมีวัสดุหลายชนิดปนกัน</p></div>${selectHtml('mixed_policy', cfg.mixed_policy)}</div></div>
    <div class="card"><h2>ตอนคนขับรับของ</h2>
      <div class="set-row"><div><strong>ระยะห่างจากหมุดตอนสแกน QR</strong><p class="muted">ใช้เมื่ออุปกรณ์ของคนขับให้ตำแหน่งได้</p></div>${numHtml('scan_max_distance_m', cfg.scan_max_distance_m, 'ม.', 10)}</div>
      <div class="set-row"><div><strong>ถ้าสแกนไกลเกินระยะ</strong></div>${selectHtml('scan_far_policy', cfg.scan_far_policy)}</div>
      <div class="set-row"><div><strong>รับบางส่วน</strong><p class="muted">ถ้าปิด คนขับต้องพบครบทุกถุงจึงจะยืนยันรับได้</p></div>${switchHtml('allow_partial_pickup', cfg.allow_partial_pickup, 'รับได้แม้ไม่พบบางถุง')}</div>
      <div class="set-row"><div><strong>น้ำหนักจริงต่างจากที่ประเมิน</strong><p class="muted">ถ้าต่างเกินค่านี้ คำขอจะถูกติดธงให้ตรวจ</p></div>${numHtml('weight_tolerance_pct', cfg.weight_tolerance_pct, '%', 5)}</div></div>
    <div class="card"><h2>แต้ม คาร์บอน และการนำทาง</h2>
      <div class="set-row"><div><strong>แต้มต่อกิโลกรัม</strong></div>${numHtml('points_per_kg', cfg.points_per_kg, 'แต้ม')}</div>
      <div class="set-row"><div><strong>ราคาคาร์บอนที่ใช้ตีมูลค่า</strong><p class="muted">เป็นค่าสมมติ ใช้แสดงมูลค่าเทียบเท่าในหน้าคาร์บอน</p></div>${numHtml('carbon_price_thb', cfg.carbon_price_thb, 'บาท/tCO2e', 10)}</div>
      <div class="set-row"><div><strong>เส้นทางตามถนนในโหมดนำทาง</strong><p class="muted">ส่งพิกัดต้นทางและปลายทางไปยังบริการ OSRM สาธารณะ ถ้าปิดจะใช้เส้นตรง</p></div>${switchHtml('road_routing', cfg.road_routing, 'ใช้บริการภายนอก')}</div></div>`;
}

$('#save-settings').addEventListener('click', async () => {
  const patch = { materials: {} };
  for (const el of document.querySelectorAll('#settings-form [data-key]')) patch[el.dataset.key] = el.type === 'checkbox' ? el.checked : el.type === 'number' ? Number(el.value) : el.value;
  for (const el of document.querySelectorAll('#settings-form [data-mat]')) (patch.materials[el.dataset.mat] ||= {})[el.dataset.field] = el.type === 'checkbox' ? el.checked : Number(el.value);
  try {
    await api('/admin/settings', patch, 'PUT');
    document.activeElement?.blur();
    settingsShown = ''; priceData = null;
    await refresh();
    toast('บันทึกเกณฑ์แล้ว มีผลทันที');
  } catch (e) { toast(e.message); }
});

// ---------- คู่ค้า (ผู้ดูแล) ----------
function renderPartners() {
  if ($('#partner-cards').contains(document.activeElement) && document.activeElement.tagName === 'INPUT') return;
  const mats = S.config.materials;
  $('#partner-cards').innerHTML = S.partners.map((p) => {
    const notes = S.notices.filter((n) => n.partner_id === p.id).slice(0, 3);
    return `<article class="card partner">
      <div class="row between"><h2>${esc(p.name)}</h2><span class="badge ${p.kind === 'factory' ? 'info' : 'gray'}">${p.kind === 'factory' ? 'โรงงานรีไซเคิล' : 'ร้านรับซื้อของเก่า'}</span></div>
      <div class="tag-row">${p.accepts_label.map((t) => `<span class="tag-chip">รับ${t}</span>`).join('')}</div>
      <dl class="contact">
        <dt>ผู้ติดต่อ</dt><dd>${esc(p.contact_name)}</dd>
        <dt>โทร</dt><dd><a href="tel:${esc(p.phone.replace(/[^0-9+]/g, ''))}">${esc(p.phone)}</a></dd>
        <dt>LINE</dt><dd>${esc(p.line_id)}</dd>
        <dt>อีเมล</dt><dd><a href="mailto:${esc(p.email)}">${esc(p.email)}</a></dd>
        <dt>เวลาทำการ</dt><dd>${esc(p.hours)}</dd>
      </dl>
      <h3>ราคารับซื้อล่าสุด</h3>
      <div class="tag-row">${Object.entries(p.prices).map(([k, v]) => `<span class="tag-chip"><b>${num(v, 2)}</b>${esc(mats[k].label)}</span>`).join('')}</div>
      ${p.kind === 'factory' ? `<p class="muted">ตามแผนวันนี้จะส่งให้ประมาณ <strong>${num(p.expected_kg, 1)} กก.</strong></p>` : ''}
      <form class="command" data-notice="${p.id}">
        <input type="text" value="${p.kind === 'factory' ? `วันนี้จะนำส่งประมาณ ${num(p.expected_kg, 1)} กก. ช่วงบ่าย รบกวนเตรียมลานรับ` : 'ขอราคารับซื้อล่าสุดของวันนี้'}" aria-label="ข้อความถึง${esc(p.name)}" maxlength="300">
        <button class="btn primary small" type="submit">ส่งแจ้ง</button>
      </form>
      ${notes.map((n) => `<div class="list-item"><span class="badge ${n.ack_at ? '' : 'warn'}">${n.ack_at ? `รับทราบ ${timeText(n.ack_at)}` : 'ยังไม่รับทราบ'}</span> ${esc(n.text)} <span class="muted">${timeText(n.created_at)}</span></div>`).join('')}
    </article>`;
  }).join('');
}
$('#partner-cards').addEventListener('submit', async (e) => {
  const form = e.target.closest('[data-notice]');
  if (!form) return;
  e.preventDefault();
  try {
    await api('/admin/notices', { partner_id: Number(form.dataset.notice), text: $('input', form).value });
    document.activeElement?.blur();
    await refresh();
    toast('ส่งข้อความถึงคู่ค้าแล้ว');
  } catch (err) { toast(err.message); }
});

// ---------- พอร์ทัลคู่ค้า ----------
function renderPortal() {
  if ($('#portal-body').contains(document.activeElement) && document.activeElement.tagName === 'INPUT') return;
  const p = S.me.partner, mats = S.config.materials;
  const waiting = S.notices.filter((n) => !n.ack_at).length;
  $('#portal-body').innerHTML = `
    <div class="hero partner"><div class="hero-text"><p class="eyebrow">${p.kind === 'factory' ? 'โรงงานรีไซเคิล' : 'ร้านรับซื้อของเก่า'}</p><h1>${esc(p.name)}</h1>
      <p class="hero-sub">รับ${p.accepts_label.join(' ')} · ${esc(p.hours)}</p></div>
      <div class="points"><b>${num(S.expected_kg, 1)}</b><small>กก. ที่คาดว่าจะได้รับวันนี้</small></div></div>
    <div class="card"><h2>ราคารับซื้อของฉันวันนี้</h2>
      <p class="muted">ราคาที่บันทึกจะขึ้นกระดานราคาทันที และผู้ดูแลระบบใช้เทียบกับคู่ค้ารายอื่น</p>
      ${Object.entries(p.prices).map(([k, v]) => `<form class="set-row" data-price="${k}"><div><strong><span class="dot mat-${k}"></span> ${esc(mats[k].label)}</strong></div>
        <span class="unit"><input type="number" min="0.01" step="0.01" value="${v}" aria-label="ราคารับซื้อ${esc(mats[k].label)}"><small>บาท/กก.</small></span>
        <button class="btn ghost small" type="submit">บันทึก</button></form>`).join('')}</div>
    <div class="card"><h2>ข้อความจากผู้ให้บริการ ${waiting ? `<span class="badge warn">รอรับทราบ ${waiting}</span>` : ''}</h2>
      ${S.notices.length ? S.notices.map((n) => `<div class="list-item"><div>${esc(n.text)}</div><div class="row between"><span class="muted">${timeText(n.created_at)}</span>
        ${n.ack_at ? `<span class="badge">รับทราบแล้ว ${timeText(n.ack_at)}</span>` : `<button type="button" class="btn primary small" data-ack="${n.id}">รับทราบ</button>`}</div></div>`).join('')
      : '<p class="muted">ยังไม่มีข้อความ</p>'}</div>`;
}
$('#portal-body').addEventListener('submit', async (e) => {
  const form = e.target.closest('[data-price]');
  if (!form) return;
  e.preventDefault();
  try {
    await api('/partner/prices', { material: form.dataset.price, price: Number($('input', form).value) });
    document.activeElement?.blur();
    priceData = null;
    await refresh();
    toast('บันทึกราคาแล้ว');
  } catch (err) { toast(err.message); }
});
$('#portal-body').addEventListener('click', async (e) => {
  const id = e.target.dataset.ack;
  if (!id) return;
  try { await api(`/partner/notices/${id}/ack`, {}); await refresh(); } catch (err) { toast(err.message); }
});

// ---------- คาร์บอน ----------
let carbonData = null, carbonAt = 0;
const hbars = (rows, unit) => { const max = Math.max(...rows.map((r) => r.value), 1e-9); return `<div class="hbars">${rows.map((r) => `<div class="hbar" title="${esc(r.label)}: ${num(r.value, 1)} ${unit}">
  <span class="hbar-label">${esc(r.label)}</span><span class="hbar-track"><span style="width:${Math.max(1, (r.value / max) * 100)}%"></span></span><b>${num(r.value, 1)}</b></div>`).join('')}</div>`; };

async function renderCarbon() {
  if (!carbonData || Date.now() - carbonAt > 15000) {
    try { carbonData = await api('/carbon'); carbonAt = Date.now(); } catch (e) { return toast(e.message); }
  }
  if ($('#carbon-body').contains(document.activeElement) && ['INPUT', 'SELECT'].includes(document.activeElement.tagName)) return;
  const c = carbonData, admin = S.me.role === 'admin', t = c.total, f = c.factors, fs = c.factor_source;
  const co2Rows = Object.entries(t.by_material).filter(([k]) => f[k]).map(([k, kg]) => ({ label: f[k].label, value: kg * f[k].kg_co2e_per_kg })).sort((a, b) => b.value - a.value);
  const maxMonth = Math.max(...c.monthly.map((m) => m.co2e_kg), 1e-9);
  const month = (m) => new Date(m + '-01T00:00:00').toLocaleDateString('th-TH', { month: 'short', year: '2-digit' });
  $('#carbon-body').innerHTML = `
    <div class="page-head"><div><h1>${admin ? 'คาร์บอนจากการรีไซเคิล' : 'สิ่งที่คุณช่วยลดได้'}</h1>
      <p class="muted">ประมาณการก๊าซเรือนกระจกที่หลีกเลี่ยงได้ จากน้ำหนักจริงที่คนขับชั่ง</p></div>
      ${admin ? '<a class="btn ghost small" href="/api/carbon.csv">ดาวน์โหลด CSV</a>' : ''}</div>
    <div class="stat-grid three">
      <div class="stat"><b>${num(t.kg, 1)} กก.</b><span>วัสดุที่ส่งรีไซเคิลแล้ว</span></div>
      <div class="stat accent"><b>${num(t.co2e_kg, 1)} kgCO2e</b><span>ที่หลีกเลี่ยงได้โดยประมาณ</span></div>
      <div class="stat"><b>${num(t.value_thb, 2)} บาท</b><span>มูลค่าเทียบเท่าที่ ${num(c.carbon_price_thb)} บาท/tCO2e</span></div></div>
    ${t.kg ? `<div class="card"><h2>แยกตามวัสดุ (kgCO2e)</h2>${hbars(co2Rows, 'kgCO2e')}</div>
      <div class="card"><h2>รายเดือน (kgCO2e)</h2><div class="cols">${c.monthly.map((m) => `<div class="col" title="${month(m.month)}: ${num(m.co2e_kg, 1)} kgCO2e จาก ${num(m.kg, 1)} กก.">
        <b>${num(m.co2e_kg)}</b><span style="height:${Math.max(2, (m.co2e_kg / maxMonth) * 100)}%"></span><small>${month(m.month)}</small></div>`).join('')}</div></div>`
      : '<div class="card"><p class="muted">ยังไม่มีของที่รับแล้ว ตัวเลขจะขึ้นหลังคนขับรับของครั้งแรก</p></div>'}
    ${admin ? `<div class="card"><h2>รายสมาชิก</h2><div class="table-wrap"><table><thead><tr><th>สมาชิก</th><th>ประเภท</th><th>ครั้งที่รับ</th><th>น้ำหนัก (กก.)</th><th>kgCO2e</th><th>มูลค่าเทียบเท่า (บาท)</th></tr></thead><tbody>
      ${c.members.map((m) => `<tr><td>${esc(m.name)}</td><td>${m.kind === 'company' ? '<span class="badge info">บริษัท</span>' : 'ครัวเรือน'}</td><td class="num">${num(m.pickups)}</td><td class="num">${num(m.kg, 1)}</td><td class="num">${num(m.co2e_kg, 1)}</td><td class="num">${num(m.value_thb, 2)}</td></tr>`).join('')}
      </tbody></table></div></div>` : ''}
    <div class="card"><h2>เครื่องคำนวณ</h2><p class="muted">ใส่น้ำหนักที่คาดว่าจะส่งรีไซเคิล เพื่อดูผลโดยประมาณก่อนทำสัญญารับกับบริษัท</p>
      <div class="calc">${Object.entries(f).map(([k, m]) => `<label><span><span class="dot mat-${k}"></span> ${esc(m.label)}</span><span class="unit"><input type="number" min="0" step="1" value="0" data-calc="${k}"><small>กก.</small></span></label>`).join('')}</div>
      <div class="totals" id="calc-out"></div></div>
    <div class="card"><h2>ที่มาของตัวเลข และข้อจำกัด</h2>
      <ul class="notes">
        <li>ปัจจัยที่ใช้อยู่มาจาก <strong>${esc(fs.source)}</strong>${fs.version ? ` (${esc(fs.version)})` : ''}${fs.reference_url ? ` <a href="${esc(fs.reference_url)}" target="_blank" rel="noopener">เอกสารอ้างอิง</a>` : ''}${fs.is_default ? ' ซึ่งเป็นค่าการปล่อยสุทธิของการรีไซเคิลของสหรัฐฯ ไม่ใช่ของไทย' : ` อัปเดตเมื่อ ${new Date(fs.updated_at * 1000).toLocaleString('th-TH')} โดย ${esc(fs.updated_by)}`}</li>
        <li>ตัวเลขนี้เป็นประมาณการสำหรับรายงานภายในและงาน ESG ยังไม่ใช่คาร์บอนเครดิตที่ซื้อขายได้</li>
        <li>การขอคาร์บอนเครดิต เช่น T-VER ของ อบก. ต้องขึ้นทะเบียนโครงการ ใช้ระเบียบวิธีที่รับรอง และผ่านการทวนสอบโดยผู้ประเมินภายนอก</li>
        <li>ราคาคาร์บอนที่ใช้ตีมูลค่าเป็นค่าสมมติ ผู้ดูแลระบบแก้ได้ที่หน้าเกณฑ์รับของ</li>
      </ul>
      <div class="table-wrap"><table><thead><tr><th>วัสดุ</th><th>kgCO2e ที่หลีกเลี่ยงได้ต่อ 1 กก.</th></tr></thead><tbody>
      ${Object.values(f).map((m) => `<tr><td>${esc(m.label)}</td><td class="num">${num(m.kg_co2e_per_kg, 2)}</td></tr>`).join('')}</tbody></table></div></div>
    ${admin ? carbonAdminHtml(c) : ''}`;
  calcCarbon();
}
let newToken = null;   // โทเคนที่เพิ่งสร้าง แสดงครั้งเดียวจนกว่าผู้ดูแลจะปิด

function carbonAdminHtml(c) {
  const fs = c.factor_source, origin = location.origin;
  const companies = S.members.filter((m) => m.kind === 'company');
  return `
    <div class="card"><h2>ค่าปัจจัยการปล่อย</h2>
      <p class="muted">ใส่ค่าที่ อบก. หรือแหล่งอื่นประกาศ เพื่อใช้แทนค่าตั้งต้น ค่าที่บันทึกมีผลกับการคำนวณทั้งระบบทันที และส่งเข้ามาผ่าน API ได้ด้วย</p>
      <form id="factor-form">
        <div class="form-grid">
          <label>ที่มาของค่า<input type="text" name="source" value="${fs.is_default ? '' : esc(fs.source)}" placeholder="เช่น อบก. (TGO)" required></label>
          <label>รุ่นหรือฉบับ<input type="text" name="version" value="${fs.is_default ? '' : esc(fs.version)}"></label>
          <label>ลิงก์เอกสารอ้างอิง<input type="text" name="reference_url" value="${fs.is_default ? '' : esc(fs.reference_url)}"></label>
          <label>วันที่มีผล<input type="text" name="effective_date" value="${fs.is_default ? '' : esc(fs.effective_date)}" placeholder="ปปปป-ดด-วว"></label>
        </div>
        <div class="calc">${Object.entries(c.factors).map(([k, m]) => `<label><span><span class="dot mat-${k}"></span> ${esc(m.label)}</span><span class="unit"><input type="number" min="0" max="100" step="0.001" name="f:${k}" value="${m.kg_co2e_per_kg}"><small>kgCO2e/กก.</small></span></label>`).join('')}</div>
        <div class="row"><button class="btn primary" type="submit">บันทึกค่าปัจจัย</button>
          ${fs.is_default ? '' : '<button class="btn ghost" type="button" data-factor-reset>กลับไปใช้ค่าตั้งต้น</button>'}</div>
      </form></div>
    <div class="card"><h2>API สำหรับระบบภายนอก</h2>
      <p class="muted">ระบบอื่นดึงข้อมูลคาร์บอน หรือส่งค่าปัจจัยเข้ามาได้ ด้วยโทเคนของระบบในส่วนหัว <code>Authorization: Bearer</code></p>
      <div class="table-wrap"><table><thead><tr><th>เส้นทาง</th><th>สิทธิ์</th><th>ใช้ทำอะไร</th></tr></thead><tbody>
        <tr><td><code>GET /api/v1/carbon/summary</code></td><td>carbon:read</td><td>ยอดรวม รายเดือน และรายสมาชิก</td></tr>
        <tr><td><code>GET /api/v1/carbon/members/{id}</code></td><td>carbon:read</td><td>ข้อมูลของสมาชิกรายเดียว</td></tr>
        <tr><td><code>GET /api/v1/carbon/factors</code></td><td>carbon:read</td><td>ค่าปัจจัยที่ใช้อยู่และที่มา</td></tr>
        <tr><td><code>PUT /api/v1/carbon/factors</code></td><td>carbon:write</td><td>ส่งค่าปัจจัยชุดใหม่เข้ามา เช่น ค่าจาก อบก.</td></tr>
        <tr><td><code>DELETE /api/v1/carbon/factors</code></td><td>carbon:write</td><td>กลับไปใช้ค่าตั้งต้น</td></tr>
      </tbody></table></div>
      <pre class="code-block">curl -H "Authorization: Bearer &lt;โทเคน&gt;" ${origin}/api/v1/carbon/summary

curl -X PUT ${origin}/api/v1/carbon/factors \\
  -H "Authorization: Bearer &lt;โทเคน&gt;" -H "Content-Type: application/json" \\
  -d '{"source": "อบก. (TGO)", "version": "2569", "factors": {"pet": 1.2, "cardboard": 3.1}}'</pre>
      <h3>โทเคนของระบบ</h3>
      ${newToken ? `<div class="notice ok"><strong>คัดลอกโทเคนนี้ตอนนี้ ระบบจะไม่แสดงอีก</strong><br><code class="token">${esc(newToken)}</code>
        <div class="row" style="margin-top:.4rem"><button type="button" class="btn ghost small" data-token-copy>คัดลอก</button><button type="button" class="btn ghost small" data-token-hide>ปิด</button></div></div>` : ''}
      <form id="token-form" class="form-grid">
        <label>ชื่อโทเคน<input type="text" name="name" placeholder="เช่น ระบบ ESG ของบริษัท" required maxlength="60"></label>
        <label>สิทธิ์<select name="scope"><option value="read">อ่านข้อมูลคาร์บอน</option><option value="write">อ่าน และส่งค่าปัจจัยเข้ามา</option></select></label>
        <label>ขอบเขตข้อมูล<select name="member"><option value="">ทุกสมาชิก</option>${companies.map((m) => `<option value="${m.id}">เฉพาะ ${esc(m.name)}</option>`).join('')}</select></label>
        <button class="btn primary" type="submit">สร้างโทเคน</button>
      </form>
      ${S.tokens.length ? `<div class="table-wrap"><table><thead><tr><th>ชื่อ</th><th>ขึ้นต้นด้วย</th><th>สิทธิ์</th><th>ขอบเขต</th><th>ใช้ล่าสุด</th><th></th></tr></thead><tbody>
        ${S.tokens.map((t) => `<tr><td>${esc(t.name)}</td><td><code>${esc(t.prefix)}…</code></td><td>${t.scopes.map((x) => `<span class="badge gray">${esc(x)}</span>`).join(' ')}</td>
          <td>${t.member_name ? esc(t.member_name) : 'ทุกสมาชิก'}</td><td>${t.last_used_at ? new Date(t.last_used_at * 1000).toLocaleString('th-TH') : 'ยังไม่เคยใช้'}</td>
          <td>${t.revoked_at ? '<span class="badge warn">ยกเลิกแล้ว</span>' : `<button type="button" class="btn ghost small" data-token-revoke="${t.id}">ยกเลิก</button>`}</td></tr>`).join('')}
      </tbody></table></div>` : '<p class="muted">ยังไม่มีโทเคน</p>'}
    </div>`;
}

async function reloadCarbon() { carbonData = null; document.activeElement?.blur(); await refresh(); await renderCarbon(); }

$('#carbon-body').addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = new FormData(e.target);
  try {
    if (e.target.id === 'factor-form') {
      const factors = {};
      for (const [k, v] of data) if (k.startsWith('f:')) factors[k.slice(2)] = Number(v);
      await api('/v1/carbon/factors', { source: data.get('source'), version: data.get('version'), reference_url: data.get('reference_url'), effective_date: data.get('effective_date'), factors }, 'PUT');
      toast('บันทึกค่าปัจจัยแล้ว การคำนวณทั้งระบบใช้ค่าชุดนี้');
    } else if (e.target.id === 'token-form') {
      const res = await api('/admin/tokens', { name: data.get('name'), scopes: data.get('scope') === 'write' ? ['carbon:read', 'carbon:write'] : ['carbon:read'], member_id: data.get('member') ? Number(data.get('member')) : null });
      newToken = res.token;
      toast('สร้างโทเคนแล้ว คัดลอกเก็บไว้ทันที');
    }
    await reloadCarbon();
  } catch (err) { toast(err.message); }
});
$('#carbon-body').addEventListener('click', async (e) => {
  const d = e.target.dataset;
  try {
    if (d.tokenRevoke) { if (!confirm('ยกเลิกโทเคนนี้ใช่ไหม ระบบที่ใช้โทเคนนี้จะเรียก API ไม่ได้ทันที')) return; await api(`/admin/tokens/${d.tokenRevoke}/revoke`, {}); await reloadCarbon(); }
    else if (d.tokenHide !== undefined) { newToken = null; await reloadCarbon(); }
    else if (d.tokenCopy !== undefined) { await navigator.clipboard.writeText(newToken); toast('คัดลอกโทเคนแล้ว'); }
    else if (d.factorReset !== undefined) { await api('/v1/carbon/factors', {}, 'DELETE'); toast('กลับไปใช้ค่าตั้งต้นแล้ว'); await reloadCarbon(); }
  } catch (err) { toast(err.message); }
});

function calcCarbon() {
  if (!carbonData) return;
  let kg = 0, co2 = 0;
  for (const el of document.querySelectorAll('[data-calc]')) { const v = Math.max(0, Number(el.value) || 0); kg += v; co2 += v * carbonData.factors[el.dataset.calc].kg_co2e_per_kg; }
  $('#calc-out').innerHTML = `<div><b>${num(kg, 1)}</b><span>กก. รวม</span></div><div><b>${num(co2, 1)}</b><span>kgCO2e</span></div>
    <div><b>${num(co2 / 1000, 3)}</b><span>tCO2e</span></div><div><b>${num((co2 / 1000) * carbonData.carbon_price_thb, 2)}</b><span>บาท เทียบเท่า</span></div>`;
}
$('#carbon-body').addEventListener('input', (e) => { if (e.target.dataset.calc) calcCarbon(); });

// ---------- แผนที่เส้นทางของคนขับ ----------
let drvMap, drvLayer, drvSel = null, drvFit = '', drvStops = [];
const tiles = () => L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' });

function renderDriverMap(stops, nextId) {
  drvStops = stops;
  const depot = S.config.depot;
  if (!drvMap) {
    drvMap = L.map('driver-map', { zoomControl: false }).setView([depot.lat, depot.lng], 13);
    tiles().addTo(drvMap);
    drvLayer = L.layerGroup().addTo(drvMap);
  }
  drvMap.invalidateSize();
  drvLayer.clearLayers();
  const pts = [[depot.lat, depot.lng], ...stops.map((s) => [s.r.lat, s.r.lng]), [depot.lat, depot.lng]];
  if (stops.length) L.polyline(pts, { color: '#059669', weight: 4, opacity: 0.85, lineJoin: 'round' }).addTo(drvLayer);
  if (!stops.some((s) => s.r.id === drvSel)) drvSel = nextId ?? null;
  stops.forEach((s, n) => {
    const r = s.r, cls = `${isDone(r) ? 'done' : ''} ${r.status === 'verified' ? 'here' : ''} ${r.id === drvSel ? 'sel' : ''}`;
    const color = isDone(r) ? '#94a3b8' : r.id === nextId ? '#059669' : '#0f1f1a';
    L.marker([r.lat, r.lng], { icon: pinIcon(isDone(r) ? '✓' : n + 1, color, cls), title: `จุดที่ ${n + 1} ${r.member_name}` }).addTo(drvLayer)
      .on('click', () => { drvSel = r.id; renderDriverMap(drvStops, nextId); });
  });
  L.marker([depot.lat, depot.lng], { icon: pinIcon('ศ', '#0f1f1a', 'depot'), title: depot.name }).addTo(drvLayer);
  const key = `${stops.map((s) => s.r.id).join(',')}:${drvMap.getSize().x}`;
  if (key !== drvFit) { drvMap.fitBounds(pts, { padding: [28, 28] }); drvFit = key; }

  const idx = stops.findIndex((s) => s.r.id === drvSel), s = stops[idx];
  $('#driver-sheet').innerHTML = !s ? `<p class="muted">${stops.length ? 'แตะหมุดบนแผนที่เพื่อดูรายละเอียดของจุดนั้น' : 'ยังไม่มีจุดรับในรอบนี้'}</p>` : `
    <div class="sheet-head"><span class="seq-badge">${idx + 1}</span><div class="grow"><strong>${esc(s.r.member_name)}</strong>
      <span class="muted">ถึงประมาณ ${hhmm(s.eta)} · นัด ${esc(slotLabel(s.r.slot))}</span></div>${s.r.status === 'pending' ? '' : statusTag(s.r)}</div>
    <p class="muted">${esc(s.r.address)} · ${num(s.r.bags.length)} ถุง · ${num(s.r.total_count)} ชิ้น · ประมาณ ${num(s.r.est_kg, 1)} กก.</p>
    <div class="row">${isOpen(s.r) ? `<button type="button" class="btn primary small" data-nav="${s.r.id}">${ic('nav', 15)} นำทาง</button>` : ''}
      ${s.r.status === 'pending' ? `<button type="button" class="btn ghost small" data-arrive="${s.r.id}">${ic('qr', 15)} ถึงแล้ว สแกน QR</button>` : ''}
      <button type="button" class="btn ghost small" data-goto="${s.r.id}">ดูในรายการ</button></div>`;
}
$('#driver-sheet').addEventListener('click', (e) => {
  const d = e.target.closest('button')?.dataset;
  if (!d) return;
  if (d.nav) openNav(Number(d.nav));
  else if (d.arrive) startScan(Number(d.arrive));
  else if (d.goto) $(`#stop-${d.goto}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
});
function startScan(id) {
  stopCamera(); scanFor = id; renderDriver();
  $(`#stop-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ---------- โหมดนำทาง ----------
let navMap, navLayer, navBounds = null, navToken = 0;
const haversineKm = (a, b) => {
  const rad = Math.PI / 180, dLat = (b.lat - a.lat) * rad, dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
};

// เส้นทางตามถนนจากบริการ OSRM สาธารณะ ถ้าปิดไว้ในเกณฑ์ หรือเรียกไม่ได้ภายใน 3.5 วินาที จะคืน null แล้วใช้เส้นตรงแทน
async function roadRoute(a, b) {
  if (!S.config.road_routing) return null;
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 3500);
  try {
    const res = await fetch(`https://router.project-osrm.org/route/v1/driving/${a.lng},${a.lat};${b.lng},${b.lat}?overview=full&geometries=geojson`, { signal: ctl.signal });
    const r = (await res.json()).routes?.[0];
    return r ? { line: r.geometry.coordinates.map(([x, y]) => [y, x]), km: r.distance / 1000, min: r.duration / 60 } : null;
  } catch { return null; } finally { clearTimeout(timer); }
}

async function openNav(target) {
  const depot = S.config.depot, toDepot = target === 'depot';
  const idx = toDepot ? drvStops.length : drvStops.findIndex((s) => s.r.id === target);
  const stop = toDepot ? null : drvStops[idx];
  if (!toDepot && !stop) return;
  const dest = toDepot ? { lat: depot.lat, lng: depot.lng } : { lat: stop.r.lat, lng: stop.r.lng };
  const prev = drvStops[idx - 1];
  let origin = prev ? { lat: prev.r.lat, lng: prev.r.lng } : { lat: depot.lat, lng: depot.lng };
  let originLabel = prev ? `จุดก่อนหน้า (${prev.r.member_name})` : depot.name;
  const token = ++navToken;

  const el = $('#nav');
  el.hidden = false;
  requestAnimationFrame(() => el.classList.add('open'));
  $('#nav-title').textContent = toDepot ? depot.name : `จุดที่ ${idx + 1} · ${stop.r.member_name}`;
  if (!navMap) {
    navMap = L.map('nav-map', { zoomControl: false }).setView([dest.lat, dest.lng], 15);
    tiles().addTo(navMap);
    navLayer = L.layerGroup().addTo(navMap);
  }
  const draw = (line, dashed) => {
    navLayer.clearLayers();
    L.polyline(line, { color: '#fff', weight: 9, opacity: 0.9, lineJoin: 'round' }).addTo(navLayer);   // ขอบขาวให้เส้นเด่นบนแผนที่
    L.polyline(line, { color: '#10b981', weight: 5, lineJoin: 'round', dashArray: dashed ? '2 10' : null }).addTo(navLayer);
    L.marker([origin.lat, origin.lng], { icon: L.divIcon({ className: '', html: '<div class="car-pin"></div>', iconSize: [30, 30], iconAnchor: [15, 15] }), title: originLabel }).addTo(navLayer);
    L.marker([dest.lat, dest.lng], { icon: L.divIcon({ className: '', html: '<div class="dest-pin"><span></span></div>', iconSize: [44, 44], iconAnchor: [22, 22] }), title: 'ปลายทาง' }).addTo(navLayer);
    navBounds = L.latLngBounds(line);
    navMap.invalidateSize();
    navMap.fitBounds(navBounds, { paddingTopLeft: [30, 90], paddingBottomRight: [30, 30] });
  };
  const sheet = (km, min, source) => {
    const eta = new Date(Date.now() + min * 60000).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' });
    $('#nav-sheet').innerHTML = `
      <div class="nav-metrics"><div><b>${num(min)} นาที</b><span>ถึงประมาณ ${eta}</span></div><div><b>${num(km, 1)} กม.</b><span>${source}</span></div>
        ${stop ? `<div><b>${num(stop.r.bags.length)} ถุง</b><span>ประมาณ ${num(stop.r.est_kg, 1)} กก.</span></div>` : ''}</div>
      <p><strong>${toDepot ? esc(depot.name) : esc(stop.r.member_name)}</strong> <span class="muted">${toDepot ? 'ส่งของเพื่อปิดรอบ' : `${esc(stop.r.address)} · นัด ${esc(slotLabel(stop.r.slot))}`}</span></p>
      ${stop ? `<div class="tag-row">${tagChips(stop.r)}</div>` : ''}
      <p class="muted">ออกจาก ${esc(originLabel)}</p>
      <div class="row">
        ${stop && stop.r.status === 'pending' ? `<button type="button" class="btn primary" data-arrive="${stop.r.id}">${ic('qr', 16)} ถึงแล้ว สแกน QR</button>` : ''}
        <a class="btn ghost" href="https://www.google.com/maps/dir/?api=1&destination=${dest.lat},${dest.lng}" target="_blank" rel="noopener">เปิดใน Google Maps</a>
        ${stop?.r.member_phone ? `<a class="btn ghost" href="tel:${esc(stop.r.member_phone.replace(/[^0-9+]/g, ''))}">โทรหาลูกค้า</a>` : ''}
      </div>`;
  };
  const straight = () => { const km = haversineKm(origin, dest) * 1.35; return { line: [[origin.lat, origin.lng], [dest.lat, dest.lng]], km, min: (km / 22) * 60 }; };

  let r = straight();
  setTimeout(() => { if (token === navToken) draw(r.line, true); }, 60);   // รอให้แผ่นนำทางเริ่มเลื่อนขึ้นก่อน แผนที่จึงรู้ขนาดจริง
  sheet(r.km, r.min, 'กำลังหาเส้นทาง…');
  // ถ้าอุปกรณ์ให้ตำแหน่งได้และอยู่ในระยะที่สมเหตุสมผล ใช้เป็นจุดเริ่มต้นแทน
  const pos = await driverPosition();
  if (token !== navToken) return;
  if (pos && haversineKm(pos, dest) < 60) { origin = pos; originLabel = 'ตำแหน่งปัจจุบันของคุณ'; r = straight(); }
  const road = await roadRoute(origin, dest);
  if (token !== navToken) return;
  if (road) r = road;
  draw(r.line, !road);
  sheet(r.km, r.min, road ? 'ตามถนน' : S.config.road_routing ? 'เส้นตรงโดยประมาณ (หาเส้นทางตามถนนไม่ได้)' : 'เส้นตรงโดยประมาณ');
}

function closeNav(now) {
  navToken += 1;
  const el = $('#nav');
  el.classList.remove('open');
  if (now) el.hidden = true; else setTimeout(() => { if (!el.classList.contains('open')) el.hidden = true; }, 300);
}
$('#nav-back').addEventListener('click', () => closeNav());
$('#nav-recenter').addEventListener('click', () => { if (navBounds) navMap.fitBounds(navBounds, { paddingTopLeft: [30, 90], paddingBottomRight: [30, 30] }); });
$('#nav-sheet').addEventListener('click', (e) => { const b = e.target.closest('[data-arrive]'); if (b) { closeNav(); startScan(Number(b.dataset.arrive)); } });

// ---------- เริ่มทำงาน ----------
(async () => {
  try { await enterApp(); } catch { toast('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้'); }
  // ดึงข้อมูลใหม่เป็นระยะ เพื่อให้เห็นงานที่เพิ่งแจ้งเข้ามา
  setInterval(() => { if (entered && !document.hidden) refresh().catch(() => {}); }, 4000);
})();
