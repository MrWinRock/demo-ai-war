'use strict';

// ---------- ตัวช่วย ----------
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const hhmm = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const num = (n, d = 0) => Number(n || 0).toLocaleString('th-TH', { maximumFractionDigits: d });
const coordText = (lat, lng) => `${Number(lat).toFixed(5)}, ${Number(lng).toFixed(5)}`;
const mapsUrl = (lat, lng) => `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
const coordLink = (lat, lng) => `<a class="coords" href="${mapsUrl(lat, lng)}" target="_blank" rel="noopener">${coordText(lat, lng)}</a>`;
const timeText = (ts) => new Date(ts * 1000).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' });

async function api(path, body) {
  const opts = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  const res = await fetch('/api' + path, opts);
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).detail; } catch { /* ไม่มีรายละเอียด */ }
    throw new Error(typeof detail === 'string' && detail ? detail : 'เกิดข้อผิดพลาด ลองใหม่อีกครั้ง');
  }
  return res.json();
}

let toastTimer;
function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}

// ---------- สถานะของหน้า ----------
let S = null;            // ข้อมูลล่าสุดจากเซิร์ฟเวอร์
let lastJson = '';
let view = 'member';
let draft = null;        // ผลจาก AI ที่สมาชิกแก้ไขได้ก่อนส่ง
let photoThumb = '';     // รูปย่อที่บันทึกไปกับคำขอ
let slot = null;
let pin = null;          // {lat, lng} จุดรับ
let pinMap, pinMarker, dMap, dLayer;
let dFitted = '';      // ขนาดแผนที่ตอนจัดมุมมองครั้งล่าสุด

const material = (key) => S.config.materials[key] || { label: key, price: 0 };
const itemsText = (items) => items.filter((i) => i.material !== 'non_recyclable').map((i) => `${esc(i.name_th)} ${num(i.count)} ชิ้น`).join(', ');

// สถานะของคำขอ: pending รอรับ -> verified คนขับสแกน QR ยืนยันจุดแล้ว -> collected รับของแล้ว -> delivered ส่งถึงศูนย์แล้ว
const isOpen = (r) => r.status === 'pending' || r.status === 'verified';
const isDone = (r) => r.status === 'collected' || r.status === 'delivered';
const sumCount = (items) => items.reduce((a, i) => a + (i.material === 'non_recyclable' ? 0 : Number(i.count) || 0), 0);

function statusText(r, st) {
  if (r.status === 'delivered') return 'ส่งถึงศูนย์คัดแยกแล้ว';
  if (r.status === 'collected') return 'รับของแล้ว';
  if (r.status === 'verified') return 'คนขับถึงจุดแล้ว กำลังตรวจของ';
  return st ? `${st.name} จุดที่ ${st.seq}` : 'ยังจัดรถไม่ลง';
}

function statusTag(r, st) {
  if (isDone(r)) return `<span class="tag gray">${statusText(r)} ${num(r.actual_kg, 1)} กก.</span>`;
  if (r.status === 'verified') return `<span class="tag here">${statusText(r)}</span>`;
  return st ? `<span class="tag">${esc(st.name)} ถึงประมาณ ${hhmm(st.eta)}</span>` : '<span class="tag warn">รอจัดรถ</span>';
}

// QR ของแต่ละคำขอ โหลดเมื่อสมาชิกเปิดดู แล้วเก็บไว้ใช้ซ้ำ
const tickets = {};
const openTickets = new Set();
function ticketHtml(id) {
  const t = tickets[id];
  if (!t) return '<p class="loading">กำลังโหลด QR…</p>';
  return `<div class="qr">${t.svg}</div><p>รหัส <strong class="code">${esc(t.code)}</strong></p>
    <p class="muted">แสดง QR นี้ให้คนขับสแกนเมื่อมาถึง หรือบอกรหัสแทนได้</p>`;
}

function stopIndex() {
  const idx = {};
  for (const route of S.plan?.routes || []) {
    route.stops.forEach((s, n) => { idx[s.request_id] = { seq: n + 1, eta: s.eta, name: route.name, color: route.color, vehicle_id: route.vehicle_id }; });
  }
  return idx;
}

async function refresh() {
  const res = await fetch('/api/state');
  const text = await res.text();
  if (text === lastJson) return;
  lastJson = text;
  S = JSON.parse(text);
  renderAll();
}

function renderAll() {
  const badge = $('#ai-badge');
  badge.textContent = S.ai_mode === 'claude' ? 'AI: Claude Vision' : 'AI: โหมดจำลอง';
  badge.classList.toggle('mock', S.ai_mode !== 'claude');
  renderMember();
  if (view === 'dispatch') renderDispatch();
  if (view === 'driver' && !driverBusy()) renderDriver();
  if (view === 'records') renderRecords();
}

// ---------- สมาชิก ----------
const currentMember = () => S.members.find((m) => m.id === Number($('#member-select').value)) || S.members[0];

function renderMember() {
  const sel = $('#member-select');
  if (sel.options.length !== S.members.length) {
    const keep = sel.value;
    sel.innerHTML = S.members.map((m) => `<option value="${m.id}">${esc(m.name)} · ${esc(m.address)}</option>`).join('');
    if (keep) sel.value = keep;
  }
  const me = currentMember();
  $('#member-points').textContent = num(me.points);

  if (!$('#slot-chips').children.length) {
    $('#slot-chips').innerHTML = S.config.slots.map((s) => `<button type="button" class="chip" data-slot="${s.id}">${esc(s.label)}</button>`).join('');
  }
  if (!pinMap) initPinMap(me);

  const idx = stopIndex();
  const mine = S.requests.filter((r) => r.member_id === me.id).reverse();
  $('#my-requests').innerHTML = mine.length ? mine.map((r) => {
    const st = idx[r.id];
    const qr = isOpen(r)
      ? `<details class="ticket" data-ticket="${r.id}" ${openTickets.has(r.id) ? 'open' : ''}><summary>QR สำหรับให้คนขับสแกน</summary><div class="qr-box">${ticketHtml(r.id)}</div></details>` : '';
    return `<div class="list-item"><strong>#${r.id}</strong> ${statusTag(r, st)}<br>${itemsText(r.items)} · รวม ${num(r.total_count)} ชิ้น<br>
      <span class="muted">พิกัด ${coordLink(r.lat, r.lng)} · นัด ${esc(slotLabel(r.slot))}</span>${qr}</div>`;
  }).join('') : '<p class="muted">ยังไม่มีคำขอ</p>';
}

const slotLabel = (id) => (S.config.slots.find((s) => s.id === id) || {}).label || id;

function initPinMap(me) {
  pin = { lat: me.lat, lng: me.lng };
  pinMap = L.map('pinmap').setView([pin.lat, pin.lng], 15);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(pinMap);
  pinMarker = L.marker([pin.lat, pin.lng], { draggable: true }).addTo(pinMap);
  pinMarker.on('dragend', () => { const p = pinMarker.getLatLng(); setPin(p.lat, p.lng, false); });
  pinMap.on('click', (e) => setPin(e.latlng.lat, e.latlng.lng, false));
  setPin(pin.lat, pin.lng, false);
}

function setPin(lat, lng, recenter = true) {
  pin = { lat, lng };
  pinMarker.setLatLng([lat, lng]);
  if (recenter) pinMap.setView([lat, lng], 16);
  $('#pin-coords').textContent = coordText(lat, lng);
}

function estimateLocal() {
  // สูตรเดียวกับ app/estimate.py: น้ำหนัก = จำนวนชิ้น x น้ำหนักเฉลี่ยต่อชิ้นของวัสดุ
  let total = 0, kg = 0, value = 0;
  for (const i of draft?.items || []) {
    const c = Math.max(0, parseInt(i.count, 10) || 0);
    const m = material(i.material);
    if (!m.unit_kg || c === 0) continue;
    total += c;
    kg += c * m.unit_kg;
    value += c * m.unit_kg * m.price;
  }
  return { total, kg, value };
}

function renderDraft(state) {
  const box = $('#ai-result');
  if (state === 'loading') { box.innerHTML = '<p class="loading">AI กำลังแยกชนิดและนับจำนวน…</p>'; updateSubmit(); return; }
  if (!draft) { box.innerHTML = ''; updateSubmit(); return; }

  const conf = { high: 'มั่นใจสูง', medium: 'มั่นใจปานกลาง', low: 'มั่นใจต่ำ ช่วยตรวจจำนวนอีกครั้ง' }[draft.confidence] || '';
  const rows = draft.items.map((i, n) => {
    const rejected = i.material === 'non_recyclable';
    return `<li class="${rejected ? 'rejected' : ''}">
      <div><div class="name">${esc(i.name_th)}</div>
        <span class="tag ${rejected ? 'warn' : ''}">${esc(material(i.material).label)}</span>
        ${i.prep_tip_th ? `<div class="tip">${esc(i.prep_tip_th)}</div>` : ''}</div>
      <div class="count">${rejected ? `<span>${num(i.count)} ชิ้น</span>`
        : `<input type="number" min="0" inputmode="numeric" value="${Number(i.count) || 0}" data-item="${n}" aria-label="จำนวน ${esc(i.name_th)}"><span>ชิ้น</span>`}</div>
    </li>`;
  }).join('');

  box.innerHTML = `
    ${draft.warning ? `<div class="notice">${esc(draft.warning)}</div>` : ''}
    <p>${esc(draft.summary_th)} ${conf ? `<span class="tag gray">${conf}</span>` : ''}</p>
    ${draft.items.length ? `<ul class="items">${rows}</ul><p class="muted">แก้จำนวนได้ถ้า AI นับไม่ตรง</p>` : ''}
    <p class="muted">ขนาดกอง ใช้จองพื้นที่บนรถ</p>
    <div class="chips">${Object.entries(S.config.sizes).map(([k, v]) => `<button type="button" class="chip ${k === draft.size ? 'active' : ''}" data-size="${k}">${esc(v.label)}</button>`).join('')}</div>
    <div id="draft-totals" class="totals"></div>`;
  renderTotals();
}

function renderTotals() {
  const e = estimateLocal();
  $('#draft-totals').innerHTML = `
    <div class="stat"><b>${num(e.total)}</b><span>ชิ้นที่รับได้</span></div>
    <div class="stat"><b>${num(e.kg, 1)} กก.</b><span>น้ำหนักประมาณ</span></div>
    <div class="stat"><b>${num(e.value, 1)} บาท</b><span>มูลค่าประมาณ</span></div>`;
  updateSubmit();
}

function updateSubmit() {
  $('#submit-request').disabled = !(draft && slot && pin && estimateLocal().total > 0);
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('เปิดรูปนี้ไม่ได้ ลองใช้ไฟล์ JPG หรือ PNG')); };
    img.src = url;
  });
}

function scaled(img, max, quality) {
  const k = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight));
  const c = document.createElement('canvas');
  c.width = Math.round(img.naturalWidth * k);
  c.height = Math.round(img.naturalHeight * k);
  c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL('image/jpeg', quality);
}

async function handlePhoto(file) {
  $('#submit-result').innerHTML = '';
  draft = null;
  try {
    const img = await loadImage(file);
    const full = scaled(img, 1280, 0.85);   // ส่งให้ AI
    photoThumb = scaled(img, 320, 0.7);     // เก็บเป็นหลักฐานกับคำขอ
    const prev = $('#photo-preview');
    prev.hidden = false;
    prev.innerHTML = `<img src="${full}" alt="รูปที่แนบ">`;
    renderDraft('loading');
    const res = await api('/classify', { image_b64: full.split(',')[1], media_type: 'image/jpeg' });
    draft = { ...res, items: res.items.map((i) => ({ ...i, ai_count: i.count })) };
    renderDraft();
  } catch (err) {
    draft = null;
    renderDraft();
    $('#ai-result').innerHTML = `<div class="notice">${esc(err.message)}</div>`;
  }
}

async function submitRequest() {
  const btn = $('#submit-request');
  btn.disabled = true;
  try {
    const me = currentMember();
    const items = draft.items
      .map((i) => ({ name_th: i.name_th, material: i.material, count: Math.max(0, parseInt(i.count, 10) || 0), ai_count: i.ai_count, prep_tip_th: i.prep_tip_th }))
      .filter((i) => i.count > 0);
    const res = await api('/requests', { member_id: me.id, lat: pin.lat, lng: pin.lng, slot, size: draft.size, items, photo: photoThumb });
    const r = res.request;
    try { tickets[r.id] = await api(`/requests/${r.id}/ticket`); } catch { /* เปิดดู QR ได้จากรายการคำขอ */ }
    $('#submit-result').innerHTML = `<div class="notice ok">
      <strong>แจ้งรับเรียบร้อย เลขที่ #${r.id}</strong><br>
      พิกัด ${coordLink(r.lat, r.lng)}<br>
      จำนวน ${itemsText(r.items)} รวม ${num(r.total_count)} ชิ้น<br>
      ${res.stop ? `${esc(res.stop.vehicle)} จะถึงประมาณ ${hhmm(res.stop.eta)} (จุดที่ ${res.stop.seq} ของรอบ)` : 'ช่วงเวลานี้ยังจัดรถไม่ลง ผู้จัดรถจะติดต่อกลับ'}
      ${tickets[r.id] ? `<div class="qr-box">${ticketHtml(r.id)}</div>` : ''}
    </div>`;
    draft = null; photoThumb = '';
    $('#photo-preview').hidden = true;
    $('#photo-preview').innerHTML = '';
    renderDraft();
    await refresh();
  } catch (err) {
    toast(err.message);
    updateSubmit();
  }
}

// ---------- ผู้จัดรถ ----------
function pinIcon(text, color, cls = '') {
  return L.divIcon({ className: '', html: `<div class="pin ${cls}" style="background:${color}">${esc(text)}</div>`, iconSize: [26, 26], iconAnchor: [13, 13] });
}

function renderDispatch() {
  if (!dMap) {
    dMap = L.map('dispatch-map').setView([S.config.depot.lat, S.config.depot.lng], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(dMap);
    dLayer = L.layerGroup().addTo(dMap);
  }
  dMap.invalidateSize();
  dLayer.clearLayers();

  const depot = S.config.depot;
  const plan = S.plan || { routes: [], unassigned: [], factory_kg: [] };
  const idx = stopIndex();
  const byId = Object.fromEntries(S.requests.map((r) => [r.id, r]));
  const bounds = [[depot.lat, depot.lng]];
  const now = Date.now() / 1000;

  for (const route of plan.routes) {
    const path = [[depot.lat, depot.lng], ...route.stops.map((s) => [byId[s.request_id].lat, byId[s.request_id].lng]), [depot.lat, depot.lng]];
    if (route.stops.length) L.polyline(path, { color: route.color, weight: 4, opacity: 0.75 }).addTo(dLayer);
  }
  for (const r of S.requests) {
    const st = idx[r.id];
    const done = isDone(r);
    const here = r.status === 'verified';
    const fresh = now - r.created_at < 90 ? 'new' : '';
    const icon = done ? pinIcon('✓', '#94a3b8', 'done') : st ? pinIcon(st.seq, st.color, `${fresh} ${here ? 'here' : ''}`) : pinIcon('!', '#b91c1c', fresh);
    const where = done ? `${statusText(r)} ${num(r.actual_kg, 1)} กก.` : here ? statusText(r) : st ? `${esc(st.name)} · ถึงประมาณ ${hhmm(st.eta)}` : 'ยังจัดรถไม่ลง';
    L.marker([r.lat, r.lng], { icon }).addTo(dLayer).bindPopup(
      `<strong>#${r.id} ${esc(r.member_name)}</strong><br>${where}<br>นัด ${esc(slotLabel(r.slot))}<br>
       ${itemsText(r.items)}<br>รวม ${num(r.total_count)} ชิ้น · ประมาณ ${num(r.est_kg, 1)} กก.<br>พิกัด ${coordLink(r.lat, r.lng)}`);
    bounds.push([r.lat, r.lng]);
  }
  L.marker([depot.lat, depot.lng], { icon: pinIcon('ศ', '#0f172a', 'depot') }).addTo(dLayer).bindPopup(esc(depot.name));
  // จัดมุมมองให้เห็นทุกหมุดครั้งแรก และจัดใหม่เมื่อขนาดแผนที่เปลี่ยน (เช่น หมุนจอหรือย่อขยายหน้าต่าง)
  const box = dMap.getSize();
  const fitKey = `${box.x}x${box.y}`;
  if (dFitted !== fitKey) { dMap.fitBounds(bounds, { padding: [24, 24] }); dFitted = fitKey; }

  const pending = S.requests.filter(isOpen);
  const stops = plan.routes.reduce((a, r) => a + r.stops.length, 0);
  $('#plan-stats').innerHTML = `
    <div class="stat"><b>${num(stops)}/${num(pending.length)}</b><span>จุดที่จัดลงรถ</span></div>
    <div class="stat"><b>${num(plan.total_km, 1)} กม.</b><span>ระยะทางรวม</span></div>
    <div class="stat"><b>${plan.baseline_km > 0 ? num(plan.saving_pct) + '%' : '–'}</b><span>สั้นกว่าวิ่งตามลำดับแจ้ง</span></div>
    <div class="stat"><b>${num(pending.reduce((a, r) => a + r.total_count, 0))}</b><span>ชิ้นที่รอรับ</span></div>`;
  $('#plan-summary').textContent = plan.summary || '';

  const routeOf = Object.fromEntries(plan.routes.map((r) => [r.vehicle_id, r]));
  $('#vehicle-list').innerHTML = S.vehicles.map((v) => {
    const r = routeOf[v.id];
    const info = !v.active ? '<span class="tag warn">หยุดใช้งาน</span>'
      : r && r.stops.length ? `${r.stops.length} จุด · ${num(r.km, 1)} กม. · ใช้พื้นที่ ${num(r.load_units)}/${num(v.capacity_units)} ถุง · ประมาณ ${num(r.load_kg, 1)} กก. · กลับถึงศูนย์ ${hhmm(r.back_at)}`
      : 'ไม่มีงาน';
    return `<div class="list-item"><span class="dot" style="background:${esc(v.color)}"></span><strong>${esc(v.name)}</strong><br><span class="muted">${info}</span></div>`;
  }).join('');

  const latest = [...S.requests].sort((a, b) => b.created_at - a.created_at).slice(0, 6);
  $('#feed').innerHTML = latest.map((r) => {
    const st = idx[r.id];
    return `<div class="list-item"><strong>${esc(r.member_name)}</strong> แจ้งรับ #${r.id} <span class="muted">${timeText(r.created_at)}</span><br>
      พิกัด ${coordLink(r.lat, r.lng)}<br>
      จำนวน ${itemsText(r.items)} · รวม <strong>${num(r.total_count)} ชิ้น</strong><br>
      <span class="muted">นัด ${esc(slotLabel(r.slot))} · ${esc(statusText(r, st))}</span></div>`;
  }).join('');

  $('#factory-list').innerHTML = (plan.factory_kg || []).map((f) =>
    `<div class="list-item">${esc(f.name)}<br><span class="muted">ประมาณ ${num(f.kg, 1)} กก.</span></div>`).join('')
    + '<p class="muted">รถทุกคันกลับมาส่งที่ศูนย์คัดแยก แล้วแยกส่งโรงงานตามชนิดวัสดุ</p>';
}

// ---------- คนขับรถรับของ ----------
// ขั้นตอนต่อหนึ่งจุด: นำทาง -> ถึงจุด สแกน QR ของลูกค้า (ยืนยันจุด) -> ตรวจรายการและชั่งน้ำหนัก (ยืนยันของ)
// เมื่อรับครบ: กลับศูนย์คัดแยก แล้วกดส่งของเพื่อปิดรอบ
let scanFor = null;     // เลขคำขอที่กำลังเปิดหน้าสแกน
let scanStream = null;
let scanTimer = null;
let scanBusy = false;

// ระหว่างสแกนหรือกำลังพิมพ์ตัวเลข ไม่วาดหน้าใหม่ เพื่อไม่ให้กล้องดับหรือค่าที่พิมพ์หาย
const driverBusy = () => scanFor !== null || !!document.activeElement?.closest?.('#driver-stops input');

function renderDriver() {
  const sel = $('#driver-vehicle');
  if (sel.options.length !== S.vehicles.length) {
    const keep = sel.value;
    sel.innerHTML = S.vehicles.map((v) => `<option value="${v.id}">${esc(v.name)}</option>`).join('');
    if (keep) sel.value = keep;
  }
  const vid = Number(sel.value);
  const veh = S.vehicles.find((v) => v.id === vid);
  const route = (S.plan?.routes || []).find((r) => r.vehicle_id === vid);
  const byId = Object.fromEntries(S.requests.map((r) => [r.id, r]));
  const stops = (route?.stops || []).map((s) => ({ ...s, r: byId[s.request_id] })).filter((s) => s.r);
  const open = stops.filter((s) => isOpen(s.r));
  const onTruck = S.requests.filter((r) => r.status === 'collected' && r.vehicle_id === vid);
  const total = open.length + onTruck.length;
  $('#driver-progress').style.width = total ? `${Math.round((onTruck.length / total) * 100)}%` : '0%';

  $('#driver-summary').textContent = !veh?.active ? 'รถคันนี้หยุดใช้งานอยู่'
    : open.length ? `เหลือ ${open.length} จุด · รับแล้ว ${onTruck.length} จุด · ระยะทางรอบนี้ ${num(route.km, 1)} กม.`
    : onTruck.length ? 'รับครบทุกจุดแล้ว กลับไปส่งของที่ศูนย์คัดแยก' : 'ยังไม่มีงานในรอบนี้';

  const nextId = open[0]?.r.id;
  $('#driver-stops').innerHTML = veh?.active ? stops.map((s, n) => stopCard(s, n, s.r.id === nextId)).join('') : '';
  renderDriverEnd(vid, open, onTruck);
}

const checkItems = (r) => r.items.filter((i) => i.material !== 'non_recyclable');

function stopCard(s, n, isNext) {
  const r = s.r;
  let body;
  if (isDone(r)) {
    body = `<div class="notice ok">รับแล้ว ${num(r.actual_kg, 1)} กก.${r.actual_items ? ` · นับได้ ${num(sumCount(r.actual_items))} ชิ้น` : ''}</div>`;
  } else if (r.status === 'verified') {
    const far = r.verify_distance_m != null && r.verify_distance_m > 200;
    body = `<div class="notice ${far ? '' : 'ok'}">ยืนยันจุดแล้ว ${timeText(r.verified_at)}${r.verify_distance_m != null ? ` · สแกนห่างจากหมุด ${num(r.verify_distance_m)} ม.${far ? ' ซึ่งไกลกว่าปกติ' : ''}` : ''}</div>
      <p class="muted">ตรวจของให้ตรงกับรายการ แก้จำนวนถ้าไม่ตรง แล้วชั่งน้ำหนัก</p>
      <ul class="items">${checkItems(r).map((i, k) => `<li><div><div class="name">${esc(i.name_th)}</div><div class="tip">แจ้งไว้ ${num(i.count)} ชิ้น</div></div>
        <div class="count"><input type="number" min="0" inputmode="numeric" value="${Number(i.count) || 0}" data-actual="${r.id}" data-k="${k}" aria-label="จำนวนที่รับจริง ${esc(i.name_th)}"><span>ชิ้น</span></div></li>`).join('')}</ul>
      <div class="collect"><label for="kg-${r.id}">น้ำหนักจริง</label>
        <input type="number" min="0.1" step="0.1" inputmode="decimal" value="${Number(r.est_kg).toFixed(1)}" id="kg-${r.id}"><span>กก.</span>
        <button type="button" class="btn primary small" data-collect="${r.id}">ยืนยันรับของ</button></div>`;
  } else if (scanFor === r.id) {
    body = `<div class="scanner">
      <p><strong>สแกน QR จากมือถือของลูกค้า</strong> เพื่อยืนยันว่ามาถูกจุด</p>
      <video id="scan-video" playsinline muted hidden></video>
      <div class="row">
        <button type="button" class="btn primary small" data-scan="camera">เปิดกล้องสแกน</button>
        <label class="btn ghost small" for="scan-file">แนบรูป QR</label>
        <input id="scan-file" type="file" accept="image/*" hidden>
      </div>
      <form class="row" id="scan-form">
        <input type="text" id="scan-code" placeholder="หรือพิมพ์รหัส 6 ตัว" maxlength="6" autocomplete="off" autocapitalize="characters" aria-label="รหัสรับของ 6 ตัว">
        <button type="submit" class="btn ghost small">ยืนยันรหัส</button>
      </form>
      <p id="scan-msg" class="muted" role="status"></p>
      <div><button type="button" class="btn ghost small" data-scan="cancel">ยกเลิก</button></div>
    </div>`;
  } else {
    body = `<div class="row actions"><a class="btn ghost small" href="${mapsUrl(r.lat, r.lng)}" target="_blank" rel="noopener">นำทาง</a>
      <button type="button" class="btn ${isNext ? 'primary' : 'ghost'} small" data-arrive="${r.id}">ถึงจุดแล้ว สแกน QR</button></div>`;
  }
  return `<div class="card stop ${isDone(r) ? 'done' : ''} ${isNext ? 'next' : ''}">
    <div class="seq">${n + 1}</div>
    <div>
      ${r.has_photo ? `<img src="/api/requests/${r.id}/photo" alt="รูปที่สมาชิกแนบ" loading="lazy">` : ''}
      ${isNext ? '<span class="tag">จุดถัดไป</span><br>' : ''}
      <strong>${hhmm(s.eta)} · ${esc(r.member_name)}</strong><br>
      <span class="muted">${esc(r.address)} · นัด ${esc(slotLabel(r.slot))}</span><br>
      พิกัด ${coordLink(r.lat, r.lng)}<br>
      ${itemsText(r.items)}<br>
      รวม <strong>${num(r.total_count)} ชิ้น</strong> · ประมาณ ${num(r.est_kg, 1)} กก.
      ${body}
    </div></div>`;
}

function renderDriverEnd(vid, open, onTruck) {
  const depot = S.config.depot;
  const last = [...(S.dropoffs || [])].reverse().find((d) => d.vehicle_id === vid);
  let out = '';
  if (onTruck.length) {
    const kg = onTruck.reduce((a, r) => a + (r.actual_kg || 0), 0);
    out += `<div class="card ${open.length ? '' : 'next'}">
      <h2>${open.length ? 'ของบนรถตอนนี้' : 'รับครบแล้ว กลับศูนย์คัดแยก'}</h2>
      <p>${num(onTruck.length)} จุด · ${num(kg, 1)} กก.</p>
      <p class="muted">${esc(depot.name)} · พิกัด ${coordLink(depot.lat, depot.lng)}</p>
      <div class="row actions"><a class="btn ghost small" href="${mapsUrl(depot.lat, depot.lng)}" target="_blank" rel="noopener">นำทางไปศูนย์</a>
        <button type="button" class="btn ${open.length ? 'ghost' : 'primary'} small" data-dropoff="${vid}" data-open="${open.length}">ส่งของที่ศูนย์แล้ว</button></div></div>`;
  }
  if (last) {
    out += `<div class="card"><h2>รอบที่ส่งล่าสุด</h2>
      <p>${timeText(last.at)} · ${num(last.stops)} จุด · ${num(last.pieces)} ชิ้น · ${num(last.kg, 1)} กก.</p>
      ${last.factories.filter((f) => f.kg > 0).map((f) => `<div class="list-item">${esc(f.name)}<br><span class="muted">${num(f.kg, 1)} กก.</span></div>`).join('')}</div>`;
  }
  $('#driver-end').innerHTML = out;
}

// ----- สแกน QR -----
function scanMsg(text) { const el = $('#scan-msg'); if (el) el.textContent = text; }

function stopCamera() {
  clearInterval(scanTimer);
  scanTimer = null;
  if (scanStream) scanStream.getTracks().forEach((t) => t.stop());
  scanStream = null;
}

async function decodeQR(source, w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const g = c.getContext('2d', { willReadFrequently: true });
  g.fillStyle = '#fff';
  g.fillRect(0, 0, w, h);
  g.drawImage(source, 0, 0, w, h);
  if ('BarcodeDetector' in window) {
    try {
      const hits = await new BarcodeDetector({ formats: ['qr_code'] }).detect(c);
      if (hits.length) return hits[0].rawValue;
    } catch { /* ใช้ตัวอ่านสำรองด้านล่าง */ }
  }
  if (window.jsQR) {
    const hit = jsQR(g.getImageData(0, 0, w, h).data, w, h);
    if (hit) return hit.data;
  }
  return null;
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) return scanMsg('อุปกรณ์นี้เปิดกล้องจากหน้าเว็บไม่ได้ (ต้องเป็น HTTPS หรือ localhost) ใช้แนบรูป QR หรือพิมพ์รหัสแทน');
  try {
    scanStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
  } catch { return scanMsg('เปิดกล้องไม่ได้ ใช้แนบรูป QR หรือพิมพ์รหัสแทน'); }
  const video = $('#scan-video');
  if (!video) return stopCamera();
  video.srcObject = scanStream;
  video.hidden = false;
  await video.play().catch(() => {});
  scanMsg('หันกล้องไปที่ QR บนมือถือของลูกค้า');
  scanTimer = setInterval(async () => {
    if (scanBusy || video.readyState < 2) return;
    scanBusy = true;
    try {
      const value = await decodeQR(video, video.videoWidth, video.videoHeight);
      if (value) await submitScan(value);
    } finally { scanBusy = false; }
  }, 350);
}

async function scanFromFile(file) {
  try {
    const img = await loadImage(file);
    const k = Math.min(1, 1200 / Math.max(img.naturalWidth, img.naturalHeight));
    const value = await decodeQR(img, Math.round(img.naturalWidth * k), Math.round(img.naturalHeight * k));
    if (!value) return scanMsg('อ่าน QR จากรูปนี้ไม่ได้ ลองรูปที่ชัดขึ้น หรือพิมพ์รหัสแทน');
    await submitScan(value);
  } catch (err) { scanMsg(err.message); }
}

// ตำแหน่งของคนขับตอนสแกน ถ้าอุปกรณ์ให้ได้ภายใน 1.5 วินาที ใช้บันทึกว่าสแกนห่างจากหมุดเท่าไร
function driverPosition() {
  return new Promise((resolve) => {
    if (!navigator.geolocation || !window.isSecureContext) return resolve(null);
    const timer = setTimeout(() => resolve(null), 1500);
    navigator.geolocation.getCurrentPosition(
      (p) => { clearTimeout(timer); resolve({ lat: p.coords.latitude, lng: p.coords.longitude }); },
      () => { clearTimeout(timer); resolve(null); },
      { maximumAge: 30000, timeout: 1500 });
  });
}

async function submitScan(value) {
  const id = scanFor;
  if (!id) return;
  scanMsg('กำลังตรวจรหัส…');
  try {
    const pos = await driverPosition();
    await api(`/requests/${id}/verify`, { scan: value, vehicle_id: Number($('#driver-vehicle').value), ...(pos || {}) });
    stopCamera();
    scanFor = null;
    toast('ยืนยันจุดแล้ว ตรวจของต่อได้เลย');
    await refresh();
    renderDriver();
  } catch (err) { scanMsg(err.message); }
}

async function collectStop(id, btn) {
  const r = S.requests.find((x) => x.id === id);
  const items = checkItems(r).map((i, k) => ({
    name_th: i.name_th, material: i.material, prep_tip_th: '',
    count: Math.max(0, parseInt($(`[data-actual="${id}"][data-k="${k}"]`).value, 10) || 0),
  }));
  btn.disabled = true;
  try {
    const res = await api(`/requests/${id}/collect`, { actual_kg: Number($(`#kg-${id}`).value), items });
    toast(`รับของแล้ว สมาชิกได้รับ ${num(res.points)} แต้ม`);
    document.activeElement?.blur();
    await refresh();
    renderDriver();
  } catch (err) { toast(err.message); btn.disabled = false; }
}

// ---------- บันทึก ----------
function renderRecords() {
  const idx = stopIndex();
  const rows = [...S.requests].reverse();
  const collected = rows.filter(isDone);
  $('#records-totals').innerHTML = `
    <div class="stat"><b>${num(rows.length)}</b><span>คำขอทั้งหมด</span></div>
    <div class="stat"><b>${num(rows.reduce((a, r) => a + r.total_count, 0))}</b><span>ชิ้นที่แจ้ง</span></div>
    <div class="stat"><b>${num(collected.length)}</b><span>รับแล้ว</span></div>
    <div class="stat"><b>${num(collected.reduce((a, r) => a + (r.actual_kg || 0), 0), 1)} กก.</b><span>น้ำหนักจริงที่รับ</span></div>`;
  $('#records-table').innerHTML = `<thead><tr>
      <th>เลขที่</th><th>เวลาแจ้ง</th><th>สมาชิก</th><th>พิกัด</th><th>ช่วงนัด</th><th>รายการและจำนวน</th>
      <th>รวม (ชิ้น)</th><th>ประมาณ (กก.)</th><th>ยืนยันจุด</th><th>รับจริง (ชิ้น)</th><th>จริง (กก.)</th><th>สถานะ</th></tr></thead><tbody>${rows.map((r) => {
    const st = idx[r.id];
    return `<tr><td>#${r.id}</td><td>${timeText(r.created_at)}</td><td>${esc(r.member_name)}</td><td>${coordLink(r.lat, r.lng)}</td>
      <td>${esc(slotLabel(r.slot))}</td><td>${itemsText(r.items)}</td><td class="num">${num(r.total_count)}</td>
      <td class="num">${num(r.est_kg, 1)}</td><td>${r.verified_at ? timeText(r.verified_at) : '–'}</td><td class="num">${r.actual_items ? num(sumCount(r.actual_items)) : '–'}</td>
      <td class="num">${r.actual_kg ? num(r.actual_kg, 1) : '–'}</td>
      <td>${isDone(r) || r.status === 'verified' ? `<span class="tag ${isDone(r) ? 'gray' : 'here'}">${statusText(r)}</span>` : st ? `<span class="tag">${esc(st.name)}</span>` : '<span class="tag warn">รอจัดรถ</span>'}</td></tr>`;
  }).join('')}</tbody>`;
}

// ---------- การสลับหน้าและเหตุการณ์ ----------
function show(next) {
  view = ['member', 'dispatch', 'driver', 'records'].includes(next) ? next : 'member';
  for (const v of ['member', 'dispatch', 'driver', 'records']) $(`#view-${v}`).hidden = v !== view;
  document.querySelectorAll('.tabs button').forEach((b) => b.classList.toggle('active', b.dataset.view === view));
  if (view !== 'driver') { stopCamera(); scanFor = null; }
  if (location.hash.slice(1) !== view) history.replaceState(null, '', '#' + view);
  if (S) renderAll();
  if (view === 'member' && pinMap) pinMap.invalidateSize();
}

document.querySelector('.tabs').addEventListener('click', (e) => { if (e.target.dataset.view) show(e.target.dataset.view); });
window.addEventListener('hashchange', () => show(location.hash.slice(1)));

$('#member-select').addEventListener('change', () => { const me = currentMember(); setPin(me.lat, me.lng); renderMember(); });
$('#photo').addEventListener('change', (e) => { const f = e.target.files[0]; e.target.value = ''; if (f) handlePhoto(f); });
$('#use-gps').addEventListener('click', () => {
  if (!navigator.geolocation) return toast('อุปกรณ์นี้ไม่รองรับการระบุตำแหน่ง');
  navigator.geolocation.getCurrentPosition((p) => setPin(p.coords.latitude, p.coords.longitude), () => toast('อ่านตำแหน่งไม่ได้ ลากหมุดบนแผนที่แทน'));
});
$('#slot-chips').addEventListener('click', (e) => {
  if (!e.target.dataset.slot) return;
  slot = e.target.dataset.slot;
  document.querySelectorAll('#slot-chips .chip').forEach((c) => c.classList.toggle('active', c.dataset.slot === slot));
  updateSubmit();
});
$('#ai-result').addEventListener('input', (e) => {
  if (e.target.dataset.item === undefined) return;
  draft.items[Number(e.target.dataset.item)].count = e.target.value;
  renderTotals();
});
$('#ai-result').addEventListener('click', (e) => {
  if (!e.target.dataset.size) return;
  draft.size = e.target.dataset.size;
  document.querySelectorAll('#ai-result [data-size]').forEach((c) => c.classList.toggle('active', c.dataset.size === draft.size));
  renderTotals();
});
$('#submit-request').addEventListener('click', submitRequest);

$('#replan').addEventListener('click', async () => {
  try { const p = await api('/plan', {}); await refresh(); toast(p.summary); } catch (err) { toast(err.message); }
});
$('#reset').addEventListener('click', async () => {
  if (!confirm('ล้างข้อมูลทั้งหมดแล้วกลับไปใช้ข้อมูลตัวอย่างใช่ไหม')) return;
  try { await api('/reset', {}); dFitted = ''; await refresh(); toast('รีเซ็ตข้อมูลแล้ว'); } catch (err) { toast(err.message); }
});
$('#command-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = $('#command-text');
  if (!input.value.trim()) return;
  $('#command-reply').textContent = 'กำลังประมวลผล…';
  try {
    const res = await api('/command', { text: input.value });
    $('#command-reply').textContent = res.reply + (res.source === 'rule' ? ' (ตีความด้วยกฎคำสำคัญ เพราะยังไม่ได้ตั้งค่า AI)' : '');
    if (res.ok) input.value = '';
    await refresh();
  } catch (err) { $('#command-reply').textContent = err.message; }
});
$('#my-requests').addEventListener('toggle', async (e) => {
  const id = Number(e.target.dataset?.ticket);
  if (!id) return;
  if (!e.target.open) { openTickets.delete(id); return; }
  openTickets.add(id);
  if (!tickets[id]) {
    try { tickets[id] = await api(`/requests/${id}/ticket`); } catch (err) { return toast(err.message); }
  }
  e.target.querySelector('.qr-box').innerHTML = ticketHtml(id);
}, true);  // toggle ไม่ bubble จึงต้องจับในช่วง capture

$('#driver-vehicle').addEventListener('change', () => { stopCamera(); scanFor = null; renderDriver(); });
$('#driver-stops').addEventListener('click', (e) => {
  const d = e.target.dataset;
  if (d.arrive) { stopCamera(); scanFor = Number(d.arrive); renderDriver(); $('#scan-code')?.focus(); }
  else if (d.scan === 'camera') startCamera();
  else if (d.scan === 'cancel') { stopCamera(); scanFor = null; renderDriver(); }
  else if (d.collect) collectStop(Number(d.collect), e.target);
});
$('#driver-stops').addEventListener('submit', (e) => {
  if (e.target.id !== 'scan-form') return;
  e.preventDefault();
  const code = $('#scan-code').value.trim();
  if (code) submitScan(code);
});
$('#driver-stops').addEventListener('change', (e) => {
  if (e.target.id !== 'scan-file') return;
  const f = e.target.files[0];
  e.target.value = '';
  if (f) scanFromFile(f);
});
$('#driver-end').addEventListener('click', async (e) => {
  const vid = e.target.dataset.dropoff;
  if (!vid) return;
  if (Number(e.target.dataset.open) > 0 && !confirm('ยังมีจุดที่ยังไม่ได้รับ ต้องการส่งของที่ศูนย์ตอนนี้ใช่ไหม')) return;
  e.target.disabled = true;
  try {
    const res = await api(`/vehicles/${vid}/dropoff`, {});
    toast(`ส่งของแล้ว ${num(res.stops)} จุด รวม ${num(res.kg, 1)} กก.`);
    await refresh();
    renderDriver();
  } catch (err) { toast(err.message); e.target.disabled = false; }
});

// ---------- เริ่มทำงาน ----------
(async () => {
  try {
    await refresh();
    show(location.hash.slice(1) || 'member');
  } catch { toast('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้'); }
  // ดึงข้อมูลใหม่เป็นระยะ เพื่อให้หน้าผู้จัดรถเห็นงานที่เพิ่งแจ้งเข้ามา
  setInterval(() => { if (!document.hidden) refresh().catch(() => {}); }, 4000);
})();

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
}
