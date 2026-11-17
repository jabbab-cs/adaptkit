// AdaptKit runtime v0.1 — watches how a person uses a web page and adapts it
// (target size, text size, contrast, layout) using a trained policy file.
// Plain JavaScript ES module, no dependencies. Definitions: ../spec/features.md
//
// Usage:
//   import { AdaptKit } from './adaptkit.js';
//   await AdaptKit.init({ policy: 'policy.json', mode: 'adaptive', lang: 'en', participant: 'T001' });
//   <button data-adapt-target>Book</button>

export const VERSION = '0.1.0';

export const EVENT_COLUMNS = [
  'source', 'is_synthetic', 'participant', 'session', 'device', 'platform', 'condition', 'task', 'trial',
  'target_w', 'amplitude', 'hit', 'time_ms', 'misses', 'miss_dist_px', 'hesitation_ms', 'zoom',
  'target_x', 'target_y', 'tap_x', 'tap_y', 'ui_target_level', 'ui_text_level', 'ui_contrast', 'ui_layout',
  'policy_action', 'undo', 'outlier', 'timestamp',
];

export const ACTIONS = ['none', 'target_up', 'target_down', 'text_up', 'text_down', 'contrast_toggle', 'layout_toggle'];

// ---------------------------------------------------------------------------
// Pure functions (same results as adaptkit/python/adaptkit/features.py)
// ---------------------------------------------------------------------------

export function indexOfDifficulty(amplitude, targetW) {
  if (amplitude == null || targetW == null || !(targetW > 0)) return null;
  return Math.log2(amplitude / targetW + 1);
}

function speedRatio(event, policy) {
  const id = indexOfDifficulty(event.amplitude, event.target_w);
  if (id == null) return null;
  const ref = policy.reference_fitts[event.device];
  if (!ref) return null;
  const pred = ref.a_ms + ref.b_ms_per_bit * id;
  if (!(pred > 0)) return null;
  const r = event.time_ms / pred;
  if (policy.speed_ratio_cap != null && r > policy.speed_ratio_cap) return null; // a reading/deciding pause, not movement
  return r;
}

function median(values) {
  const s = [...values].sort((a, b) => a - b);
  const n = s.length;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

export function sigmoid(z) {
  return 1 / (1 + Math.exp(-z));
}

// Features over the last policy.window_size non-outlier events (one session, one device).
export function windowFeatures(events, policy) {
  const clean = events.filter((e) => e.outlier !== 1);
  const win = clean.slice(-policy.window_size);
  const out = { miss_rate: null, speed_ratio: null, variability: null, need: null };
  if (win.length === 0) return out;
  out.miss_rate = win.reduce((acc, e) => acc + (1 - e.hit), 0) / win.length;
  const ratios = win.map((e) => speedRatio(e, policy)).filter((r) => r != null);
  if (ratios.length > 0) out.speed_ratio = median(ratios);
  if (ratios.length >= 3) {
    const mean = ratios.reduce((a, b) => a + b, 0) / ratios.length;
    const variance = ratios.reduce((a, r) => a + (r - mean) ** 2, 0) / ratios.length;
    out.variability = mean > 0 ? Math.sqrt(variance) / mean : null;
  }
  if (out.miss_rate != null && out.speed_ratio != null && out.speed_ratio > 0) {
    const m = policy.need_model;
    const deviceTouch = win[win.length - 1].device === 'touch' ? 1 : 0;
    const z = m.intercept
      + m.coef.miss_rate * out.miss_rate
      + m.coef.log_speed_ratio * Math.log(out.speed_ratio)
      + m.coef.variability * (out.variability ?? 0)
      + m.coef.device_touch * deviceTouch;
    out.need = sigmoid(z);
  }
  return out;
}

export function binValue(value, thresholds) {
  if (value == null || Number.isNaN(value)) return Math.floor(thresholds.length / 2);
  return thresholds.filter((t) => t <= value).length;
}

export function stateKey(features, ui, device, policy) {
  const b = policy.bins;
  return [
    `m${binValue(features.miss_rate, b.miss_rate)}`,
    `s${binValue(features.speed_ratio, b.speed_ratio)}`,
    `v${binValue(features.variability, b.variability)}`,
    `n${binValue(features.need, b.need)}`,
    `t${ui.target}`, `x${ui.text}`, `c${ui.contrast}`, `l${ui.layout}`,
    `d${device === 'touch' ? 1 : 0}`,
  ].join('-');
}

const LEVEL_OF = { target_up: ['target', 1], target_down: ['target', -1], text_up: ['text', 1], text_down: ['text', -1] };
const LEVEL_LIST = { target: 'target_px', text: 'font_scale', contrast: 'contrast', layout: 'layout' };

export function applyAction(ui, action, policy) {
  const next = { ...ui };
  if (LEVEL_OF[action]) {
    const [key, step] = LEVEL_OF[action];
    next[key] = ui[key] + step;
  } else if (action === 'contrast_toggle') {
    next.contrast = ui.contrast === 0 ? 1 : 0;
  } else if (action === 'layout_toggle') {
    next.layout = ui.layout === 0 ? 1 : 0;
  }
  return next;
}

function inRange(ui, policy) {
  return Object.entries(LEVEL_LIST).every(([key, list]) => ui[key] >= 0 && ui[key] < policy.levels[list].length);
}

// ctx: { eventsSeen, undone: Set of actions undone this session }
export function shieldAction(action, ctx, ui, policy) {
  if (action === 'none') return 'none';
  if (ctx.eventsSeen < policy.shield.min_events_before_first_change) return 'none';
  if (policy.shield.block_undone_actions && ctx.undone.has(action)) return 'none';
  if (!inRange(applyAction(ui, action, policy), policy)) return 'none';
  return action;
}

export function decide(events, ui, ctx, policy) {
  const features = windowFeatures(events, policy);
  const device = events.length ? events[events.length - 1].device : 'mouse';
  const state = stateKey(features, ui, device, policy);
  const proposed = Object.prototype.hasOwnProperty.call(policy.table, state) ? policy.table[state] : policy.default_action;
  const action = shieldAction(proposed, ctx, ui, policy);
  return { features, state, proposed, action };
}

export function toCSV(events) {
  const cell = (v) => {
    if (v == null) return '';
    const s = String(v);
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [EVENT_COLUMNS.join(',')];
  for (const e of events) lines.push(EVENT_COLUMNS.map((c) => cell(e[c])).join(','));
  return lines.join('\n') + '\n';
}

// ---------------------------------------------------------------------------
// Browser runtime
// ---------------------------------------------------------------------------

const MESSAGES = {
  en: {
    target_up: 'Buttons made larger to make tapping easier.',
    target_down: 'Buttons made a little smaller to show more.',
    text_up: 'Text made larger to make reading easier.',
    text_down: 'Text made a little smaller to show more.',
    contrast_toggle: 'Contrast changed to make things clearer.',
    layout_toggle: 'Spacing changed to make the page easier to use.',
    undo: 'Undo',
  },
  ar: {
    target_up: 'تم تكبير الأزرار لتسهيل الضغط.',
    target_down: 'تم تصغير الأزرار قليلاً لعرض محتوى أكثر.',
    text_up: 'تم تكبير النص لتسهيل القراءة.',
    text_down: 'تم تصغير النص قليلاً لعرض محتوى أكثر.',
    contrast_toggle: 'تم تغيير التباين لجعل المحتوى أوضح.',
    layout_toggle: 'تم تغيير المسافات لتسهيل استخدام الصفحة.',
    undo: 'تراجع',
  },
};

const PRESS_SLOP_PX = 10;
const MISS_WINDOW_MS = 1500;

function distToRectEdge(x, y, r) {
  const dx = Math.max(r.left - x, 0, x - r.right);
  const dy = Math.max(r.top - y, 0, y - r.bottom);
  return Math.hypot(dx, dy);
}

function round(v, digits = 1) {
  if (v == null) return null;
  const f = 10 ** digits;
  return Math.round(v * f) / f;
}

function safeStorage(fn) {
  try { return fn(); } catch { return null; }
}

function download(text, filename) {
  const blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
}

function createRuntime() {
  let opts = null;
  let policy = null;
  let events = [];
  let ui = { target: 0, text: 0, contrast: 0, layout: 0 };
  let ctx = { eventsSeen: 0, undone: new Set() };
  let last = null; // { t, x, y } of previous selection or session start
  let firstActivityAt = null;
  let pendingMisses = [];
  let down = null;
  let zoomFlag = 0;
  let lastScale = null;
  let history = []; // [{ action, before, eventIndex }]
  let noticeEl = null;
  let noticeTimer = null;
  const listeners = { event: [], adapt: [], undo: [] };
  const handlers = [];

  const emit = (name, payload) => (listeners[name] || []).forEach((fn) => { try { fn(payload); } catch (err) { console.error(err); } });
  const now = () => performance.now();
  const STORAGE_PREFIX = 'adaptkit:';
  const storageKey = () => `${STORAGE_PREFIX}${opts.participant}:${opts.session}`;

  function clearUI(root) {
    root.style.removeProperty('--ak-target-min');
    root.style.removeProperty('--ak-font-scale');
    delete root.dataset.akContrast;
    delete root.dataset.akLayout;
  }

  // Never overwrite a saved log silently: keep a backup copy under a new key.
  function backupExisting() {
    const key = storageKey();
    const existing = safeStorage(() => localStorage.getItem(key));
    if (existing) safeStorage(() => localStorage.setItem(`${key}:backup-${new Date().toISOString()}`, existing));
  }

  function applyUI() {
    const root = opts.root;
    const lv = (policy && policy.levels) || DEFAULT_LEVELS;
    root.style.setProperty('--ak-target-min', `${lv.target_px[ui.target]}px`);
    root.style.setProperty('--ak-font-scale', String(lv.font_scale[ui.text]));
    root.dataset.akContrast = lv.contrast[ui.contrast];
    root.dataset.akLayout = lv.layout[ui.layout];
  }

  function persist() {
    safeStorage(() => localStorage.setItem(storageKey(), JSON.stringify({ events, ui, undone: [...ctx.undone] })));
  }

  function on(type, fn, target = document, options = { capture: true, passive: true }) {
    target.addEventListener(type, fn, options);
    handlers.push([target, type, fn, options]);
  }

  function ignored(el) {
    return el && el.closest && el.closest('[data-adapt-ignore]');
  }

  function onActivity() {
    if (firstActivityAt == null) firstActivityAt = now();
  }

  function onPointerDown(e) {
    if (ignored(e.target)) return;
    onActivity();
    down = { x: e.clientX, y: e.clientY, t: now(), target: e.target, pointerType: e.pointerType, id: e.pointerId, cancelled: false };
  }

  function onPointerMove(e) {
    if (ignored(e.target)) return;
    onActivity();
    if (down && down.id === e.pointerId && Math.hypot(e.clientX - down.x, e.clientY - down.y) > PRESS_SLOP_PX) down.cancelled = true;
  }

  function onPointerCancel() {
    if (down) down.cancelled = true;
  }

  function onPointerUp(e) {
    if (!down || down.id !== e.pointerId) return;
    const d = down;
    down = null;
    if (d.cancelled || Math.hypot(e.clientX - d.x, e.clientY - d.y) > PRESS_SLOP_PX) return;
    const targetEl = d.target.closest ? d.target.closest('[data-adapt-target]') : null;
    const t = now();
    if (!targetEl || targetEl.disabled || targetEl.getAttribute('aria-disabled') === 'true') {
      // Page coordinates, so scrolling before the next selection does not distort miss_dist_px.
      pendingMisses.push({ t, px: d.x + window.scrollX, py: d.y + window.scrollY });
      return;
    }
    recordSelection(targetEl, d, t);
  }

  function recordSelection(el, d, t) {
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const counted = pendingMisses.filter((m) => t - m.t <= MISS_WINDOW_MS);
    pendingMisses = [];
    const device = d.pointerType === 'mouse' ? 'mouse' : 'touch';
    const taskEl = el.closest('[data-adapt-task]');
    const event = {
      source: opts.source,
      is_synthetic: 0,
      participant: opts.participant,
      session: opts.session,
      device,
      platform: opts.platform,
      condition: opts.mode,
      task: (taskEl && taskEl.dataset.adaptTask) || opts.task,
      trial: events.length,
      target_w: round(Math.min(rect.width, rect.height)),
      amplitude: last && last.x != null ? round(Math.hypot(cx - last.x, cy - last.y)) : null,
      hit: counted.length === 0 ? 1 : 0,
      time_ms: round(t - last.t),
      misses: counted.length,
      miss_dist_px: counted.length
        ? round(distToRectEdge(counted[0].px - window.scrollX, counted[0].py - window.scrollY, rect))
        : null,
      hesitation_ms: firstActivityAt != null ? round(Math.max(0, firstActivityAt - last.t)) : null,
      zoom: zoomFlag,
      target_x: round(cx), target_y: round(cy), tap_x: round(d.x), tap_y: round(d.y),
      ui_target_level: ui.target, ui_text_level: ui.text, ui_contrast: ui.contrast, ui_layout: ui.layout,
      policy_action: null,
      undo: 0,
      outlier: 0,
      timestamp: new Date().toISOString(),
    };
    events.push(event);
    ctx.eventsSeen += 1;
    last = { t, x: d.x, y: d.y };
    firstActivityAt = null;
    zoomFlag = 0;
    emit('event', event);

    if (opts.mode === 'adaptive' && policy && ctx.eventsSeen % policy.decision_every === 0) {
      const sessionEvents = events.filter((ev) => ev.device === device);
      const result = decide(sessionEvents, ui, ctx, policy);
      event.policy_action = result.action;
      if (result.action !== 'none') {
        history.push({ action: result.action, before: { ...ui }, eventIndex: events.length - 1 });
        ui = applyAction(ui, result.action, policy);
        applyUI();
        showNotice(result.action);
      }
      emit('adapt', { ...result, ui: { ...ui } });
    }
    persist();
  }

  function onViewportResize() {
    const vv = window.visualViewport;
    if (!vv) return;
    if (lastScale != null && Math.abs(vv.scale - lastScale) > 0.01) zoomFlag = 1;
    lastScale = vv.scale;
  }

  function showNotice(action) {
    if (!opts.notice) return;
    const msg = (MESSAGES[opts.lang] || MESSAGES.en);
    if (!noticeEl) {
      noticeEl = document.createElement('div');
      noticeEl.className = 'ak-notice';
      noticeEl.setAttribute('role', 'status');
      noticeEl.setAttribute('aria-live', 'polite');
      noticeEl.setAttribute('data-adapt-ignore', '');
      document.body.appendChild(noticeEl);
    }
    noticeEl.dir = opts.lang === 'ar' ? 'rtl' : 'ltr';
    noticeEl.innerHTML = '';
    const text = document.createElement('span');
    text.textContent = msg[action] || '';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'ak-notice-undo';
    btn.textContent = msg.undo;
    btn.addEventListener('click', () => api.undoLast());
    noticeEl.append(text, btn);
    noticeEl.hidden = false;
    clearTimeout(noticeTimer);
    noticeTimer = setTimeout(() => { if (noticeEl) noticeEl.hidden = true; }, opts.noticeMs);
  }

  const api = {
    VERSION,

    async init(options = {}) {
      if (opts) api.destroy();
      opts = {
        mode: 'static',
        source: 'usability',
        participant: 'anon',
        session: `s${Date.now()}`,
        task: 'task',
        lang: 'en',
        notice: true,
        noticeMs: 8000,
        root: document.documentElement,
        platform: window.matchMedia && window.matchMedia('(pointer: coarse)').matches ? 'mobile' : 'web',
        resume: false,
        ...options,
      };
      policy = null;
      if (opts.policy) {
        if (typeof opts.policy === 'string') {
          const res = await fetch(opts.policy);
          if (!res.ok) { opts = null; throw new Error(`AdaptKit: could not load policy (${res.status})`); }
          policy = await res.json();
        } else {
          policy = opts.policy;
        }
        if (policy.is_placeholder && opts.mode === 'adaptive') console.warn('AdaptKit: this policy is a placeholder, not a trained policy.');
      }
      if (opts.mode === 'adaptive' && !policy) { opts = null; throw new Error('AdaptKit: adaptive mode needs a policy'); }
      events = [];
      ui = { target: 0, text: 0, contrast: 0, layout: 0 };
      ctx = { eventsSeen: 0, undone: new Set() };
      history = [];
      if (opts.resume) {
        const saved = safeStorage(() => JSON.parse(localStorage.getItem(storageKey())));
        if (saved) {
          events = saved.events || [];
          ui = saved.ui || ui;
          ctx = { eventsSeen: events.length, undone: new Set(saved.undone || []) };
        }
      } else {
        backupExisting();
      }
      last = { t: now(), x: null, y: null };
      firstActivityAt = null;
      pendingMisses = [];
      lastScale = window.visualViewport ? window.visualViewport.scale : null;
      applyUI();
      on('pointerdown', onPointerDown);
      on('pointermove', onPointerMove);
      on('pointerup', onPointerUp);
      on('pointercancel', onPointerCancel);
      if (window.visualViewport) on('resize', onViewportResize, window.visualViewport, { passive: true });
      return api;
    },

    // Call when a new task starts, so the first selection's time is measured from here.
    startTask(task) {
      if (!opts) return;
      if (task) opts.task = task;
      last = { t: now(), x: last ? last.x : null, y: last ? last.y : null };
      firstActivityAt = null;
      pendingMisses = [];
    },

    undoLast() {
      const h = history.pop();
      if (!h) return false;
      ui = h.before;
      applyUI();
      if (policy && policy.shield.block_undone_actions) ctx.undone.add(h.action);
      if (events[h.eventIndex]) events[h.eventIndex].undo = 1;
      if (noticeEl) noticeEl.hidden = true;
      emit('undo', { action: h.action, ui: { ...ui } });
      persist();
      return true;
    },

    on(name, fn) {
      if (!listeners[name]) listeners[name] = [];
      listeners[name].push(fn);
      return () => { listeners[name] = listeners[name].filter((f) => f !== fn); };
    },
    getEvents() { return events.map((e) => ({ ...e })); },
    getUI() { return { ...ui }; },
    getPolicy() { return policy; },
    exportCSV() { return toCSV(events); },

    // Language of the adaptation notice ('en' or 'ar'); can change mid-session.
    setLang(lang) {
      if (opts) opts.lang = lang;
      if (noticeEl) noticeEl.hidden = true;
    },

    downloadCSV(filename) {
      const name = filename || (opts ? `adaptkit_${opts.participant}_${opts.session}.csv` : 'adaptkit_events.csv');
      download(toCSV(events), name);
    },

    // Every log saved in this browser (current, earlier and backup copies), newest last.
    savedSessions() {
      const keys = [];
      safeStorage(() => {
        for (let i = 0; i < localStorage.length; i += 1) {
          const k = localStorage.key(i);
          if (k && k.startsWith(STORAGE_PREFIX)) keys.push(k);
        }
      });
      return keys.sort();
    },

    // One CSV with every saved log in this browser; a recovery tool, never deletes anything.
    downloadAllSaved(filename = 'adaptkit_all_saved.csv') {
      const all = [];
      for (const key of api.savedSessions()) {
        const saved = safeStorage(() => JSON.parse(localStorage.getItem(key)));
        if (saved && Array.isArray(saved.events)) all.push(...saved.events);
      }
      download(toCSV(all), filename);
      return all.length;
    },

    clearSaved() { if (opts) safeStorage(() => localStorage.removeItem(storageKey())); },

    destroy() {
      handlers.splice(0).forEach(([target, type, fn, options]) => target.removeEventListener(type, fn, options));
      clearTimeout(noticeTimer);
      if (noticeEl) { noticeEl.remove(); noticeEl = null; }
      if (opts) clearUI(opts.root);
      opts = null;
    },
  };
  return api;
}

const DEFAULT_LEVELS = { target_px: [32, 44, 64], font_scale: [1, 1.5, 2], contrast: ['normal', 'high'], layout: ['compact', 'spacious'] };

export const AdaptKit = typeof window !== 'undefined' ? createRuntime() : null;
