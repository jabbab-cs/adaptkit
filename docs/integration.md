# Add AdaptKit to your website

AdaptKit is one JavaScript file and one CSS file, with no dependencies. It works with plain HTML and with any framework (React, Vue, Svelte, Angular…) because it only listens to pointer events and sets CSS variables.

## 1. Load the files

From a CDN (replace `vX.Y.Z` with a release tag):

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/jabbab-cs/adaptkit@vX.Y.Z/js/adaptkit.css">
<script type="module">
  import { AdaptKit } from 'https://cdn.jsdelivr.net/gh/jabbab-cs/adaptkit@vX.Y.Z/js/adaptkit.js';
  await AdaptKit.init({
    mode: 'adaptive',
    policy: 'https://cdn.jsdelivr.net/gh/jabbab-cs/adaptkit@vX.Y.Z/policies/default.json',
  });
</script>
```

Or copy `js/adaptkit.js`, `js/adaptkit.css` and `policies/default.json` into your project and load them from your own server.

## 2. Mark what people press

```html
<button data-adapt-target>Book</button>
<a href="/cart" data-adapt-target>Cart</a>
```

| Attribute | Put it on | Meaning |
|---|---|---|
| `data-adapt-target` | buttons, links, cards, inputs | Something a person aims at. A press on it is a *selection*; a press beside it (within 1.5 s) is a *miss*. |
| `data-adapt-task="name"` | a container (a page step, a form) | Groups selections by task in the log. |
| `data-adapt-ignore` | a container | Nothing inside is recorded (admin panels, cookie banners). |

## 3. Let your CSS follow the adaptations

AdaptKit sets four values on `<html>`. Your styles decide what they do:

```css
html { font-size: calc(16px * var(--ak-font-scale, 1)); }        /* text size: 1, 1.5, 2 */
button, [data-adapt-target] {
  min-width: var(--ak-target-min, 32px);                            /* target size: 32, 44, 64 px */
  min-height: var(--ak-target-min, 32px);
}
[data-ak-contrast="high"] { /* your high-contrast theme */ }
[data-ak-layout="spacious"] .toolbar { gap: 1.5rem; }               /* more spacing */
```

Use `rem` units for text so the font scale reaches everything, and test your layout at font scale 2 on a 360 px-wide phone.

## Options

| Option | Default | Meaning |
|---|---|---|
| `mode` | `'static'` | `'static'` records only; `'adaptive'` also changes the page (needs `policy`) |
| `policy` | – | URL or object of a policy file (see `spec/policy.schema.json`) |
| `lang` | `'en'` | Language of the notice: `'en'` or `'ar'` (change later with `setLang`) |
| `notice` / `noticeMs` | `true` / `8000` | Show the "what changed + Undo" notice, and for how long |
| `participant`, `session`, `source`, `task` | – | Labels written into every logged event |
| `resume` | `false` | Continue a session saved earlier in this browser |

## API

| Call | What it does |
|---|---|
| `await AdaptKit.init(options)` | Start watching and (in adaptive mode) adapting |
| `AdaptKit.startTask(name)` | A new task starts now (times are measured from here) |
| `AdaptKit.undoLast()` | Undo the last change (the notice's button calls this) |
| `AdaptKit.setLang('ar')` | Change the notice language |
| `AdaptKit.on('event' / 'adapt' / 'undo', fn)` | Listen to selections, decisions and undos |
| `AdaptKit.getEvents()` / `getUI()` / `getPolicy()` | Read the log, the current levels, the policy |
| `AdaptKit.exportCSV()` / `downloadCSV(name)` | The log as CSV text / as a downloaded file |
| `AdaptKit.savedSessions()` / `downloadAllSaved()` | Every log saved in this browser (a recovery tool) |
| `AdaptKit.destroy()` | Stop, remove listeners and reset the page styles |

## Privacy

- AdaptKit records **positions and timings only**. It never reads what people type.
- Logs stay in the visitor's browser (`localStorage`) until you export them. Nothing is sent anywhere.
- If you collect logs for research, ask for consent first, and tell people the page may adapt.

## Good to know

- Keyboard-only use (Tab + Enter) is not recorded in v0.1.
- The trained policy was learned from simulated users based on real pointing data. Test it with your own users before relying on it.
