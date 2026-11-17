// Al-Noor Family Clinic: study prototype that uses the AdaptKit runtime.
// The runtime records positions and times only. This file never reads,
// stores or logs what the participant types (form values are only checked
// for being non-empty and are cleared when the booking is finished).

import { AdaptKit } from '../../js/adaptkit.js';

// The policy the adaptive condition uses. Swap for '../../policies/demo.json' to try the
// easy-to-trigger demo rules (the panel then warns that it is a placeholder).
const POLICY_URL = '../../policies/default.json';
import {
  YEAR, MONTH, SPECIALTIES, DOCTORS, SLOTS, TASKS, STRINGS, MONTHS, WEEKDAYS_SHORT, WEEKDAYS,
  dayAvailable, slotAvailable, formatTime, formatDate,
} from './data.js';

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const html = document.documentElement;

const STEPS = ['pick_specialty', 'pick_doctor', 'pick_date', 'pick_slot', 'fill_form', 'confirm', 'done'];
const LANG_KEY = 'clinic:lang';
const PANEL_KEY = 'clinic:researcher';

const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch { /* storage blocked: ignore */ } },
};

const state = {
  lang: store.get(LANG_KEY) === 'ar' ? 'ar' : 'en',
  step: 'pick_specialty',
  spec: null,
  doctor: null,
  day: null,
  slot: null,
  session: null, // { id, n, mode, card, participant }
  selections: 0,
  misses: 0,
  exported: false,
  warnedUnexported: false,
  lastAdapt: '-',
  booking: '-',
};

// ---------------------------------------------------------------------------
// Text
// ---------------------------------------------------------------------------

function t(key, vars = {}) {
  let s = (STRINGS[state.lang] && STRINGS[state.lang][key]) ?? STRINGS.en[key] ?? key;
  for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, v);
  return s;
}

const specName = (id) => { const s = SPECIALTIES.find((x) => x.id === id); return s ? s[state.lang] : ''; };
const docName = (id) => { const d = DOCTORS.find((x) => x.id === id); return d ? d[state.lang] : ''; };

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children) if (c != null) node.append(c);
  return node;
}

const ICONS = {
  general: 'M10 3h4v7h7v4h-7v7h-4v-7H3v-4h7z',
  paeds: 'M12 2a4 4 0 1 1 0 8 4 4 0 0 1 0-8zm-6 20v-5a6 6 0 0 1 12 0v5z',
  derm: 'M12 2c3 4.5 7 8.5 7 12.5A7 7 0 0 1 5 14.5C5 10.5 9 6.5 12 2z',
  eye: 'M12 5c5 0 9 4 10.5 7C21 15 17 19 12 19S3 15 1.5 12C3 9 7 5 12 5zm0 3.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z',
  dental: 'M7 2c2 0 3 1 5 1s3-1 5-1c3 0 4 3 4 6 0 4-2 6-2.5 10-.3 2.5-1.2 4-2.5 4-2 0-1.5-6-4-6s-2 6-4 6c-1.3 0-2.2-1.5-2.5-4C5 14 3 12 3 8c0-3 1-6 4-6z',
  heart: 'M12 21C5 15.5 2 12.5 2 8.5A5 5 0 0 1 12 6a5 5 0 0 1 10 2.5c0 4-3 7-10 12.5z',
};

function icon(id) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', ICONS[id] || ICONS.general);
  path.setAttribute('fill', 'currentColor');
  svg.append(path);
  return svg;
}

function initials(name) {
  return name.replace(/^(Dr\.|د\.)\s*/, '').split(/\s+/).map((w) => w[0]).slice(0, 2).join(state.lang === 'ar' ? ' ' : '');
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function applyLang() {
  html.lang = state.lang;
  html.dir = state.lang === 'ar' ? 'rtl' : 'ltr';
  document.title = `${t('clinic')} — ${t('clinic_sub')}`;
  $$('[data-i18n]').forEach((node) => { node.textContent = t(node.dataset.i18n); });
  $$('[data-stepno]').forEach((node) => { node.textContent = t('step', { n: node.dataset.stepno }); });
  const toggle = $('#langToggle');
  toggle.textContent = t('lang_toggle');
  toggle.setAttribute('aria-label', t('lang_toggle_label'));
  toggle.setAttribute('lang', state.lang === 'ar' ? 'en' : 'ar');
  $$('.err:not([hidden])').forEach((node) => { node.textContent = t('f_required'); });
  $$('[data-hint]').forEach((node) => { node.textContent = ''; });
  renderAll();
}

function setLang(lang) {
  state.lang = lang === 'ar' ? 'ar' : 'en';
  store.set(LANG_KEY, state.lang);
  applyLang();
  AdaptKit.setLang(state.lang);
}

function renderAll() {
  renderTaskCard();
  renderSpecialties();
  renderDoctors();
  renderCalendar();
  renderSlots();
  renderSummary();
  updateNext();
}

function renderTaskCard() {
  const card = $('#taskCard');
  const s = state.session;
  card.hidden = !s;
  $('#demoNote').hidden = !!s || !isResearcher;
  if (!s) return;
  const task = TASKS[s.card];
  $('#taskCardName').textContent = `(${t('task_card')} ${s.card})`;
  const rows = [
    ['task_spec', specName(task.spec)],
    ['task_doctor', docName(task.doctor)],
    ['task_date', formatDate(task.day, state.lang)],
    ['task_time', formatTime(task.slot, state.lang)],
    ['task_name', task.name[state.lang]],
    ['task_phone', task.phone],
    ['task_reason', task.reason[state.lang]],
  ];
  $('#taskBody').replaceChildren(...kvRows(rows, 'task_phone'));
}

// <dl> rows wrapped in <div>s so each label/value pair can wrap on narrow screens.
function kvRows(rows, ltrKey) {
  return rows.map(([k, v]) => el('div', {}, el('dt', { text: t(k) }), el('dd', { text: v, dir: k === ltrKey ? 'ltr' : null })));
}

function choiceButton(cls, pressed, onClick, ...children) {
  return el('button', { type: 'button', class: cls, 'data-adapt-target': true, 'aria-pressed': pressed ? 'true' : 'false', onclick: onClick }, ...children);
}

function renderSpecialties() {
  const grid = $('#specGrid');
  grid.replaceChildren(...SPECIALTIES.map((s) => choiceButton('card', state.spec === s.id, () => {
    if (state.spec !== s.id) { state.spec = s.id; state.doctor = null; state.day = null; state.slot = null; }
    renderSpecialties(); renderDoctors(); updateNext();
  },
  el('span', { class: 'card-icon' }, icon(s.id)),
  el('span', { class: 'card-text' },
    el('span', { class: 'card-title', text: s[state.lang] }),
    el('span', { class: 'card-desc', text: s[`${state.lang}_desc`] })),
  el('span', { class: 'card-check', 'aria-hidden': 'true' }))));
}

function renderDoctors() {
  const grid = $('#docGrid');
  const list = DOCTORS.filter((d) => d.spec === state.spec);
  grid.replaceChildren(...list.map((d) => choiceButton('card', state.doctor === d.id, () => {
    if (state.doctor !== d.id) { state.doctor = d.id; state.day = null; state.slot = null; }
    renderDoctors(); renderCalendar(); updateNext();
  },
  el('span', { class: 'card-icon avatar', 'aria-hidden': 'true', text: initials(d[state.lang]) }),
  el('span', { class: 'card-text' },
    el('span', { class: 'card-title', text: d[state.lang] }),
    el('span', { class: 'card-desc', text: `${specName(d.spec)} · ${t('years', { n: d.years })}` })),
  el('span', { class: 'card-check', 'aria-hidden': 'true' }))));
}

function renderCalendar() {
  const cal = $('#calendar');
  const first = new Date(YEAR, MONTH, 1).getDay();
  const days = new Date(YEAR, MONTH + 1, 0).getDate();
  const grid = el('div', { class: 'cal-grid', role: 'group', 'aria-labelledby': 'cal-title' });
  WEEKDAYS_SHORT[state.lang].forEach((w, i) => grid.append(el('abbr', { class: 'cal-head', title: WEEKDAYS[state.lang][i], text: w })));
  for (let i = 0; i < first; i++) grid.append(el('span', { class: 'cal-blank', 'aria-hidden': 'true' }));
  for (let day = 1; day <= days; day++) {
    const dow = new Date(YEAR, MONTH, day).getDay();
    const open = state.doctor ? dayAvailable(state.doctor, day) : false;
    const label = `${formatDate(day, state.lang)}${open ? '' : `, ${t('unavailable')}`}`;
    const content = [el('span', { class: 'dow', 'aria-hidden': 'true', text: WEEKDAYS_SHORT[state.lang][dow] }), el('span', { class: 'num', text: String(day) })];
    if (open) {
      grid.append(el('button', {
        type: 'button', class: 'day', 'data-adapt-target': true, 'aria-label': label,
        'aria-pressed': state.day === day ? 'true' : 'false',
        onclick: () => {
          if (state.day !== day) { state.day = day; state.slot = null; }
          $$('.day', cal).forEach((b) => b.setAttribute('aria-pressed', b.dataset.day === String(day) ? 'true' : 'false'));
          renderSlots(); updateNext();
        },
        'data-day': day,
      }, ...content));
    } else {
      // Not a target: a press here is recorded by AdaptKit as a miss.
      grid.append(el('button', { type: 'button', class: 'day is-unavailable', 'aria-disabled': 'true', 'aria-label': label }, ...content));
    }
  }
  cal.replaceChildren(el('p', { id: 'cal-title', class: 'cal-title', text: `${MONTHS[state.lang][MONTH]} ${YEAR}` }), grid);
  fitCalendar();
}

// A 7-column grid of 64px cells does not fit on a narrow phone. When the grid
// would overflow, switch to a wrapping list of days (weekday shown in each cell).
function fitCalendar() {
  const cal = $('#calendar');
  const grid = $('.cal-grid', cal);
  if (!grid || cal.offsetParent === null) return;
  cal.classList.remove('is-wrap');
  if (grid.scrollWidth > cal.clientWidth + 1) cal.classList.add('is-wrap');
}

function renderSlots() {
  const grid = $('#slotGrid');
  $('#slotDate').textContent = state.day && state.doctor ? `${docName(state.doctor)} · ${formatDate(state.day, state.lang)}` : '';
  if (!state.day || !state.doctor) { grid.replaceChildren(); return; }
  grid.replaceChildren(...SLOTS.map((min) => {
    const label = formatTime(min, state.lang);
    if (!slotAvailable(state.doctor, state.day, min)) {
      return el('button', { type: 'button', class: 'slot is-unavailable', 'aria-disabled': 'true', 'aria-label': `${label}, ${t('unavailable')}`, text: label });
    }
    return el('button', {
      type: 'button', class: 'slot', 'data-adapt-target': true, 'data-slot': min,
      'aria-pressed': state.slot === min ? 'true' : 'false', text: label,
      onclick: () => {
        state.slot = min;
        $$('.slot', grid).forEach((b) => b.setAttribute('aria-pressed', b.dataset.slot === String(min) ? 'true' : 'false'));
        updateNext();
      },
    });
  }));
}

function summaryRows(includeDetails) {
  const rows = [
    ['s_spec', specName(state.spec)],
    ['s_doctor', docName(state.doctor)],
    ['s_date', state.day ? formatDate(state.day, state.lang) : ''],
    ['s_time', state.slot != null ? formatTime(state.slot, state.lang) : ''],
  ];
  if (includeDetails) {
    // Shown back to the participant on screen only; never stored or logged.
    rows.push(['s_name', $('#fName').value], ['s_phone', $('#fPhone').value], ['f_reason', $('#fReason').value]);
  }
  return rows;
}

function renderSummary() {
  if (state.step === 'confirm') $('#summary').replaceChildren(...kvRows(summaryRows(true), 's_phone'));
  if (state.step === 'done') {
    $('#doneSummary').replaceChildren(...kvRows([...summaryRows(false), ['done_ref', state.ref || '']], 'done_ref'));
  }
}

const ready = {
  pick_specialty: () => !!state.spec,
  pick_doctor: () => !!state.doctor,
  pick_date: () => !!state.day,
  pick_slot: () => state.slot != null,
  fill_form: () => true,
  confirm: () => true,
};

// A Next button with nothing chosen stays a real button but is aria-disabled,
// so AdaptKit counts a press on it as a miss (an error), not a selection.
function updateNext() {
  $$('[data-next]').forEach((b) => {
    const ok = ready[b.dataset.next]();
    if (ok) {
      b.removeAttribute('aria-disabled');
      const hint = $('[data-hint]', b.closest('.screen'));
      if (hint) hint.textContent = '';
    } else {
      b.setAttribute('aria-disabled', 'true');
    }
  });
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

function showStep(step, { focus = true } = {}) {
  state.step = step;
  $$('.screen').forEach((s) => { s.hidden = s.dataset.step !== step; });
  $$('[data-hint]').forEach((node) => { node.textContent = ''; });
  renderSummary();
  updateNext();
  if (step === 'pick_date') fitCalendar();
  window.scrollTo(0, 0);
  if (focus) { const h = $(`.screen[data-step="${step}"] h1`); if (h) h.focus({ preventScroll: true }); }
  if (state.session && step !== 'done') AdaptKit.startTask(`clinic.${step}`);
  updatePanel();
}

function validateForm() {
  let firstBad = null;
  for (const id of ['fName', 'fPhone', 'fReason']) {
    const input = $(`#${id}`);
    const err = $(`#${id}-err`);
    const empty = input.value.trim() === '';
    err.hidden = !empty;
    err.textContent = empty ? t('f_required') : '';
    if (empty) input.setAttribute('aria-invalid', 'true'); else input.removeAttribute('aria-invalid');
    if (empty && !firstBad) firstBad = input;
  }
  if (firstBad) firstBad.focus();
  return !firstBad;
}

function onNext(step, button) {
  const screen = button.closest('.screen');
  if (button.getAttribute('aria-disabled') === 'true') {
    $('[data-hint]', screen).textContent = t('pick_first');
    return;
  }
  if (step === 'fill_form' && !validateForm()) return;
  if (step === 'confirm') { finishBooking(); return; }
  showStep(STEPS[STEPS.indexOf(step) + 1]);
}

function onBack() {
  const i = STEPS.indexOf(state.step);
  if (i > 0) showStep(STEPS[i - 1]);
}

function finishBooking() {
  state.ref = `AN-${String(1000 + Math.floor(Math.random() * 9000))}`;
  if (state.session) {
    const task = TASKS[state.session.card];
    const checks = [state.spec === task.spec, state.doctor === task.doctor, state.day === task.day, state.slot === task.slot];
    state.booking = `finished; ${checks.filter(Boolean).length}/4 choices match card ${state.session.card}`;
    state.session.finishedAt = new Date().toLocaleTimeString();
  }
  showStep('done');
  $('#bookForm').reset(); // clear the typed fake details
  $$('.err').forEach((e) => { e.hidden = true; });
}

function resetBooking() {
  state.spec = null; state.doctor = null; state.day = null; state.slot = null; state.ref = null;
  $('#bookForm').reset();
  $$('.err').forEach((e) => { e.hidden = true; });
  $$('#bookForm input').forEach((i) => i.removeAttribute('aria-invalid'));
}

// ---------------------------------------------------------------------------
// Researcher panel and sessions
// ---------------------------------------------------------------------------

const isResearcher = new URLSearchParams(location.search).get('researcher') === '1';
let policyCache; // undefined = not checked yet, null = missing

async function loadPolicy() {
  try {
    const res = await fetch(POLICY_URL, { cache: 'no-store' });
    if (!res.ok) return null;
    const json = await res.json();
    return json && typeof json === 'object' && json.levels && json.table ? json : null;
  } catch {
    return null;
  }
}

function panelSettings() {
  const pid = ($('#rpPid').value || '').trim().replace(/[^A-Za-z0-9_-]/g, '').slice(0, 16) || 'P00';
  return { pid, order: $('#rpOrder').value, card1: $('#rpCard1').value, lang: $('#rpLang').value };
}

function plan(n) {
  const s = panelSettings();
  const first = s.order === 'static-first' ? 'static' : 'adaptive';
  const mode = n === 1 ? first : (first === 'static' ? 'adaptive' : 'static');
  const card = n === 1 ? s.card1 : (s.card1 === 'A' ? 'B' : 'A');
  return { ...s, n, mode, card, id: `${s.pid}-${mode}` };
}

function savePanel() {
  store.set(PANEL_KEY, JSON.stringify(panelSettings()));
  const p1 = plan(1); const p2 = plan(2);
  $('#rpPlan').textContent = `Session 1: ${p1.id}, card ${p1.card}. Session 2: ${p2.id}, card ${p2.card}.`;
}

function restorePanel() {
  let saved = null;
  try { saved = JSON.parse(store.get(PANEL_KEY)); } catch { saved = null; }
  if (saved) {
    if (saved.pid) $('#rpPid').value = saved.pid;
    if (saved.order) $('#rpOrder').value = saved.order;
    if (saved.card1) $('#rpCard1').value = saved.card1;
  }
  $('#rpLang').value = state.lang;
}

function msg(text, kind = 'info') {
  const node = $('#rpMsg');
  node.textContent = text;
  node.dataset.kind = kind;
}

function updatePanel() {
  if (!isResearcher) return;
  const s = state.session;
  $('#rpSession').textContent = s ? s.id : 'none';
  $('#rpMode').textContent = s ? s.mode : '-';
  $('#rpCard').textContent = s ? s.card : '-';
  $('#rpStep').textContent = s ? (state.step === 'done' ? `done (${s.finishedAt || ''})` : `clinic.${state.step}`) : '-';
  $('#rpSel').textContent = String(state.selections);
  $('#rpMiss').textContent = String(state.misses);
  const ui = s ? AdaptKit.getUI() : null;
  $('#rpUI').textContent = ui ? `target ${ui.target}, text ${ui.text}, contrast ${ui.contrast}, layout ${ui.layout}` : '-';
  $('#rpAdapt').textContent = state.lastAdapt;
  $('#rpBooking').textContent = s ? state.booking : '-';
  $('#rpExported').textContent = s ? (state.exported ? 'yes' : 'no') : '-';
}

function clearRootUI() {
  html.style.removeProperty('--ak-target-min');
  html.style.removeProperty('--ak-font-scale');
  delete html.dataset.akContrast;
  delete html.dataset.akLayout;
}

async function startSession(n) {
  const p = plan(n);
  if (state.session && state.selections > 0 && !state.exported && !state.warnedUnexported) {
    state.warnedUnexported = true;
    msg(`${state.session.id} has ${state.selections} selections that were not exported. Press Export CSV first, or press Start again to continue (a copy stays saved in this browser: "Download all saved logs").`, 'warn');
    return;
  }
  msg('Starting…');
  const policy = await loadPolicy();
  policyCache = policy;
  showPolicyStatus();
  if (p.mode === 'adaptive' && !policy) {
    msg(`Adaptive mode needs a policy file at ${POLICY_URL} (made by the AdaptKit trainer). Session NOT started; the app stays in static mode.`, 'error');
    console.warn(`Clinic: adaptive mode needs ${POLICY_URL}. Staying in static mode.`);
    return;
  }
  // Saved logs are never deleted here; the runtime also backs up a log it would overwrite.
  if (state.session) AdaptKit.destroy();
  state.session = null;
  state.selections = 0; state.misses = 0; state.exported = false; state.warnedUnexported = false;
  state.lastAdapt = '-'; state.booking = 'in progress';
  resetBooking();
  setLang(p.lang);
  try {
    // The policy (if present) is passed in BOTH modes so that level 0 (the
    // starting UI) is identical in the static and the adaptive condition.
    await AdaptKit.init({ mode: p.mode, participant: p.pid, session: p.id, lang: p.lang, source: 'usability', policy: policy || undefined });
  } catch (err) {
    clearRootUI();
    msg(`Could not start: ${err.message}`, 'error');
    return;
  }
  state.session = { id: p.id, n, mode: p.mode, card: p.card, participant: p.pid };
  let note = `Session ${n} started: ${p.id}, card ${p.card}.`;
  if (policy && policy.is_placeholder && p.mode === 'adaptive') note += ' WARNING: this policy is a placeholder (not trained). Do not use it for a study.';
  msg(note, policy && policy.is_placeholder && p.mode === 'adaptive' ? 'warn' : 'info');
  renderTaskCard();
  $('#taskCard').open = true;
  showStep('pick_specialty');
}

function resetAll() {
  if (state.session) AdaptKit.destroy();
  clearRootUI();
  state.session = null;
  state.selections = 0; state.misses = 0; state.exported = false; state.warnedUnexported = false;
  state.lastAdapt = '-'; state.booking = '-';
  resetBooking();
  renderAll();
  showStep('pick_specialty', { focus: false });
  msg('Reset done. Nothing is being recorded. Earlier logs stay saved in this browser ("Download all saved logs").');
}

function showPolicyStatus() {
  if (!isResearcher) return;
  const p = policyCache;
  $('#rpPolicy').textContent = p === undefined ? 'checking…'
    : p === null ? 'missing (static only)'
      : `${p.kind || 'policy'}${p.is_placeholder ? ' (PLACEHOLDER)' : ''}, target levels ${JSON.stringify(p.levels.target_px)}`;
}

function setupPanel() {
  const panel = $('#rpanel');
  panel.hidden = false;
  restorePanel();
  savePanel();
  ['rpPid', 'rpOrder', 'rpCard1'].forEach((id) => $(`#${id}`).addEventListener('change', savePanel));
  $('#rpPid').addEventListener('input', savePanel);
  $('#rpLang').addEventListener('change', () => setLang($('#rpLang').value));
  $('#rpStart1').addEventListener('click', () => startSession(1));
  $('#rpStart2').addEventListener('click', () => startSession(2));
  $('#rpExport').addEventListener('click', () => {
    if (!state.session) { msg('No session to export.', 'warn'); return; }
    AdaptKit.downloadCSV(`clinic_${state.session.id}.csv`);
    state.exported = true;
    msg(`Exported clinic_${state.session.id}.csv (${state.selections} rows).`);
    updatePanel();
  });
  $('#rpReset').addEventListener('click', resetAll);
  $('#rpSaved').addEventListener('click', () => {
    const n = AdaptKit.downloadAllSaved(`clinic_all_saved_${new Date().toISOString().slice(0, 10)}.csv`);
    msg(`Downloaded every log saved in this browser (${n} rows, including backups; remove duplicates by session + trial).`);
  });
  $('#rpCollapse').addEventListener('click', () => {
    const collapsed = panel.classList.toggle('is-collapsed');
    $('#rpCollapse').textContent = collapsed ? 'Researcher' : 'Hide';
    $('#rpCollapse').setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  });
  loadPolicy().then((p) => { policyCache = p; showPolicyStatus(); });
  updatePanel();
}

// Live counters. Listeners stay registered across sessions (AdaptKit keeps them).
AdaptKit.on('event', (e) => {
  state.selections += 1;
  state.misses += e.misses || 0;
  updatePanel();
});
AdaptKit.on('adapt', (r) => {
  if (r.action && r.action !== 'none') { state.lastAdapt = `${r.action} (state ${r.state})`; requestAnimationFrame(fitCalendar); }
  updatePanel();
});
AdaptKit.on('undo', (u) => { state.lastAdapt = `undo ${u.action}`; requestAnimationFrame(fitCalendar); updatePanel(); });

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

$('#langToggle').addEventListener('click', () => {
  setLang(state.lang === 'ar' ? 'en' : 'ar');
  if (isResearcher) $('#rpLang').value = state.lang;
});
$$('[data-next]').forEach((b) => b.addEventListener('click', () => onNext(b.dataset.next, b)));
$$('[data-back]').forEach((b) => b.addEventListener('click', onBack));
$('#bookForm').addEventListener('submit', (e) => { e.preventDefault(); onNext('fill_form', $('[data-next="fill_form"]')); });

// Keep the calendar from overflowing when the size, font scale or layout changes.
if ('ResizeObserver' in window) new ResizeObserver(() => fitCalendar()).observe($('#calendar'));
new MutationObserver(() => requestAnimationFrame(fitCalendar))
  .observe(html, { attributes: true, attributeFilter: ['style', 'data-ak-layout', 'data-ak-contrast', 'dir'] });

if (isResearcher) setupPanel();
applyLang();
showStep('pick_specialty', { focus: false });

// For the researcher's browser console only (inspection while piloting).
window.AdaptKit = AdaptKit;
window.clinicDebug = { state };
