# Derma Chart Panel Restyle (Phase 2b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle every panel inside the derma chart's section cards to the Patient Overview look, using an accent read from Do Health Settings, with section-level actions moved into the card header.

**Architecture:** Three new accent tokens derive from do_health's `--do-health-header-accent`. The old `--derma-*` palette becomes aliases of `--chart-*`, and shared buttons, pills, labels, inner cards and inputs are defined once in `derma_chart.bundle.css`. Each panel then drops its hardcoded hex colours, adopts the shared classes, and teleports its section buttons into `#chart-section-actions` in `SectionCard`. Source-reading Python tests pin the colour wiring and drive the hex removal panel by panel.

**Tech Stack:** Frappe v16, Vue 3.5 SFCs (`<Teleport defer>`), CSS `color-mix()`, Python `unittest.TestCase` source tests, `bench build --app do_derma`.

**Spec:** `.planning/specs/2026-10-01-derma-chart-panel-restyle.md`

## Global Constraints

- Branch `feat/derma-chart-panel-restyle` (cut from `feat/derma-chart-overview-skin`).
- Accent: `--chart-accent: var(--do-health-header-accent, #16a34a)`; `--chart-accent-strong: color-mix(in srgb, var(--chart-accent) 82%, black)`; `--chart-accent-soft: color-mix(in srgb, var(--chart-accent) 10%, white)`.
- "OK" green stays `--chart-ok` / `--chart-ok-soft` / `--chart-ok-text`. Never the accent.
- One filled (`.primary`) button per card header. Every other header button is `.ghost`.
- Behaviour unchanged: keep every handler, `:disabled` rule and `data-test` name.
- New shared CSS goes in one block directly after the `--chart-*` token block in `derma_chart.bundle.css`, before line ~200. Nothing else is added to that file. Existing rules may be edited or deleted.
- Out of scope: dark mode, `annotation/**`, print HTML strings in `DermaChart.vue`, the canvas fallbacks in `VoiceWaveform.vue` (outside `<style>`), the early-closing `@media` bug, any do_health change.
- Repo rules (`CLAUDE.md`): terse comments, no file-top comments, no abbreviations, complexity ≤ 8.
- Commits: `<type>: <description>` + body, ending `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Test and build commands (bench quirks)

- Run from `/Users/hameed/Developer/bench-v16`. `--test` takes the **bare method name** only. A class name silently runs nothing.
- Theme tests: `bench --site dermaone.localhost run-tests --module do_derma.tests.test_chart_theme 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s|AssertionError"`
- Build: `bench build --app do_derma`, then **restart the web server** (`frappe serve --port 8002` whose cwd is `bench-v16/sites`), or `/assets/do_derma/...` 404s.
- Browser: `bench --site dermaone.localhost browse --user Administrator` prints a port-8002 login URL. Chart URL: `http://dermaone.localhost:8002/app/derma-chart?patient=PAT-2017-10285&appointment=APT-2026-9474&encounter=HLC-ENC-2026-18379` (open draft). Submitted: `...&appointment=APT-2026-7472&encounter=HLC-ENC-2026-17613`.
- The suite has a red baseline on `main` (5 names). Judge by diffing failing names, never by "all green".

## Hex map (used by every panel task)

Replace each hex in a `<style>` block with the token for its role. Borders take the `-border` / `border-strong` variant, backgrounds the `-soft` / surface variant, text the `-text` variant.

| Hex | Token |
|---|---|
| `#fff` `#ffffff` `#fcfdff` `#f9fafb` | `var(--chart-surface)` |
| `#f8fafc` `#f1f5f9` `#f6f8fa` `#f3f4f6` `#edeef0` `#eef6f6` `#e5edf5` | `var(--chart-surface-muted)` |
| `#e5e7eb` `#e2e8f0` `#dbe4f0` | `var(--chart-border)` |
| `#d1d5db` `#cbd5e1` | `var(--chart-border-strong)` |
| `#94a3b8` | `var(--chart-faint)` |
| `#0f172a` `#111827` `#1e293b` | `var(--chart-text)` |
| `#334155` `#475569` | `var(--chart-text-soft)` |
| `#64748b` `#6b7280` | `var(--chart-muted)` |
| `#1d4ed8` `#0369a1` | `var(--chart-info-text)` |
| `#2563eb` | `var(--chart-blue)` |
| `#eff6ff` `#e0f2fe` `#dbeafe` `#eef4ff` `#eef2ff` `#e0e7ff` | `var(--chart-info-soft)` |
| `#bfdbfe` `#93c5fd` `#c7d2fe` | `var(--chart-border-strong)` |
| `#b91c1c` `#dc2626` | `var(--chart-danger-text)` |
| `#ef4444` `#f87171` | `var(--chart-danger)` |
| `#fee2e2` `#fff1f2` | `var(--chart-danger-soft)` |
| `#fecaca` | `var(--chart-danger-border)` |
| `#92400e` `#c2410c` | `var(--chart-caution-text)` |
| `#fffbeb` `#fff7ed` `#fef3c7` | `var(--chart-caution-soft)` |
| `#fed7aa` `#fcd34d` `#fde68a` | `var(--chart-caution-border)` |
| `#166534` | `var(--chart-ok-text)` |
| `#dcfce7` `#ecfdf5` `#ecfdf3` `#f0fdfa` `#bbf7d0` | `var(--chart-ok-soft)` |
| `#16a34a` `#087b75` `#0f766e` (brand use) | `var(--chart-accent-strong)` |

A hex not in the table: pick the nearest role above and note it in the commit body. `rgba(...)` shadows may stay.

## Review Focus

1. **A settings colour other than green.** Every accent surface follows it, and Completed / Ready / ok chips stay green. Pinned by Task 1 `test_accent_reads_the_settings_colour` and the Task 10 purple check.
2. **Switching tabs.** A panel's teleported buttons leave with it: no duplicate New Procedure under Photos, and no orphaned Save. Pinned by the browser check in Tasks 3, 4 and 9.
3. **Read-only (submitted) encounter.** Teleported buttons keep their `:disabled` / `v-if` rules (New Procedure disabled, Upload hidden or disabled as today). Pinned by the browser check in Tasks 3, 4 and 9.
4. **Narrow width (1280).** The Procedures header holds a label and three buttons without overflow. Pinned by the Task 9 measurement.
5. **A component's own `button.primary` override.** Scoped overrides in Prescription, Assessment and Consent would beat the shared button style. Each owning task deletes them, and Task 10 greps that none remain.

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `do_derma/tests/test_chart_theme.py` | Modify | Accent, alias, hex-allowlist and teleport tests |
| `do_derma/public/js/chart/derma_chart.bundle.css` | Modify | Accent tokens, aliases, shared blocks; per-panel dead-rule deletion |
| `components/shell/SectionCard.vue` | Modify | Always-present `#chart-section-actions` target |
| `components/shell/SectionTabs.vue`, `ChartHero.vue` | Modify | Accent instead of ok-green / hex gradient |
| `components/photos/PhotosPanel.vue` | Modify | Teleport Upload; scope chips as pills |
| `components/PrescriptionPanel.vue` | Modify | Teleport Save; drop empty header; hex |
| `components/review/AiDocumentsCard.vue`, `DermaChart.vue` (review + drawings) | Modify | Pills, inner cards |
| `components/assessment/{AssessmentPanel,SoapNoteFields,StructuredAssessmentFields,PreviousVisitsPanel}.vue` | Modify | Hex, inner cards, status pills |
| `components/{ConsentPanel,AnesthesiaPanel}.vue` | Modify | Hex, button overrides removed |
| `components/consumables/ConsumablesEditor.vue` | Modify | Hex, removed chip as pill |
| `components/ProcedurePanel.vue` | Modify | Teleport three buttons; pills; hex |

All `components/...` paths are under `do_derma/public/js/chart/`.

---

### Task 1: Accent tokens, palette aliases, and the source tests

**Files:**
- Modify: `do_derma/public/js/chart/derma_chart.bundle.css` (`:root` block lines 1–31; the `--chart-*` token block)
- Test: `do_derma/tests/test_chart_theme.py`

**Interfaces:**
- Produces: `--chart-accent`, `--chart-accent-strong`, `--chart-accent-soft` on `.dental-chart-page.derma-chart-page`; every `--derma-*` declared there as `var(--chart-*)`; `HEX_ALLOWED` dict in the test (later tasks delete entries from it).

- [ ] **Step 1: Write the failing tests**

Append to `do_derma/tests/test_chart_theme.py` (tabs; reuse existing `CHART_CSS`, `get_token_block`, `CHART_FIRST_TOKEN`):

```python
CHART_DIR = CHART_CSS.parent
STYLE_BLOCK = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# Files still carrying hex colours in <style>; each panel task deletes its entry.
HEX_ALLOWED = {
	"components/AnesthesiaPanel.vue",
	"components/ConsentPanel.vue",
	"components/PrescriptionPanel.vue",
	"components/ProcedurePanel.vue",
	"components/assessment/AssessmentPanel.vue",
	"components/assessment/SoapNoteFields.vue",
	"components/assessment/StructuredAssessmentFields.vue",
	"components/consumables/ConsumablesEditor.vue",
	"components/shell/ChartHero.vue",
}


class TestChartAccent(TestCase):
	"""The chart's accent follows Do Health Settings; the old palette points at the new one."""

	def get_chart_tokens(self):
		return get_token_block(CHART_CSS.read_text(), CHART_FIRST_TOKEN)

	def test_accent_reads_the_settings_colour(self):
		tokens = self.get_chart_tokens()
		self.assertEqual(tokens["--chart-accent"].strip(), "var(--do-health-header-accent, #16a34a)")
		self.assertIn("var(--chart-accent)", tokens["--chart-accent-strong"])
		self.assertIn("var(--chart-accent)", tokens["--chart-accent-soft"])

	def test_old_palette_is_aliased(self):
		tokens = self.get_chart_tokens()
		old = {name: value for name, value in tokens.items() if name.startswith("--derma-")}
		self.assertEqual(len(old), 29)
		for name, value in old.items():
			self.assertRegex(value.strip(), r"^var\(--chart-[\w-]+\)$", name)
		root = CHART_CSS.read_text().split(":root {", 1)
		self.assertTrue(len(root) == 1 or "--derma-" not in root[1].split("}", 1)[0])


class TestChartComponentColours(TestCase):
	"""Component styles read tokens, not hex; the allowlist only shrinks."""

	def get_files_with_hex(self):
		found = set()
		for path in CHART_DIR.rglob("*.vue"):
			relative = path.relative_to(CHART_DIR).as_posix()
			if relative.startswith("annotation/"):
				continue
			styles = "".join(STYLE_BLOCK.findall(path.read_text()))
			if HEX_COLOUR.search(styles):
				found.add(relative)
		return found

	def test_no_new_hex_colours(self):
		self.assertEqual(self.get_files_with_hex() - HEX_ALLOWED, set())

	def test_allowlist_has_no_cleaned_files(self):
		self.assertEqual(HEX_ALLOWED - self.get_files_with_hex(), set())

	def test_teleports_target_the_section_card(self):
		self.assertIn('id="chart-section-actions"', (CHART_DIR / "components/shell/SectionCard.vue").read_text())
		for path in CHART_DIR.rglob("*.vue"):
			for tag in re.findall(r"<Teleport[^>]*>", path.read_text()):
				self.assertIn('to="#chart-section-actions"', tag, path.name)
				self.assertIn("defer", tag, path.name)
```

- [ ] **Step 2: Run and confirm the expected failures**

Run the theme tests command. Expected: `test_accent_reads_the_settings_colour` errors with `KeyError: '--chart-accent'`; `test_old_palette_is_aliased` fails (0 != 29); `test_teleports_target_the_section_card` fails (id missing). `test_no_new_hex_colours` and `test_allowlist_has_no_cleaned_files` pass, which proves the seed list is exact. If either fails, fix the seed list to the real set before going on.

- [ ] **Step 3: Implement the tokens and aliases**

In `derma_chart.bundle.css`:
1. Delete the whole `:root { ... }` block at the top (the 29 `--derma-*` declarations).
2. In the `/* Patient Overview tokens ... */` block, after `--chart-brand: #16a34a;`, add:

```css
  --chart-accent: var(--do-health-header-accent, #16a34a);
  --chart-accent-strong: color-mix(in srgb, var(--chart-accent) 82%, black);
  --chart-accent-soft: color-mix(in srgb, var(--chart-accent) 10%, white);

  --derma-white: var(--chart-surface);
  --derma-bg-faint: var(--chart-surface);
  --derma-bg-faint-alt: var(--chart-surface);
  --derma-bg-subtle: var(--chart-surface-muted);
  --derma-bg-muted: var(--chart-surface-muted);
  --derma-text-strong: var(--chart-text);
  --derma-text-strong-alt: var(--chart-text);
  --derma-text-deep: var(--chart-text);
  --derma-text-deepest: var(--chart-text);
  --derma-navy: var(--chart-text);
  --derma-text-secondary: var(--chart-text-soft);
  --derma-text-secondary-alt: var(--chart-text-soft);
  --derma-text-muted: var(--chart-muted);
  --derma-border-subtle: var(--chart-border);
  --derma-border-faint: var(--chart-border);
  --derma-border: var(--chart-border-strong);
  --derma-border-muted: var(--chart-border-strong);
  --derma-border-light: var(--chart-border-strong);
  --derma-brand: var(--chart-accent-strong);
  --derma-brand-light: var(--chart-accent-soft);
  --derma-success-bg: var(--chart-ok-soft);
  --derma-success-bg-alt: var(--chart-ok-soft);
  --derma-warning-bg-subtle: var(--chart-caution-soft);
  --derma-warning-bg: var(--chart-caution-soft);
  --derma-danger: var(--chart-danger-text);
  --derma-danger-bg: var(--chart-danger-soft);
  --derma-info: var(--chart-blue);
  --derma-info-bg-subtle: var(--chart-info-soft);
  --derma-info-bg: var(--chart-info-soft);
```

Update that block's comment to: `/* Patient Overview tokens (do_health --ov-*, light), the settings accent, and the old palette as aliases. */`

- [ ] **Step 4: Run the theme tests**

Expected: everything passes except `test_teleports_target_the_section_card` (Task 2 adds the id).

- [ ] **Step 5: Commit**

```bash
git add do_derma/public/js/chart/derma_chart.bundle.css do_derma/tests/test_chart_theme.py
git commit -m "feat(chart): accent from Do Health Settings; old palette aliased

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Shared building blocks and the card actions target

**Files:**
- Modify: `derma_chart.bundle.css` (new block after the token block; the button rules at lines ~1624–1656)
- Modify: `components/shell/SectionCard.vue`, `components/shell/SectionTabs.vue`, `components/shell/ChartHero.vue`
- Test: `test_chart_theme.py` (existing tests)

**Interfaces:**
- Produces: `.chart-pill` with `data-tone="neutral|accent|ok|caution|danger"`; `button.chart-pill[aria-pressed="true"]` = selected; `.chart-label`; `.chart-inner-card`; `#chart-section-actions` (a flex row in the card header that wraps).

- [ ] **Step 1: Give `SectionCard` a permanent target**

Replace its header actions markup with:

```vue
      <div id="chart-section-actions" class="chart-section-card-actions">
        <slot name="actions" />
      </div>
```

Change `.chart-section-card-header` to `flex-wrap: wrap;` with `row-gap: 8px`, and `.chart-section-card-actions` to add `flex-wrap: wrap; justify-content: flex-end; margin-left: auto;`. Run the theme tests: all pass.

- [ ] **Step 2: Add the shared block**

Directly after the closing `}` of the `--chart-*` token block, add:

```css
/* Shared chart building blocks, mirroring the Patient Overview. */
.dental-chart-page .chart-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 9px;
  border: 1px solid var(--chart-border-strong);
  border-radius: 999px;
  background: var(--chart-surface-muted);
  color: var(--chart-text-soft);
  font-size: 11.5px;
  font-weight: 600;
  line-height: 18px;
  white-space: nowrap;
}

.dental-chart-page button.chart-pill {
  cursor: pointer;
}

.dental-chart-page .chart-pill[data-tone="accent"],
.dental-chart-page button.chart-pill[aria-pressed="true"] {
  background: var(--chart-accent-soft);
  border-color: color-mix(in srgb, var(--chart-accent) 35%, transparent);
  color: var(--chart-accent-strong);
}

.dental-chart-page .chart-pill[data-tone="ok"] {
  background: var(--chart-ok-soft);
  border-color: transparent;
  color: var(--chart-ok-text);
}

.dental-chart-page .chart-pill[data-tone="caution"] {
  background: var(--chart-caution-soft);
  border-color: var(--chart-caution-border);
  color: var(--chart-caution-text);
}

.dental-chart-page .chart-pill[data-tone="danger"] {
  background: var(--chart-danger-soft);
  border-color: var(--chart-danger-border);
  color: var(--chart-danger-text);
}

.dental-chart-page .chart-label {
  margin: 0;
  color: var(--chart-muted);
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.dental-chart-page .chart-inner-card {
  border: 1px solid var(--chart-border);
  border-radius: 12px;
  background: var(--chart-surface-muted);
  box-shadow: none;
}

.dental-chart-page :where(input:not([type="checkbox"], [type="radio"], [type="range"], [type="color"]), select, textarea) {
  border-color: var(--chart-border-strong);
  border-radius: 8px;
}

.dental-chart-page :where(input, select, textarea):focus-visible {
  outline: none;
  box-shadow: var(--chart-focus);
}
```

- [ ] **Step 3: Rewrite the button rules in place**

In the group rule beginning `.dental-chart-page .primary-toggle button,` (line ~1624), replace its body with:

```css
  border: 1px solid var(--chart-border-strong);
  border-radius: 8px;
  background: var(--chart-surface);
  color: var(--chart-text);
  padding: 7px 12px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
```

Replace the `.dental-chart-page .primary, .dental-chart-page .primary-toggle button.active` body with:

```css
  border-color: var(--chart-accent-strong);
  background: var(--chart-accent-strong);
  color: white;
```

Replace the `.dental-chart-page .ghost.small` rule with:

```css
.dental-chart-page .ghost.small,
.dental-chart-page .primary.small {
  padding: 5px 10px;
  font-size: 12px;
}

.dental-chart-page .ghost:hover:not(:disabled) {
  background: var(--chart-surface-muted);
}

.dental-chart-page .primary:hover:not(:disabled) {
  background: color-mix(in srgb, var(--chart-accent-strong) 88%, black);
}

.dental-chart-page :where(.primary, .ghost):focus-visible {
  outline: none;
  box-shadow: var(--chart-focus);
}
```

- [ ] **Step 4: Point the shell at the accent**

- `SectionTabs.vue`: in `.chart-tabs-button[data-active="true"]` use `background: var(--chart-accent-soft); color: var(--chart-accent-strong);`. In `.chart-tabs-tick` use `color: var(--chart-accent-strong);`.
- `ChartHero.vue`: in `.chart-hero-avatar` replace the `linear-gradient(...)` line with `background: var(--chart-accent-soft);` and `color: var(--chart-ok-text);` with `color: var(--chart-accent-strong);`. Then delete `"components/shell/ChartHero.vue"` from `HEX_ALLOWED`.

- [ ] **Step 5: Test, build, look**

Run the theme tests. Expected: all pass. Build, restart the server, open the draft chart at 1600. Expected: active tab, tick, avatar and Complete Encounter all in the green accent; the Procedures toolbar buttons are rounded 8px; no layout shift. Screenshot it.

- [ ] **Step 6: Commit**

```bash
git add -A do_derma/public/js/chart do_derma/tests/test_chart_theme.py
git commit -m "feat(chart): shared buttons, pills, labels and inner cards; card actions target

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Photos

**Files:**
- Modify: `components/photos/PhotosPanel.vue`; `derma_chart.bundle.css` (`.photo-scope-chip` rules near line 4765)

**Interfaces:**
- Consumes: `#chart-section-actions` and `.chart-pill` (Task 2).

- [ ] **Step 1: Teleport Upload Photo**

Wrap the existing Upload button (`data-test="photos-upload"`), unchanged inside, in:

```vue
      <Teleport defer to="#chart-section-actions">
        <!-- existing <button ... data-test="photos-upload"> ... </button> -->
      </Teleport>
```

Keep it inside the `<header>` element where it is now.

- [ ] **Step 2: Scope chips become pills**

On the scope button replace `class="photo-scope-chip"` and `:class="{ active: scope.key === activeScope }"` with `class="chart-pill"` and `:aria-pressed="scope.key === activeScope ? 'true' : 'false'"`. Change the count `<small>` to `<small class="chart-label">`.

- [ ] **Step 3: Delete dead CSS**

```bash
cd do_derma/public/js/chart
grep -rn "photo-scope-chip" --include=*.vue --include=*.js . | grep -v node_modules   # expect no output
```

Delete every rule in `derma_chart.bundle.css` whose selectors all contain `.photo-scope-chip`. Check brace balance:
`python3 -c "import re;s=re.sub(r'/\*.*?\*/','',open('derma_chart.bundle.css').read(),flags=re.S);print(s.count('{')-s.count('}'))"` → `0`.

- [ ] **Step 4: Run the theme tests**

Expected: all pass, including `test_teleports_target_the_section_card`.

- [ ] **Step 5: Build and browser-check**

At 1280 / 1600 / 1920 on the draft encounter, Photos tab:
- Upload Photo is in the card header, right of PHOTOS, filled accent.
- Switch to Procedures, then back. Upload appears exactly once, and never under another tab.
- This visit / All photos look like pills; the selected one is tinted.
- Click Upload Photo: the upload dialog opens (cancel it).
- Submitted encounter: Upload keeps today's disabled or hidden state.

- [ ] **Step 6: Commit**

```bash
git add -A do_derma/public/js/chart
git commit -m "style(photos): upload in the card header; scope pills

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Prescription

**Files:**
- Modify: `components/PrescriptionPanel.vue`
- Test: `test_chart_theme.py` (`HEX_ALLOWED`)

- [ ] **Step 1: Red**

Delete `"components/PrescriptionPanel.vue"` from `HEX_ALLOWED`. Run the theme tests. Expected: `test_no_new_hex_colours` fails naming `components/PrescriptionPanel.vue`.

- [ ] **Step 2: Teleport Save and drop the empty header**

Replace the `<header class="panel-header"> <div class="actions"> … </div> </header>` block with the same Save button (unchanged attributes) wrapped in `<Teleport defer to="#chart-section-actions"> … </Teleport>`, and no header around it. Delete the scoped rules for `.panel-header` and `.actions` if no other markup in the file uses those classes (grep the template first).

- [ ] **Step 3: Remove the scoped button overrides and the hex**

Delete the scoped `button.ghost { … }` and `button.primary { … }` rules (lines ~357–370) so the shared buttons apply. Replace every remaining hex in `<style>` using the Hex map. Change `class="status-note"` paragraphs to `class="status-note chart-pill" data-tone="caution"` only if the text is a warning ("Already ordered…" is). Leave plain notes unchanged.

- [ ] **Step 4: Green**

Run the theme tests. Expected: all pass.

- [ ] **Step 5: Build and browser-check**

Prescription tab at 1280 / 1600:
- Save in the card header, filled accent. Not visible on other tabs.
- Add a row on the draft encounter (medication + period), Save, reload: the row persists. Delete it, Save.
- On the submitted encounter, Save is disabled as today.

- [ ] **Step 6: Commit**

```bash
git add -A do_derma/public/js/chart do_derma/tests/test_chart_theme.py
git commit -m "style(prescription): save in the card header; tokens instead of hex

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Review

**Files:**
- Modify: `components/review/AiDocumentsCard.vue`; `DermaChart.vue` (review template, `class="derma-readiness-summary"`, `class="derma-timeline-workspace"`, follow-up cards); `derma_chart.bundle.css` (`.ai-doc-status` rules near line 5205)

- [ ] **Step 1: Status as a pill**

In `AiDocumentsCard.vue` change `<span class="ai-doc-status">{{ doc.status }}</span>` to:

```vue
<span class="chart-pill" :data-tone="doc.status === 'Issued' ? 'ok' : 'neutral'">{{ doc.status }}</span>
```

Delete the `.ai-doc-status` rules from the bundle CSS after a zero-users grep.

- [ ] **Step 2: Inner cards and labels**

In `DermaChart.vue`'s review template, add `chart-inner-card` to the class list of `section.derma-readiness-summary`, `section.derma-timeline-workspace`, and the AI documents card root. Give each section header's `<strong>` title the `chart-label` class. In the bundle CSS, delete those sections' own `border`, `background`, `border-radius` and `box-shadow` declarations (keep layout and padding) so the inner card style shows. Leave `.readiness-source`, the blocker list and the follow-up cards' layout alone.

- [ ] **Step 3: Test, build, browser-check**

Theme tests pass. Review tab at 1600: readiness, timeline and AI documents read as flat grey inner cards with uppercase labels; nothing overflows; "Clear Overlay" still works.

- [ ] **Step 4: Commit**

```bash
git add -A do_derma/public/js/chart
git commit -m "style(review): inner cards, labels and status pills

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Assessment

**Files:**
- Modify: `components/assessment/AssessmentPanel.vue`, `SoapNoteFields.vue`, `StructuredAssessmentFields.vue`, `PreviousVisitsPanel.vue`; `DermaChart.vue` (`section.chart-annotation-history`)
- Test: `test_chart_theme.py`

- [ ] **Step 1: Red**

Delete the three assessment entries from `HEX_ALLOWED`. Run the theme tests. Expected: `test_no_new_hex_colours` fails naming those three files.

- [ ] **Step 2: Replace hex, drop the button override**

Replace every hex in the three files' `<style>` blocks with the Hex map. Delete `button.primary { … }` in `AssessmentPanel.vue` (line ~294). Change `<span class="footer-status">` to `<span class="footer-status chart-pill">`, and delete the `.footer-status` declarations that set colour, background or border.

- [ ] **Step 3: Inner cards**

Add `chart-inner-card` to `section.chart-annotation-history` in `DermaChart.vue` and to the `PreviousVisitsPanel.vue` root section. Give their header `<strong>` titles the `chart-label` class. In the bundle CSS, remove `border`, `background`, `border-radius` and `box-shadow` from `.chart-annotation-history` and `.previous-visits` (or the class the root uses; check the template) rules only.

- [ ] **Step 4: Green, build, browser-check**

Theme tests pass. Assessment tab at 1280 / 1600:
- Dictate, Edit and Annotate Consultation are filled accent.
- Drawings and Previous Visits are flat grey inner cards.
- Click Edit on the draft encounter, type in a field, cancel without saving: nothing persists.
- The format switch still toggles.

- [ ] **Step 5: Commit**

```bash
git add -A do_derma/public/js/chart do_derma/tests/test_chart_theme.py
git commit -m "style(assessment): tokens, inner cards and labels

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Consent dialog and anaesthesia

**Files:**
- Modify: `components/ConsentPanel.vue`, `components/AnesthesiaPanel.vue`
- Test: `test_chart_theme.py`

- [ ] **Step 1: Red**

Delete both entries from `HEX_ALLOWED`; run the theme tests; expect a failure naming both files.

- [ ] **Step 2: Replace hex and the overrides**

Replace every hex in both `<style>` blocks per the Hex map. Delete `ConsentPanel.vue`'s scoped `button.ghost { … }` and `button.primary { … }` (lines ~713–730). The dialog keeps its own footer buttons (Create, Cancel, Print). They are not teleported, because the dialog is an overlay, not the section card.

- [ ] **Step 3: Green, build, browser-check**

Theme tests pass. On the draft encounter, Procedures → New Consent:
- The dialog shows Create filled accent and Cancel outlined.
- Draw a signature, Create: a consent appears on the procedure. Delete it afterwards through the existing consent list (or `bench console` with `frappe.delete_doc`, noting its name first).
- Anaesthesia rows, if the panel shows on this encounter, read in tokens.

- [ ] **Step 4: Commit**

```bash
git add -A do_derma/public/js/chart do_derma/tests/test_chart_theme.py
git commit -m "style(consent): tokens; shared buttons in the consent dialog

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Materials

**Files:**
- Modify: `components/consumables/ConsumablesEditor.vue`
- Test: `test_chart_theme.py`

- [ ] **Step 1: Red**

Delete its `HEX_ALLOWED` entry; run; expect a failure naming it.

- [ ] **Step 2: Replace hex; removed chips as pills**

Replace every hex per the Hex map. Change `class="removed-chip"` to `class="removed-chip chart-pill" data-tone="neutral"` and delete the `.removed-chip` colour, background, border and radius declarations (keep any layout). The amber *Changed* flag reads `--chart-caution-*`; per-line errors read `--chart-danger-text`.

- [ ] **Step 3: Green, build, browser-check**

Theme tests pass. Procedures → a draft procedure → Materials (0): open the editor, add a line, remove it (the removed chip shows with Restore), Restore, cancel without saving.

- [ ] **Step 4: Commit**

```bash
git add -A do_derma/public/js/chart do_derma/tests/test_chart_theme.py
git commit -m "style(materials): tokens; removed lines as pills

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Procedures

**Files:**
- Modify: `components/ProcedurePanel.vue`
- Test: `test_chart_theme.py`

- [ ] **Step 1: Teleport the three section buttons**

In `.panel-actions`, move Copy marks, New Consent and New Procedure into one teleport, in this order, keeping every attribute except the classes noted:

```vue
        <Teleport defer to="#chart-section-actions">
          <button type="button" class="ghost small" data-test="procedure-copy-marks" ...>…</button>
          <button type="button" class="ghost small" data-test="procedure-new-consent" ...>…</button>
          <button type="button" class="primary small" data-test="procedure-new" ...>…</button>
        </Teleport>
```

New Consent changes from `primary small consent-action` to `ghost small`. Delete the scoped `.panel-actions .primary.consent-action` and `.panel-actions .ghost` rules. The Load selector and the read-only / anaesthesia badges stay in `.panel-actions`. The two badges become `class="chart-pill" data-tone="neutral"` and `data-tone="caution"` respectively.

- [ ] **Step 2: Pills**

- Status filter buttons (`class="pill"` with `:class="{ active: … }"`) become `class="chart-pill"` with `:aria-pressed="activeStatus === pill.key ? 'true' : 'false'"`.
- Row status chips (`class="status-chip"` with `statusClass(row.status)`) become `class="chart-pill"` with `:data-tone="statusTone(row.status)"`. Add next to `statusClass`:

```js
const STATUS_TONES = { Draft: "neutral", "In Progress": "caution", Completed: "ok", Cancelled: "danger" }

function statusTone(status) {
  return STATUS_TONES[status] || "neutral"
}
```

  Delete `statusClass` if it has no other caller (grep).
- `detail-chip` spans and buttons keep their class and gain `chart-pill`; `no-charge-label` and `insurance-locked-label` get `data-tone="caution"`, `override-label` gets `data-tone="accent"`. Delete the `.detail-chip` colour, background, border and radius declarations; keep sizing and layout.

- [ ] **Step 3: Red, then replace the hex**

Delete `"components/ProcedurePanel.vue"` from `HEX_ALLOWED`; run the theme tests; expect a failure naming it. Replace all ~188 hex values in its `<style>` per the Hex map, working top to bottom. Also replace its `var(--derma-*)` uses with the `--chart-*` token they alias (see Task 1). Run until `test_no_new_hex_colours` passes.

- [ ] **Step 4: Build and browser-check**

At 1280 / 1600 / 1920 on the draft encounter:
- PROCEDURES header holds Copy marks, New Consent (outlined) and New Procedure (filled). At 1280 measure that every button's right edge ≤ the card's right edge and that the page has no horizontal scroll.
- Switch to Photos: none of the three appear there.
- Status filter pills tint when selected; row status pills show tones (Draft neutral, Completed green).
- New Procedure: add one (any template), confirm the row appears, then delete it with the row's delete action.
- Submitted encounter: New Procedure and New Consent disabled; the "Read only" pill shows.

- [ ] **Step 5: Commit**

```bash
git add -A do_derma/public/js/chart do_derma/tests/test_chart_theme.py
git commit -m "style(procedures): actions in the card header; pills; tokens instead of hex

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Purple accent check, sweep, suite

- [ ] **Step 1: Confirm the done conditions**

```bash
cd do_derma/public/js/chart
grep -rnE "^\s*button\.(primary|ghost)\s*\{" --include=*.vue components    # expect no output
wc -l < derma_chart.bundle.css                                           # expect < 5270
```

Run the theme tests: `HEX_ALLOWED` is now empty, so `test_allowlist_has_no_cleaned_files` and `test_no_new_hex_colours` both pass. Replace the `HEX_ALLOWED` set literal with `HEX_ALLOWED: set[str] = set()` and its comment with `# Component styles read --chart-* tokens; hex is not allowed.`

- [ ] **Step 2: Purple accent**

```bash
cd /Users/hameed/Developer/bench-v16
echo 'frappe.db.set_single_value("Do Health Settings", "sidebar_header_color", "#7c3aed"); frappe.db.commit()' | bench --site dermaone.localhost console
bench --site dermaone.localhost clear-cache
```

Reload the chart. Expected: sidebar header, active tab, avatar, filled buttons and selected pills are purple; Completed pill, "Ready to complete" and ok chips stay green. Screenshot. Then restore:

```bash
echo 'frappe.db.set_single_value("Do Health Settings", "sidebar_header_color", None); frappe.db.commit()' | bench --site dermaone.localhost console
bench --site dermaone.localhost clear-cache
```

Confirm the chart is green again.

- [ ] **Step 3: Full suite against main**

```bash
RESULTS=$(mktemp -d)
bench --site dermaone.localhost run-tests --app do_derma 2>&1 | grep -E "^\s*(FAIL|ERROR)\s" | sed -E 's/^\s*(FAIL|ERROR)\s+//' | sort > "$RESULTS/branch.txt"
```

Compare against the 5 known `main` failures (`test_documents` ×3 sign-off/letter tests, `test_readiness.test_an_inventory_row_with_no_product_name_still_names_its_item`, `test_ai_ops.test_prompts_name_the_company_not_a_hardcoded_clinic`). Expected: no other names.

- [ ] **Step 4: Commit**

```bash
git add do_derma/tests/test_chart_theme.py
git commit -m "test(chart): component styles carry no hex colours

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
