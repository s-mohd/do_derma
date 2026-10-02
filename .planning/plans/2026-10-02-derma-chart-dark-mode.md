# Derma Chart Dark Mode (Phase 2c) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The derma chart follows desk's dark theme with the Patient Overview's dark palette, while the annotation studio and prints stay light.

**Architecture:** A `[data-theme="dark"]` block redefines the `--chart-*` tokens on the chart page and `.modal`. A new `--chart-accent-text` token keeps accent-coloured text readable on dark. Desk's light pinning moves from the chart page to the studio. Every literal colour left in `derma_chart.bundle.css` becomes a token, so the dark block reaches everything. Source tests pin the palette, its scope, contrast and the absence of hex. Browser checks prove light mode unchanged and dark mode free of light islands.

**Tech Stack:** CSS custom properties, `color-mix()`, Vue 3.5 SFCs, Python `unittest.TestCase` source tests, `bench build --app do_derma`, agent-browser.

**Spec:** `.planning/specs/2026-10-02-derma-chart-dark-mode.md`

## Global Constraints

- Branch `feat/derma-chart-dark-mode` (cut from `feat/derma-chart-panel-restyle`).
- Dark trigger: `[data-theme="dark"]` on `<html>` only. No toggle, no JavaScript.
- Dark block selector: `[data-theme="dark"] .dental-chart-page.derma-chart-page, [data-theme="dark"] .modal`. It must **not** include `.derma-annotation-modal`.
- Desk-variable light pinning selector becomes `[data-theme="dark"] .derma-annotation-modal`.
- `.modal` may appear only in token blocks and under `body.derma-annotation-open`.
- `--chart-accent-strong` stays `color-mix(in srgb, var(--chart-accent) 70%, black)` in both themes. `--chart-accent-text` = `var(--chart-accent-strong)` in light, `color-mix(in srgb, var(--chart-accent) 70%, white)` in dark. Dark `--chart-accent-soft` = `color-mix(in srgb, var(--chart-accent) 18%, var(--chart-surface))`.
- Light mode must not change except where a literal was mapped to its nearest token; every such change is reviewed.
- Out of scope: `annotation/**` JSX, print HTML in `DermaChart.vue`, `VoiceWaveform.vue` canvas fallbacks, the early-closing `@media`, any do_health change.
- Commits end with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Commands

- Theme tests: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_chart_theme 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s|AssertionError|Error:"`
- Build: `bench build --app do_derma`, then restart the bench-v16 `frappe serve --port 8002` (cwd `bench-v16/sites`). The session scratchpad `rebuild.sh` does both.
- Browser: scratchpad `open.sh WIDTH NAME [patient appointment encounter]` (logs in if needed). Dark: `agent-browser eval "document.documentElement.setAttribute('data-theme','dark')"`. Light: same with `'light'`.
- Suite: `bench --site dermaone.localhost run-tests --app do_derma`, diff failing names against `main`'s 5.

## Review Focus

1. **Text on filled backgrounds under dark.** `var(--derma-white)` used as text colour would turn near-black. Task 2 maps the three known uses to `white`, and Task 3's island scan checks contrast of filled buttons and badges.
2. **Desk controls inside the chart under dark** (link fields, prescription grid, selects). They must turn dark with desk, not stay white. Pinned by Task 1 (pinning retargeted) and Task 3's island scan on the Prescription tab.
3. **Chart dialogs (frappe `.modal`) under dark.** Custom content (`.panel-muted`, previews) must read dark tokens. Pinned by Task 3, which opens Copy marks, Procedure details and the annotation review dialog.
4. **Studio opened while desk is dark.** It must stay light, including desk inputs inside it. Pinned by Task 1 `test_studio_stays_light` and Task 3's studio check.
5. **Accent text contrast on dark** for light or mid settings colours. Pinned by Task 1 `test_accent_text_reads_on_dark` for `#16a34a` and `#EC864B`, and Task 3's purple run.

---

## File structure

| File | Change |
|---|---|
| `do_derma/tests/test_chart_theme.py` | Dark parity, scope, pin, contrast, `.modal` guard and no-hex tests; retire the light-only tests |
| `do_derma/public/js/chart/derma_chart.bundle.css` | Dark block, `--chart-accent-text`, retargeted pinning, `color-scheme`, every literal mapped |
| `components/shell/SectionTabs.vue`, `components/shell/ChartHero.vue`, `components/ProcedurePanel.vue` | Accent text uses `--chart-accent-text` |

---

### Task 1: Dark tokens, accent text, studio pinning, tests

**Files:** `test_chart_theme.py`; `derma_chart.bundle.css`; `SectionTabs.vue`; `ChartHero.vue`; `ProcedurePanel.vue`

**Interfaces:**
- Produces: `--chart-accent-text`; the dark block; `get_rule_body(css, selector_start) -> str` and `OVERVIEW_DARK_FIRST` in the test, which Task 2 reuses.

- [ ] **Step 1: Replace the light-only tests with failing dark tests**

In `test_chart_theme.py`:
- Change `DARK_SCOPE` to `'[data-theme="dark"] .derma-annotation-modal {'` and the `TestChartDarkMode` docstring to `"""Desk dark mode must not leak dark text or control colours into the light annotation studio."""`. Rename its test to `test_studio_stays_light`.
- Delete `test_chart_tokens_are_not_overridden_in_dark_mode`.
- Add:

```python
DARK_CHART_SELECTOR = '[data-theme="dark"] .dental-chart-page.derma-chart-page'
OVERVIEW_DARK_SELECTOR = '[data-theme="dark"] .do-health-drawer--overview'


def get_rule_body(css: str, selector_start: str) -> str:
	"""Body of the first rule whose selector list starts with `selector_start`."""
	css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
	start = css.index(selector_start)
	return css[css.index("{", start) + 1 : css.index("}", start)]


def get_variables(body: str) -> dict[str, str]:
	return {name: value.strip() for name, value in re.findall(r"(--[\w-]+):\s*([^;]+);", body)}


def mix(hex_colour: str, share: float, other: tuple[int, int, int]) -> str:
	channels = [int(hex_colour[i : i + 2], 16) for i in (1, 3, 5)]
	return "#" + "".join(f"{round(c * share + o * (1 - share)):02x}" for c, o in zip(channels, other))


def get_contrast(first: str, second: str) -> float:
	lighter, darker = sorted((get_relative_luminance(first), get_relative_luminance(second)), reverse=True)
	return (lighter + 0.05) / (darker + 0.05)


class TestChartDarkPalette(TestCase):
	"""Under desk dark mode the chart and its dialogs take the Overview's dark palette."""

	def get_dark_tokens(self):
		return get_variables(get_rule_body(CHART_CSS.read_text(), DARK_CHART_SELECTOR))

	def test_every_overview_dark_token_has_a_chart_twin(self):
		overview_css = Path(frappe.get_app_path("do_health", "public", "css", "health_sidebar.css")).read_text()
		overview = get_variables(get_rule_body(overview_css, OVERVIEW_DARK_SELECTOR))
		dark = self.get_dark_tokens()
		for name, value in overview.items():
			self.assertEqual(dark.get(name.replace("--ov-", "--chart-", 1)), value, name)

	def test_dark_block_covers_page_and_dialogs_but_not_the_studio(self):
		css = re.sub(r"/\*.*?\*/", "", CHART_CSS.read_text(), flags=re.S)
		start = css.index(DARK_CHART_SELECTOR)
		selectors = [part.strip() for part in css[start : css.index("{", start)].split(",")]
		self.assertIn('[data-theme="dark"] .modal', selectors)
		self.assertFalse(any("derma-annotation-modal" in part for part in selectors))
		self.assertIn("color-scheme: dark", get_rule_body(CHART_CSS.read_text(), DARK_CHART_SELECTOR))

	def test_accent_text_reads_on_dark(self):
		dark = self.get_dark_tokens()
		self.assertEqual(dark["--chart-accent-text"], "color-mix(in srgb, var(--chart-accent) 70%, white)")
		for accent in ("#16a34a", "#EC864B"):
			self.assertGreaterEqual(get_contrast(mix(accent, 0.7, (255, 255, 255)), dark["--chart-surface"]), 4.5, accent)

	def test_light_accent_text_matches_filled_buttons(self):
		light = get_token_block(CHART_CSS.read_text(), CHART_FIRST_TOKEN)
		self.assertEqual(light["--chart-accent-text"], "var(--chart-accent-strong)")

	def test_modal_selector_only_in_token_blocks(self):
		css = re.sub(r"/\*.*?\*/", "", CHART_CSS.read_text(), flags=re.S)
		for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
			if not re.search(r"\.modal(?![\w-])", selector) or "body.derma-annotation-open" in selector:
				continue
			real = [line for line in body.split(";") if line.strip() and not line.strip().startswith("--") and "color-scheme" not in line]
			self.assertEqual(real, [], selector.strip())
```

- [ ] **Step 2: Run, confirm RED**

Expected failures: `test_studio_stays_light` (`ValueError`/`AssertionError`: studio pin block missing), every new `TestChartDarkPalette` test (`ValueError: substring not found` for the dark selector), `test_light_accent_text_matches_filled_buttons` (`KeyError`).

- [ ] **Step 3: Implement the tokens**

In the light token block, after `--chart-accent-soft: …;` add:

```css
  --chart-accent-text: var(--chart-accent-strong);
```

Retarget the pinning block: change `[data-theme="dark"] .dental-chart-page.derma-chart-page {` (the one under `/* The chart is light-only … */`) to `[data-theme="dark"] .derma-annotation-modal {` and its comment to `/* The annotation studio stays light: pin Frappe's dark-mode variables to their v16 light values. */`.

Directly after the light token block, add:

```css
/* Desk dark mode: the Patient Overview's dark palette (do_health --ov-*, dark). The studio keeps the light block. */
[data-theme="dark"] .dental-chart-page.derma-chart-page,
[data-theme="dark"] .modal {
  color-scheme: dark;
  --chart-bg: #141414;
  --chart-surface: #1e1e1e;
  --chart-surface-muted: #262626;
  --chart-border: rgba(255, 255, 255, 0.08);
  --chart-border-strong: rgba(255, 255, 255, 0.16);
  --chart-text: #f4f4f5;
  --chart-text-soft: #d4d4d8;
  --chart-muted: #a1a1aa;
  --chart-faint: #71717a;
  --chart-shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 10px 28px -18px rgba(0, 0, 0, 0.6);
  --chart-focus: 0 0 0 3px rgba(96, 165, 250, 0.4);
  --chart-danger: #f43f5e;
  --chart-danger-soft: rgba(244, 63, 94, 0.12);
  --chart-danger-border: rgba(244, 63, 94, 0.3);
  --chart-danger-text: #fda4af;
  --chart-caution: #f59e0b;
  --chart-caution-soft: rgba(245, 158, 11, 0.12);
  --chart-caution-border: rgba(245, 158, 11, 0.3);
  --chart-caution-text: #fcd34d;
  --chart-ok: #34d399;
  --chart-ok-soft: rgba(52, 211, 153, 0.12);
  --chart-ok-text: #6ee7b7;
  --chart-info-soft: rgba(96, 165, 250, 0.12);
  --chart-info-text: #93c5fd;
  --chart-teal: #2dd4bf;
  --chart-violet: #a78bfa;
  --chart-blue: #60a5fa;
  --chart-rose: #fb7185;
  --chart-amber: #fbbf24;
  --chart-brand: #22c55e;
  --chart-accent-soft: color-mix(in srgb, var(--chart-accent) 18%, var(--chart-surface));
  --chart-accent-text: color-mix(in srgb, var(--chart-accent) 70%, white);
}
```

Check these values against `do_health/public/css/health_sidebar.css` `[data-theme="dark"] .do-health-drawer--overview` before saving; the parity test enforces it.

- [ ] **Step 4: Point accent text at the new token**

- `SectionTabs.vue` lines ~77 and ~88: `color: var(--chart-accent-strong);` → `color: var(--chart-accent-text);`
- `ChartHero.vue` `.chart-hero-avatar` (~215): same change.
- `ProcedurePanel.vue` `.derma-detail-chip` (~2308): same change.
- `derma_chart.bundle.css`: in `.dental-chart-page .chart-pill[data-tone="accent"], …[aria-pressed="true"]` change `color: var(--chart-accent-strong);` → `color: var(--chart-accent-text);`. Then replace every exact `  color: var(--derma-brand);` line with `  color: var(--chart-accent-text);` (15 lines; leave `background`, `border-color` and `accent-color` uses alone).

- [ ] **Step 5: GREEN and light unchanged**

Run the theme tests: all pass. Build, open the draft chart at 1600 in light. Check that the active tab colour, avatar initials and an accent pill are unchanged from before this task (`getComputedStyle(...).color`), because `--chart-accent-text` equals `--chart-accent-strong` in light.

- [ ] **Step 6: Commit**

```bash
git add -A do_derma/public/js/chart do_derma/tests/test_chart_theme.py
git commit -m "feat(chart): dark tokens for the chart and its dialogs; the studio stays light

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: The stylesheet goes token-only

**Files:** `derma_chart.bundle.css`; `test_chart_theme.py`

**Interfaces:** Consumes `get_rule_body`, `DARK_CHART_SELECTOR` (Task 1).

- [ ] **Step 1: Failing test**

```python
TOKEN_BLOCK_STARTS = (".dental-chart-page.derma-chart-page,", DARK_CHART_SELECTOR, DARK_SCOPE.rstrip(" {"))


class TestChartStylesheetColours(TestCase):
	"""Outside the token blocks the stylesheet reads tokens, so both themes reach every rule."""

	def test_no_hex_outside_token_blocks(self):
		css = re.sub(r"/\*.*?\*/", "", CHART_CSS.read_text(), flags=re.S)
		offenders = []
		for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
			if selector.strip().startswith(TOKEN_BLOCK_STARTS):
				continue
			offenders += [f"{selector.strip()[:60]}: {value}" for value in HEX_COLOUR.findall(body)]
		self.assertEqual(offenders, [])

	def test_text_on_fills_is_never_the_surface_token(self):
		self.assertNotRegex(CHART_CSS.read_text(), r"(?<![\w-])color:\s*var\(--derma-white\)")
```

Run: expected `test_no_hex_outside_token_blocks` fails listing about 56 values, and `test_text_on_fills_is_never_the_surface_token` fails.

- [ ] **Step 2: Map every literal**

Apply this table to `derma_chart.bundle.css` outside the three token blocks (line numbers are from the start of 2c and will drift by Task 1's insertions; match on selector and value):

| Rule | Literal | Replacement |
|---|---|---|
| `.derma-section-actions button:hover` | `#5eead4` | `color-mix(in srgb, var(--chart-accent) 35%, transparent)` |
| same | `#f0fdfa` | `var(--chart-accent-soft)` |
| `.derma-annotation-pick`, `.derma-annotation-review-image img` | `#e5e7eb` | `var(--chart-border)` |
| `.derma-annotation-pick-preview`, `.derma-annotation-pick-data` | `#f8fafc` | `var(--chart-surface-muted)` |
| `.derma-annotation-pick-preview`, `.chart-annotation-preview` | `#94a3b8` | `var(--chart-faint)` |
| `.chart-annotation-delete:hover` | `var(--red-4, #e03131)` | `var(--chart-danger)` |
| `.derma-annotation-preview-dialog img`, `.derma-annotation-preview-data`, `.derma-annotation-search` | `#fff` | `var(--chart-surface)` |
| `.skeleton-block` | `#eef1f5` / `#e2e7ee` | `var(--chart-surface-muted)` / `var(--chart-border-strong)` |
| `.chart-refresh-banner` | `var(--derma-surface-muted, #f6f8fa)` | `var(--chart-surface-muted)` |
| `.chart-error-banner` | `#fef3f2` / `#fda29b` | `var(--chart-danger-soft)` / `var(--chart-danger-border)` |
| `.derma-session-summary .attention` | `#9a3412` | `var(--chart-caution-text)` |
| `.error-overlay` | `rgba(255, 255, 255, 0.7)` | `color-mix(in srgb, var(--chart-surface) 70%, transparent)` |
| `.embedded-excalidraw .excalidraw` | `#0d5f5a` / `#0b4d49` | `color-mix(in srgb, var(--chart-accent-strong) 85%, black)` / `color-mix(in srgb, var(--chart-accent-strong) 70%, black)` |
| `.derma-annotation-canvas .excalidraw` | `#ccfbf1` | `var(--chart-accent-soft)` |
| `.readiness-mode[data-mode="Block"]`, `.readiness-blocker-list li` | `var(--derma-danger, #c0392b)` | `var(--chart-danger-text)` |
| `.followup-card.high`, `.inventory-card.blocked` | `#fff7f7` | `var(--chart-danger-soft)` |
| `.followup-card.medium`, `.inventory-card.warning` | `#fffaf2` | `var(--chart-caution-soft)` |
| `.followup-card.low` | `#f8fbff` | `var(--chart-info-soft)` |
| `.inventory-card.ready`, `.followup-card.done` | `#f7fef9`, `#f0fdf4` | `var(--chart-ok-soft)` |
| `.inventory-metrics span` | `rgba(148, 163, 184, 0.35)` / `rgba(255, 255, 255, 0.72)` | `var(--chart-border-strong)` / `color-mix(in srgb, var(--chart-surface) 72%, transparent)` |
| `.pill.complete` / `.pill.cancelled` / `.pill.draft` | `#047857` / `#fef2f2`, `#b91c1c` / `#c2410c` | `var(--chart-ok-text)` / `var(--chart-danger-soft)`, `var(--chart-danger-text)` / `var(--chart-caution-text)` |
| `.derma-annotation-shell` / `.derma-annotation-right` | `#f8fbfd` / `#f3f7f9` | `var(--chart-surface-muted)` / `var(--chart-bg)` |
| `.derma-template-show-all` | `#475569` | `var(--chart-text-soft)` |
| `.derma-treatment-list button span:first-child` | `var(--treatment-color, #0ea5e9)` | `var(--treatment-color, var(--chart-blue))` |
| `.voice-scribe .voice-stop` | `#dc2626` (border, background) / `#fff` | `color-mix(in srgb, var(--chart-danger) 85%, black)` / `white` |
| `@keyframes` pulse | `rgba(220, 38, 38, 0.18)` | `color-mix(in srgb, var(--chart-danger) 18%, transparent)` |
| `.voice-scribe[data-state="failed"] .voice-hint`, `.voice-scribe .voice-level[data-zone="loud"]`, `.ai-documents .error-text` | `#b91c1c` | `var(--chart-danger-text)` |
| `.voice-waveform` | `#f4f4f5` / `--wave-bar: #ef4444` / `--wave-head: #dc2626` | `var(--chart-surface-muted)` / `var(--chart-danger)` / `var(--chart-danger-text)` |
| `.voice-waveform[data-paused="true"]` | `#a1a1aa` / `#71717a` | `var(--chart-faint)` / `var(--chart-muted)` |
| `.voice-scribe .voice-level` | `#15803d` | `var(--chart-ok-text)` |
| `.voice-level[data-zone="low"]`, `.voice-warning` | `#b45309` | `var(--chart-caution-text)` |
| radial-gradient glows | `rgba(20, 184, 166, 0.08)` / `rgba(15, 118, 110, 0.045)` | `color-mix(in srgb, var(--chart-accent) 8%, transparent)` / `color-mix(in srgb, var(--chart-accent) 4.5%, transparent)` |
| `.derma-annotation-tagging-banner .stop-tagging:hover`, `.derma-annotation-header-actions button.primary`, `.photo-stage-badge` | `color: var(--derma-white)` | `color: white` |
| `.dental-chart-page .primary` | `color: white` | unchanged |
| `.photo-viewer` | `rgba(0, 0, 0, 0.72)` | unchanged (scrim) |

Any hex the test still lists after the table: map by role using the 2b hex map and record it in the commit body.

- [ ] **Step 3: GREEN**

Run the theme tests: all pass.

- [ ] **Step 4: Light-mode review**

Build the commit before this task (`git stash`), dump computed styles of every element (scratchpad `styles.sh before`: five tabs, materials editor, consent dialog), then pop and dump `after`. List every changed property. Accept only changes that come from a row in the table above (expected: skeleton shade, banners, follow-up and inventory tints, voice controls, which are slight shifts). Revert or re-map anything else.

- [ ] **Step 5: Commit**

```bash
git add do_derma/public/js/chart/derma_chart.bundle.css do_derma/tests/test_chart_theme.py
git commit -m "refactor(chart): every stylesheet colour reads a token

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Dark-mode verification and island fixes

**Files:** whichever rules the scan names (`derma_chart.bundle.css` or a component `<style>`).

- [ ] **Step 1: Light-island scan**

Save as scratchpad `islands.js` and run it with `agent-browser eval` under `data-theme="dark"` on each state below:

```js
(() => {
  const near = (c) => { const m = c.match(/\d+(\.\d+)?/g); if (!m) return false; const [r, g, b, a = 1] = m.map(Number); return a > 0.5 && r > 225 && g > 225 && b > 225 }
  const roots = [document.querySelector('.derma-chart-page'), ...document.querySelectorAll('.modal.show')].filter(Boolean)
  const hits = []
  for (const root of roots) for (const el of [root, ...root.querySelectorAll('*')]) {
    if (el.closest('.derma-annotation-modal') || ['IMG', 'CANVAS', 'VIDEO', 'svg'].includes(el.tagName) || !el.offsetParent) continue
    if (near(getComputedStyle(el).backgroundColor)) hits.push(el.tagName + '.' + String(el.className).slice(0, 60))
  }
  return JSON.stringify({ count: hits.length, hits: [...new Set(hits)].slice(0, 25) })
})()
```

States: Assessment, Procedures, Photos, Prescription, Review, Materials editor open, consent dialog, Copy marks dialog, a procedure's details dialog, at 1280 and 1600. Target: `count: 0`.

- [ ] **Step 2: Fix each island**

For each hit, find the rule giving it a light background (DevTools-style: `getComputedStyle` plus grep on the class) and replace the literal or desk variable with a `--chart-*` token. Re-run the scan after each fix. Desk-owned controls (`.form-control`, `.grid-row`) should already be dark once Task 1 removed the page pinning; if one is not, find which desk variable it reads and confirm it is not pinned anywhere in the chart's stylesheet.

- [ ] **Step 3: Readability pass**

Screenshot each state in dark at 1600 and look at it: text on filled buttons white, pills legible, accent text readable, OK green distinct from the accent, danger and caution tints visible.

- [ ] **Step 4: Studio under dark**

With `data-theme="dark"`, open Annotate Consultation. Expected: header background `rgb(255, 255, 255)`, Templates/Fit/Cancel outlined, Save filled accent, canvas white. Screenshot.

- [ ] **Step 5: Accent and Automatic**

- Set `sidebar_header_color` to `#7c3aed` (bench console), clear cache, reload in dark: accent purple, OK green green. Restore the site's original value (read it first; dermaone has `#EC864B`) and clear cache.
- Desk theme Automatic (`frappe.ui.set_theme` or the theme switcher), then emulate OS dark/light via `agent-browser` media emulation if available, else toggle `data-theme` as desk does. Confirm the chart follows without reload.

- [ ] **Step 6: Theme tests, suite, commit**

Run the theme tests (all pass) and the full suite (no failure outside `main`'s 5). Commit fixes from Step 2:

```bash
git add -A do_derma/public/js/chart do_derma/tests/test_chart_theme.py
git commit -m "fix(chart): no light islands under dark mode

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

If Step 2 needed no fixes, skip the commit and record that in the ledger.
