# Derma Chart Overview Skin (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the derma chart page do_health's Patient Overview look: a hero card, a clinical strip, stateful tabs and a section card on a grey canvas.

**Architecture:** The backend adds one field, `clinical_profile`, to the existing `get_patient_derma_chart` payload by calling do_health's `get_clinical_profile`. The frontend adds four small Vue components under `components/shell/` (`ChartHero`, `ClinicalStrip`, `SectionTabs`, `SectionCard`). They replace `DermaEncounterHeader.vue` and the inline tab bar in `DermaChart.vue`, and style themselves from a light-only `--chart-*` token block that a test pins to do_health's `--ov-*` values.

**Tech Stack:** Frappe v16, Python 3 (`IntegrationTestCase`, `unittest.TestCase`), Vue 3 SFCs (`<script setup>`, `<style scoped>`) built by `bench build --app do_derma`.

**Spec:** `.planning/specs/2026-10-01-derma-chart-overview-skin.md`

## Global Constraints

- Branch `feat/derma-chart-overview-skin`. Work on `main`'s chart sources: `do_derma/public/js/chart/**` (no `frontend/` Vite tree on this branch).
- Five tabs: Assessment, Procedures, Photos, Prescription, Review. No Consent tab.
- No right column, no patient picker, no body map on the chart page.
- Light-only: no `[data-theme="dark"]` rule for `--chart-*` tokens in phase 1.
- Never edit `do_health` files in this plan. "Update history" feature-detects `window.do_health.openMedicalHistoryPanel`.
- In `derma_chart.bundle.css` the token block is the only addition. Delete only selectors with zero users. Do not fix the early-closing `@media` bug.
- Repo rules (`CLAUDE.md`): no file-top comments, terse comments, no abbreviations, cyclomatic complexity ≤ 8, booleans named `is_`/`has_` (JS: `is`/`has`).
- Python files use tabs. `tests/test_api.py` is space-indented: match that file as it is.
- Commits: `<type>: <description>` body, ending with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Test commands (bench quirks)

- Run from `/Users/hameed/Developer/bench-v16`.
- `--test` must be the **bare method name**. A class name runs zero tests and exits 0. A run that prints only the header ran nothing.
- Module run: `bench --site dermaone.localhost run-tests --module do_derma.tests.test_api 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"`
- Lint changed Python only: `pipx run ruff check <files>`.
- After any `bench build --app do_derma`, restart the web server, or every `/assets/do_derma/...` URL 404s.
- The suite has a standing red baseline on `main`. Judge by diffing the failing names against `main`, never by "all green".

## Review Focus

1. **A patient with no clinical data at all.** The strip must show "Not recorded" for allergies and quiet empty states for history and medications, not an empty card or `undefined`. Pinned by the Task 1 healthy-profile test (`allergy_status == "not_recorded"`) and the Task 4 browser check.
2. **do_health raises inside `get_clinical_profile`.** The chart still loads, `clinical_profile` is `None`, "clinical profile" is in `context_errors`, and no exception text leaks. Pinned by Task 1 tests.
3. **Readiness with warnings but no blockers.** The hero must say "{n} warning(s)" in caution tone and jump to Review, not Procedures. Pinned by the Task 7 browser check.
4. **A previous (non-latest) encounter.** The banner shows and "Open latest visit" still works, and Complete/Reopen keep their existing permission states. Pinned by the Task 7 browser check.
5. **Desk in dark mode.** The new shell stays light like the panels. Pinned by Task 2 (`test_chart_tokens_are_not_overridden_in_dark_mode`) and the Task 8 browser check.

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `do_derma/api.py` | Modify | Add `clinical_profile` to `get_patient_derma_chart` |
| `do_derma/tests/test_api.py` | Modify | Payload tests for `clinical_profile` |
| `do_derma/public/js/chart/derma_chart.bundle.css` | Modify | `--chart-*` token block, canvas background, dead-rule deletion |
| `do_derma/tests/test_chart_theme.py` | Modify | Token parity with do_health; tokens stay light |
| `do_derma/public/js/chart/components/shell/SectionCard.vue` | Create | Card frame: uppercase label, actions slot, body |
| `do_derma/public/js/chart/components/shell/SectionTabs.vue` | Create | Tab row with blocker dots and counts |
| `do_derma/public/js/chart/components/shell/ClinicalStrip.vue` | Create | Allergies / history / medications strip |
| `do_derma/public/js/chart/components/shell/ChartHero.vue` | Create | Previous-visit banner, identity, This-visit box, readiness line, Complete/Reopen, alerts |
| `do_derma/public/js/chart/DermaChart.vue` | Modify | Wire the shell in; drop tab hints; move the mode toggle |
| `do_derma/public/js/chart/components/DermaEncounterHeader.vue` | Delete | Replaced by `ChartHero.vue` |

---

### Task 1: `clinical_profile` in the chart payload

**Files:**
- Modify: `do_derma/api.py` (imports near line 9; `get_patient_derma_chart`, the `return {` dict near line 2510)
- Test: `do_derma/tests/test_api.py` (class `TestChartContextErrors`, near line 585)

**Interfaces:**
- Consumes: `do_health.api.clinical_profile.get_clinical_profile(patient_doc) -> dict` with keys `allergy_status` (`"recorded" | "none_known" | "not_recorded"`), `allergies` (`[{allergen, type, type_label, severity}]`), `conditions` (`[{name, note, is_critical}]`), `medications` (`[{name, reason, since, risk_class}]`), `surgeries` (`[{name, date}]`), `habits` (`[{habit, note}]`), `reviewed_on` (`{date, days_ago} | None`).
- Produces: the chart payload key `clinical_profile` (the dict above, or `None`) and the `context_errors` label `"clinical profile"`.

- [ ] **Step 1: Write the failing tests**

Add to `TestChartContextErrors` in `do_derma/tests/test_api.py`, matching that file's 4-space indentation:

```python
    def test_chart_carries_the_clinical_profile(self):
        patient = self._make_patient()

        chart = api.get_patient_derma_chart(patient_id=patient)

        self.assertEqual(chart["clinical_profile"]["allergy_status"], "not_recorded")
        self.assertEqual(chart["clinical_profile"]["medications"], [])

    def test_a_broken_clinical_profile_degrades_to_none(self):
        patient = self._make_patient()
        secret = "SELECT custom_allergies_table FROM tabPatient"

        with patch.object(api, "get_clinical_profile", side_effect=ValueError(secret)):
            chart = api.get_patient_derma_chart(patient_id=patient)

        self.assertIsNone(chart["clinical_profile"])
        self.assertEqual(chart["context_errors"], ["clinical profile"])
        self.assertNotIn(secret, json.dumps(chart, default=str))
```

- [ ] **Step 2: Run the tests and confirm they fail**

```bash
cd /Users/hameed/Developer/bench-v16
bench --site dermaone.localhost run-tests --module do_derma.tests.test_api --test test_chart_carries_the_clinical_profile
bench --site dermaone.localhost run-tests --module do_derma.tests.test_api --test test_a_broken_clinical_profile_degrades_to_none
```

Expected: the first errors with `KeyError: 'clinical_profile'`. The second errors with `AttributeError: ... does not have the attribute 'get_clinical_profile'`.

- [ ] **Step 3: Implement**

In `do_derma/api.py`, next to the existing do_health import on line 9:

```python
from do_health.api.appointment_methods import create_encounter_for_appointment
from do_health.api.clinical_profile import get_clinical_profile
```

In `get_patient_derma_chart`, add this entry to the returned dict, directly after the `"categories": section("categories", [], _get_categories),` line:

```python
		"clinical_profile": section(
			"clinical profile",
			None,
			lambda: get_clinical_profile(frappe.get_doc("Patient", patient)) if patient else None,
		),
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run the two commands from Step 2. Expected: each prints `Ran 1 test` and `OK`. Then run the whole class's neighbours to confirm the healthy-chart test still reports no degraded sections:

```bash
bench --site dermaone.localhost run-tests --module do_derma.tests.test_api --test test_healthy_chart_reports_no_degraded_sections
```

Expected: `OK`.

- [ ] **Step 5: Lint and commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
pipx run ruff check do_derma/api.py   # only findings already present on main (RUF005) are acceptable
git add do_derma/api.py do_derma/tests/test_api.py
git commit -m "feat(chart): carry the patient's clinical profile in the chart payload

Reuses do_health's get_clinical_profile so the chart's clinical strip reads
the same allergies, history and medications as the Patient Overview. A
failure degrades to None under the 'clinical profile' label.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `--chart-*` tokens pinned to do_health

**Files:**
- Modify: `do_derma/public/js/chart/derma_chart.bundle.css` (insert after the `:root { ... }` block that ends near line 31; change `background` in the `.dental-chart-page.derma-chart-page` rule near line 225)
- Test: `do_derma/tests/test_chart_theme.py`

**Interfaces:**
- Produces: CSS custom properties on `.dental-chart-page.derma-chart-page`. Tasks 3–6 use these: `--chart-bg`, `--chart-surface`, `--chart-surface-muted`, `--chart-border`, `--chart-border-strong`, `--chart-text`, `--chart-text-soft`, `--chart-muted`, `--chart-faint`, `--chart-shadow`, `--chart-radius`, `--chart-focus`, `--chart-danger`, `--chart-danger-soft`, `--chart-danger-border`, `--chart-danger-text`, `--chart-caution`, `--chart-caution-soft`, `--chart-caution-border`, `--chart-caution-text`, `--chart-ok`, `--chart-ok-soft`, `--chart-ok-text`, `--chart-info-soft`, `--chart-info-text`, `--chart-teal`, `--chart-violet`, `--chart-blue`, `--chart-rose`, `--chart-amber`, `--chart-brand`.

- [ ] **Step 1: Write the failing tests**

Append to `do_derma/tests/test_chart_theme.py` (tabs). Add `import frappe` under the existing imports:

```python
OVERVIEW_FIRST_TOKEN = "--ov-bg:"
CHART_FIRST_TOKEN = "--chart-bg:"


def get_token_block(css: str, first_token: str) -> dict[str, str]:
	"""Variables of the rule block holding the first occurrence of `first_token`."""
	start = css.index(first_token)
	block = css[css.rindex("{", 0, start) : css.index("}", start)]
	return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block))


class TestChartTokens(TestCase):
	"""The chart wears the Patient Overview's light tokens; drift from do_health fails here."""

	def test_every_overview_token_has_a_matching_chart_token(self):
		overview_css = Path(frappe.get_app_path("do_health", "public", "css", "health_sidebar.css")).read_text()
		overview = get_token_block(overview_css, OVERVIEW_FIRST_TOKEN)
		chart = get_token_block(CHART_CSS.read_text(), CHART_FIRST_TOKEN)
		for name, value in overview.items():
			chart_name = name.replace("--ov-", "--chart-", 1)
			self.assertIn(chart_name, chart)
			self.assertEqual(chart[chart_name].strip(), value.strip(), chart_name)

	def test_chart_tokens_are_not_overridden_in_dark_mode(self):
		css = CHART_CSS.read_text()
		self.assertNotIn("--chart-", css.split(DARK_SCOPE, 1)[1].split("}", 1)[0])
		self.assertNotRegex(css, r'\[data-theme="dark"\][^{]*\{[^}]*--chart-')
```

- [ ] **Step 2: Run the tests and confirm they fail**

```bash
cd /Users/hameed/Developer/bench-v16
bench --site dermaone.localhost run-tests --module do_derma.tests.test_chart_theme --test test_every_overview_token_has_a_matching_chart_token
```

Expected: `ERROR` with `ValueError: substring not found` (no `--chart-bg:` yet).

- [ ] **Step 3: Implement**

In `derma_chart.bundle.css`, insert directly after the closing `}` of the top `:root { ... }` block and before the `/* The chart is light-only ... */` comment:

```css
/* Patient Overview tokens (do_health --ov-*, light). test_chart_theme pins the values. */
.dental-chart-page.derma-chart-page {
  --chart-bg: #f3f5f8;
  --chart-surface: #ffffff;
  --chart-surface-muted: #f6f8fa;
  --chart-border: rgba(15, 23, 42, 0.08);
  --chart-border-strong: rgba(15, 23, 42, 0.15);
  --chart-text: #0f172a;
  --chart-text-soft: #334155;
  --chart-muted: #64748b;
  --chart-faint: #a3afbf;
  --chart-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 10px 28px -18px rgba(15, 23, 42, 0.25);
  --chart-radius: 14px;
  --chart-focus: 0 0 0 3px rgba(37, 99, 235, 0.28);
  --chart-danger: #e11d48;
  --chart-danger-soft: #fff1f3;
  --chart-danger-border: rgba(225, 29, 72, 0.22);
  --chart-danger-text: #be123c;
  --chart-caution: #d97706;
  --chart-caution-soft: #fffaeb;
  --chart-caution-border: rgba(217, 119, 6, 0.26);
  --chart-caution-text: #b45309;
  --chart-ok: #059669;
  --chart-ok-soft: #ecfdf5;
  --chart-ok-text: #047857;
  --chart-info-soft: #eff5ff;
  --chart-info-text: #1d4ed8;
  --chart-teal: #0d9488;
  --chart-violet: #7c3aed;
  --chart-blue: #2563eb;
  --chart-rose: #e11d48;
  --chart-amber: #d97706;
  --chart-brand: #16a34a;
}
```

In the `.dental-chart-page.derma-chart-page` rule near line 225 (the one with `min-height: calc(100vh - 96px)`), change `background: #f3f7f9;` to `background: var(--chart-bg);`.

- [ ] **Step 4: Run the module and confirm it passes**

```bash
bench --site dermaone.localhost run-tests --module do_derma.tests.test_chart_theme 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"
```

Expected: `Ran 3 tests` / `OK`.

- [ ] **Step 5: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
git add do_derma/public/js/chart/derma_chart.bundle.css do_derma/tests/test_chart_theme.py
git commit -m "feat(chart): Patient Overview tokens on the chart page

A light-only --chart-* block mirrors do_health's --ov-* values; a test
fails if either side drifts or a dark override appears.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `SectionCard` and `SectionTabs`

**Files:**
- Create: `do_derma/public/js/chart/components/shell/SectionCard.vue`
- Create: `do_derma/public/js/chart/components/shell/SectionTabs.vue`

**Interfaces:**
- Consumes: `--chart-*` tokens (Task 2).
- Produces:
  - `SectionCard`: props `label: String`. Slots `actions`, `default`. Root `data-test="section-card"`.
  - `SectionTabs`: props `tabs: Array<{key, label}>`, `active: String`, `counts: Object` (keyed by tab key, numbers), `filled: Array<String>` (tab keys that show ✓), `blocked: Array<String>` (tab keys that show the red dot). Emits `select(key)`. Buttons `data-test="section-tab-<key>"` with `data-active`, dot `data-test="tab-blocker-<key>"`, count `data-test="<key>-tab-count"`, tick `data-test="assessment-tick"`.

These components have no unit-test harness in this repo. They are verified in the browser once wired in (Task 7).

- [ ] **Step 1: Create `SectionCard.vue`**

```vue
<template>
  <section class="chart-section-card" data-test="section-card">
    <header class="chart-section-card-header">
      <h2>{{ label }}</h2>
      <div v-if="$slots.actions" class="chart-section-card-actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="chart-section-card-body">
      <slot />
    </div>
  </section>
</template>

<script setup>
defineProps({
  label: { type: String, default: "" },
})
</script>

<style scoped>
.chart-section-card {
  background: var(--chart-surface);
  border: 1px solid var(--chart-border);
  border-radius: var(--chart-radius);
  box-shadow: var(--chart-shadow);
  min-width: 0;
}

.chart-section-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px 0;
}

.chart-section-card-header h2 {
  margin: 0;
  color: var(--chart-muted);
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.chart-section-card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chart-section-card-body {
  padding: 12px 18px 18px;
  min-width: 0;
}
</style>
```

- [ ] **Step 2: Create `SectionTabs.vue`**

```vue
<template>
  <nav class="chart-tabs" :aria-label="__('Derma encounter sections')" data-test="derma-section-bar">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      type="button"
      class="chart-tabs-button"
      :data-test="`section-tab-${tab.key}`"
      :data-active="tab.key === active ? 'true' : 'false'"
      :aria-current="tab.key === active ? 'page' : undefined"
      @click="$emit('select', tab.key)"
    >
      <span>{{ tab.label }}</span>
      <i
        v-if="blocked.includes(tab.key)"
        class="chart-tabs-dot"
        :data-test="`tab-blocker-${tab.key}`"
        :title="__('Blocking completion')"
      ></i>
      <i v-if="filled.includes(tab.key)" class="chart-tabs-tick" :data-test="`${tab.key}-tick`">✓</i>
      <i v-if="counts[tab.key]" class="chart-tabs-count" :data-test="`${tab.key}-tab-count`">{{ counts[tab.key] }}</i>
    </button>
  </nav>
</template>

<script setup>
const __ = window.__ || ((txt) => txt)

defineProps({
  tabs: { type: Array, default: () => [] },
  active: { type: String, default: "" },
  counts: { type: Object, default: () => ({}) },
  filled: { type: Array, default: () => [] },
  blocked: { type: Array, default: () => [] },
})

defineEmits(["select"])
</script>

<style scoped>
.chart-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 4px;
  background: var(--chart-surface);
  border: 1px solid var(--chart-border);
  border-radius: 12px;
  box-shadow: var(--chart-shadow);
}

.chart-tabs-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--chart-text-soft);
  font-size: 13px;
  font-weight: 600;
}

.chart-tabs-button:hover {
  background: var(--chart-surface-muted);
}

.chart-tabs-button:focus-visible {
  outline: none;
  box-shadow: var(--chart-focus);
}

.chart-tabs-button[data-active="true"] {
  background: var(--chart-ok-soft);
  color: var(--chart-ok-text);
}

.chart-tabs-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--chart-danger);
}

.chart-tabs-tick {
  color: var(--chart-ok);
  font-style: normal;
}

.chart-tabs-count {
  min-width: 18px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--chart-surface-muted);
  border: 1px solid var(--chart-border);
  color: var(--chart-muted);
  font-size: 11px;
  font-style: normal;
  line-height: 16px;
  text-align: center;
}
</style>
```

The `filled` tick renders `data-test="assessment-tick"` for the assessment key, matching the old markup.

- [ ] **Step 3: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
git add do_derma/public/js/chart/components/shell/SectionCard.vue do_derma/public/js/chart/components/shell/SectionTabs.vue
git commit -m "feat(chart): section card and stateful tab row in the Overview style

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `ClinicalStrip`

**Files:**
- Create: `do_derma/public/js/chart/components/shell/ClinicalStrip.vue`

**Interfaces:**
- Consumes: the `clinical_profile` shape from Task 1; `DegradedSectionNotice` (`props section, label`, emits `retry`); `--chart-*` tokens.
- Produces: `ClinicalStrip` with props `profile: Object | null`, `isDegraded: Boolean`, `patient: String`. Emits `retry`. Root `data-test="clinical-strip"`; columns `data-test="clinical-strip-allergies" | "-history" | "-medications"`; link `data-test="clinical-strip-update-history"`.

- [ ] **Step 1: Create `ClinicalStrip.vue`**

```vue
<template>
  <DegradedSectionNotice
    v-if="isDegraded"
    section="clinical-profile"
    :label="__('clinical profile')"
    @retry="$emit('retry')"
  />
  <section v-else-if="profile" class="clinical-strip" data-test="clinical-strip">
    <div class="clinical-strip-columns">
      <div class="clinical-strip-column" data-test="clinical-strip-allergies">
        <h3>⚠ {{ __("Allergies") }}</h3>
        <div class="clinical-strip-chips">
          <span v-for="allergy in profile.allergies" :key="allergy.allergen" class="clinical-strip-chip" data-tone="danger">
            {{ allergy.allergen }}
          </span>
          <span v-if="!profile.allergies.length" class="clinical-strip-chip">{{ allergyEmptyText }}</span>
        </div>
      </div>
      <div class="clinical-strip-column" data-test="clinical-strip-history">
        <h3>{{ __("Medical History") }}</h3>
        <div class="clinical-strip-chips">
          <span
            v-for="condition in profile.conditions"
            :key="condition.name"
            class="clinical-strip-chip"
            :data-tone="condition.is_critical ? 'caution' : ''"
            :title="condition.note || ''"
          >{{ condition.name }}</span>
          <span v-if="!profile.conditions.length" class="clinical-strip-chip">{{ __("Not recorded") }}</span>
        </div>
      </div>
      <div class="clinical-strip-column" data-test="clinical-strip-medications">
        <h3>{{ __("Medications") }}</h3>
        <div class="clinical-strip-chips">
          <span
            v-for="medication in profile.medications"
            :key="medication.name"
            class="clinical-strip-chip"
            :data-tone="medication.risk_class ? 'caution' : ''"
            :title="medication.risk_class || ''"
          >{{ medication.name }}</span>
          <span v-if="!profile.medications.length" class="clinical-strip-chip">{{ __("Not recorded") }}</span>
        </div>
      </div>
    </div>
    <footer class="clinical-strip-footer">
      <span v-if="surgeriesText"><b>{{ __("Surgical") }}</b> {{ surgeriesText }}</span>
      <span v-if="habitsText"><b>{{ __("Habits") }}</b> {{ habitsText }}</span>
      <span class="clinical-strip-reviewed">{{ reviewedText }}</span>
      <button
        v-if="hasHistoryDrawer"
        type="button"
        class="clinical-strip-link"
        data-test="clinical-strip-update-history"
        @click="openHistory"
      >{{ __("Update history") }} →</button>
    </footer>
  </section>
</template>

<script setup>
import { computed } from "vue"
import DegradedSectionNotice from "../DegradedSectionNotice.vue"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  profile: { type: Object, default: null },
  isDegraded: { type: Boolean, default: false },
  patient: { type: String, default: "" },
})

defineEmits(["retry"])

const allergyEmptyText = computed(() =>
  props.profile?.allergy_status === "none_known" ? __("None known") : __("Not recorded")
)
const surgeriesText = computed(() => (props.profile?.surgeries || []).map((row) => row.name).join(", "))
const habitsText = computed(() =>
  (props.profile?.habits || []).map((row) => (row.note ? `${row.habit}: ${row.note}` : row.habit)).join("; ")
)
const reviewedText = computed(() => {
  const date = props.profile?.reviewed_on?.date
  if (!date) return __("History not yet reviewed")
  return __("Reviewed {0}").replace("{0}", window.frappe?.datetime?.str_to_user?.(date) || date)
})
const hasHistoryDrawer = computed(() => typeof window.do_health?.openMedicalHistoryPanel === "function")

function openHistory() {
  window.do_health.openMedicalHistoryPanel(props.patient)
}
</script>

<style scoped>
.clinical-strip {
  background: var(--chart-surface);
  border: 1px solid var(--chart-border);
  border-radius: var(--chart-radius);
  box-shadow: var(--chart-shadow);
  overflow: hidden;
}

.clinical-strip-columns {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.clinical-strip-column {
  padding: 14px 16px;
  min-width: 0;
}

.clinical-strip-column + .clinical-strip-column {
  border-left: 1px solid var(--chart-border);
}

.clinical-strip-column h3 {
  margin: 0 0 8px;
  color: var(--chart-muted);
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.clinical-strip-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.clinical-strip-chip {
  padding: 3px 10px;
  border: 1px solid var(--chart-border-strong);
  border-radius: 999px;
  background: var(--chart-surface-muted);
  color: var(--chart-text-soft);
  font-size: 12px;
}

.clinical-strip-chip[data-tone="danger"] {
  background: var(--chart-danger-soft);
  border-color: var(--chart-danger-border);
  color: var(--chart-danger-text);
}

.clinical-strip-chip[data-tone="caution"] {
  background: var(--chart-caution-soft);
  border-color: var(--chart-caution-border);
  color: var(--chart-caution-text);
}

.clinical-strip-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 20px;
  padding: 10px 16px;
  border-top: 1px solid var(--chart-border);
  background: var(--chart-surface-muted);
  color: var(--chart-text-soft);
  font-size: 12px;
}

.clinical-strip-footer b {
  color: var(--chart-muted);
  font-weight: 500;
  margin-right: 4px;
}

.clinical-strip-reviewed {
  margin-left: auto;
  color: var(--chart-muted);
}

.clinical-strip-link {
  border: 0;
  background: transparent;
  color: var(--chart-blue);
  font-size: 12px;
  font-weight: 600;
}

@media (max-width: 900px) {
  .clinical-strip-columns {
    grid-template-columns: minmax(0, 1fr);
  }

  .clinical-strip-column + .clinical-strip-column {
    border-left: 0;
    border-top: 1px solid var(--chart-border);
  }
}
</style>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
git add do_derma/public/js/chart/components/shell/ClinicalStrip.vue
git commit -m "feat(chart): clinical strip with allergies, history and medications

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `ChartHero`

**Files:**
- Create: `do_derma/public/js/chart/components/shell/ChartHero.vue`

**Interfaces:**
- Consumes: `useBrokenImages` from `../../../shared/broken_images.js`; `--chart-*` tokens.
- Produces: `ChartHero` with the same props and emits as `DermaEncounterHeader` minus `allergyText`, plus `readiness: Object` (`{items, blockers, enforcement}`) and emit `open-readiness`. Props: `patient, appointment, encounter, practitionerName, insuranceLabel, hasSessionContext, completing, pending, canReopen, reopening, alerts, latestEncounter, visitDate, visitTime, readiness`. Emits: `complete, reopen, open-latest, alert-action, open-readiness`. It keeps the `data-test` names used by the old header: `encounter-header`, `encounter-visit-strip`, `open-latest-visit`, `header-patient-name`, `complete-session`, `reopen-session`, `encounter-completed-note`, `encounter-alerts`. New: `hero-readiness`, `hero-visit-status`.

- [ ] **Step 1: Create `ChartHero.vue`**

```vue
<template>
  <div class="chart-hero-stack" data-test="encounter-header">
    <div v-if="encounter.name && !isLatest" class="chart-hero-banner" data-test="encounter-visit-strip">
      <b>{{ __("Previous visit") }}</b>
      <span>{{ visitWhen }}</span>
      <span>{{ encounter.name }}</span>
      <span v-if="encounter.practitioner_name">· {{ encounter.practitioner_name }}</span>
      <button type="button" class="chart-hero-banner-link" data-test="open-latest-visit" @click="$emit('open-latest')">
        {{ __("Open latest visit") }} →
      </button>
    </div>

    <header class="chart-hero">
      <div class="chart-hero-identity">
        <img
          v-if="patient.image && !isBroken(patient.image)"
          class="chart-hero-avatar"
          :src="patient.image"
          :alt="patientName"
          @error="markBroken(patient.image)"
        />
        <span v-else class="chart-hero-avatar">{{ initials }}</span>
        <div class="chart-hero-text">
          <h1 data-test="header-patient-name">{{ patientName }}</h1>
          <p class="chart-hero-meta">{{ patientMeta }}</p>
          <span v-if="patient.mobile" class="chart-hero-chip">☎ {{ patient.mobile }}</span>
          <div v-if="alerts.length" class="chart-hero-alerts" data-test="encounter-alerts">
            <button
              v-for="alert in alerts"
              :key="alert.key"
              type="button"
              class="chart-hero-chip"
              :data-tone="alert.tone"
              :title="alert.detail"
              @click="$emit('alert-action', alert)"
            >
              <b>{{ alert.label }}</b>
            </button>
          </div>
        </div>
      </div>

      <aside class="chart-hero-visit">
        <div class="chart-hero-visit-top">
          <span class="chart-hero-label">{{ __("This visit") }}</span>
          <span v-if="statusLabel" class="chart-hero-status" :data-tone="isCompleted ? 'ok' : 'caution'" data-test="hero-visit-status">
            {{ statusLabel }}
          </span>
        </div>
        <strong class="chart-hero-when">{{ visitWhen || __("No visit date") }}</strong>
        <small>{{ [visitType, practitionerName].filter(Boolean).join(" · ") }}</small>
        <small>{{ insuranceLabel }}</small>
        <button
          v-if="hasSessionContext"
          type="button"
          class="chart-hero-readiness"
          :data-tone="readinessTone"
          data-test="hero-readiness"
          @click="$emit('open-readiness')"
        >{{ readinessText }}</button>
        <button
          v-if="!isCompleted"
          type="button"
          class="primary chart-hero-action"
          data-test="complete-session"
          :disabled="!hasSessionContext || completing || pending"
          @click="$emit('complete')"
        >{{ completing ? __("Completing...") : __("Complete Encounter") }}</button>
        <button
          v-else-if="canReopen"
          type="button"
          class="chart-hero-action"
          data-test="reopen-session"
          :disabled="reopening"
          @click="$emit('reopen')"
        >{{ reopening ? __("Reopening...") : __("Reopen Encounter") }}</button>
        <small v-else data-test="encounter-completed-note">{{ __("Completed. Reopening needs cancel permission.") }}</small>
      </aside>
    </header>
  </div>
</template>

<script setup>
import { computed } from "vue"
import { useBrokenImages } from "../../../shared/broken_images.js"

const __ = window.__ || ((txt) => txt)
const { isBroken, markBroken } = useBrokenImages()

const props = defineProps({
  patient: { type: Object, default: () => ({}) },
  appointment: { type: Object, default: () => ({}) },
  encounter: { type: Object, default: () => ({}) },
  practitionerName: { type: String, default: "" },
  insuranceLabel: { type: String, default: "" },
  hasSessionContext: { type: Boolean, default: false },
  completing: { type: Boolean, default: false },
  // A completion awaiting its confirm dialog: refuse a second click without claiming one is under way.
  pending: { type: Boolean, default: false },
  canReopen: { type: Boolean, default: false },
  reopening: { type: Boolean, default: false },
  alerts: { type: Array, default: () => [] },
  latestEncounter: { type: String, default: "" },
  visitDate: { type: String, default: "" },
  visitTime: { type: String, default: "" },
  readiness: { type: Object, default: () => ({ items: [], blockers: [] }) },
})

defineEmits(["complete", "reopen", "open-latest", "alert-action", "open-readiness"])

const isCompleted = computed(() => Number(props.encounter.docstatus) === 1)
const isLatest = computed(() => !props.latestEncounter || props.latestEncounter === props.encounter.name)
const visitWhen = computed(() => {
  const date = window.frappe?.datetime?.str_to_user?.(props.visitDate) || props.visitDate
  // Frappe sends times as "7:15:15.9": pad the hour, drop the seconds.
  const [hour = "", minute = ""] = props.visitTime.split(":")
  const time = hour && minute ? `${hour.padStart(2, "0")}:${minute}` : ""
  return [date, time].filter(Boolean).join(" · ")
})
const patientName = computed(() => props.patient.patient_name || props.patient.name || __("Patient"))
const initials = computed(() => patientName.value.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "P")
const age = computed(() => {
  if (!props.patient.dob) return ""
  const born = new Date(props.patient.dob)
  const today = new Date()
  const hasHadBirthday =
    today.getMonth() > born.getMonth() || (today.getMonth() === born.getMonth() && today.getDate() >= born.getDate())
  return `${today.getFullYear() - born.getFullYear() - (hasHadBirthday ? 0 : 1)} y`
})
const patientMeta = computed(() =>
  [
    age.value,
    props.patient.sex,
    props.patient.custom_file_number ? `${__("File")} ${props.patient.custom_file_number}` : `${__("MRN")} ${props.patient.name || ""}`,
    props.patient.custom_cpr ? `${__("CPR")} ${props.patient.custom_cpr}` : "",
  ].filter((part) => part && part.trim()).join(" · ")
)
const visitType = computed(() => props.appointment.custom_appointment_category || props.appointment.appointment_type || props.encounter.appointment_type || "")
const statusLabel = computed(() => (isCompleted.value ? __("Completed") : props.appointment.status || ""))
const blockerCount = computed(() => (props.readiness.blockers || []).length)
const warningCount = computed(() => (props.readiness.items || []).length - blockerCount.value)
const readinessTone = computed(() => (blockerCount.value ? "danger" : warningCount.value ? "caution" : "ok"))
const readinessText = computed(() => {
  const warnings = warningCount.value ? __("{0} warning(s)").replace("{0}", warningCount.value) : ""
  if (blockerCount.value) {
    return [__("{0} blocker(s)").replace("{0}", blockerCount.value), warnings].filter(Boolean).join(" · ")
  }
  return warnings || __("Ready to complete")
})
</script>

<style scoped>
.chart-hero-stack {
  display: grid;
  gap: 8px;
}

.chart-hero-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border: 1px solid var(--chart-caution-border);
  border-radius: 10px;
  background: var(--chart-caution-soft);
  color: var(--chart-caution-text);
  font-size: 12px;
}

.chart-hero-banner-link {
  margin-left: auto;
  border: 0;
  background: transparent;
  color: var(--chart-blue);
  font-weight: 600;
}

.chart-hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 18px;
  background: var(--chart-surface);
  border: 1px solid var(--chart-border);
  border-radius: 18px;
  box-shadow: var(--chart-shadow);
}

.chart-hero-identity {
  display: flex;
  gap: 18px;
  min-width: 0;
}

.chart-hero-avatar {
  display: grid;
  place-items: center;
  flex: 0 0 96px;
  width: 96px;
  height: 96px;
  border-radius: 20px;
  border: 4px solid var(--chart-surface);
  box-shadow: 0 0 0 1px var(--chart-border), var(--chart-shadow);
  background: linear-gradient(135deg, #dcfce7, #d1fae5);
  color: var(--chart-ok-text);
  font-size: 32px;
  font-weight: 700;
  object-fit: cover;
}

.chart-hero-text {
  display: grid;
  align-content: start;
  justify-items: start;
  gap: 6px;
  min-width: 0;
}

.chart-hero-text h1 {
  margin: 0;
  color: var(--chart-text);
  font-size: 22px;
  font-weight: 750;
}

.chart-hero-meta {
  margin: 0;
  color: var(--chart-text-soft);
  font-size: 13px;
}

.chart-hero-chip {
  display: inline-flex;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid var(--chart-border-strong);
  border-radius: 999px;
  background: var(--chart-surface);
  color: var(--chart-text-soft);
  font-size: 12px;
}

.chart-hero-chip[data-tone="danger"] {
  background: var(--chart-danger-soft);
  border-color: var(--chart-danger-border);
  color: var(--chart-danger-text);
}

.chart-hero-chip[data-tone="warning"] {
  background: var(--chart-caution-soft);
  border-color: var(--chart-caution-border);
  color: var(--chart-caution-text);
}

.chart-hero-alerts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chart-hero-visit {
  display: grid;
  align-content: start;
  gap: 4px;
  flex: 0 0 240px;
  padding: 12px 14px;
  border: 1px solid var(--chart-border);
  border-radius: 12px;
  background: var(--chart-surface-muted);
  color: var(--chart-muted);
  font-size: 12px;
}

.chart-hero-visit-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-hero-label {
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.chart-hero-status {
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.chart-hero-status[data-tone="caution"] {
  background: var(--chart-caution-soft);
  border: 1px solid var(--chart-caution-border);
  color: var(--chart-caution-text);
}

.chart-hero-status[data-tone="ok"] {
  background: var(--chart-ok-soft);
  color: var(--chart-ok-text);
}

.chart-hero-when {
  color: var(--chart-text);
  font-size: 15px;
}

.chart-hero-readiness {
  justify-self: start;
  margin-top: 6px;
  padding: 0;
  border: 0;
  background: transparent;
  font-size: 12px;
  font-weight: 650;
}

.chart-hero-readiness[data-tone="danger"] { color: var(--chart-danger-text); }
.chart-hero-readiness[data-tone="caution"] { color: var(--chart-caution-text); }
.chart-hero-readiness[data-tone="ok"] { color: var(--chart-ok-text); }

.chart-hero-action {
  margin-top: 8px;
  width: 100%;
}

@media (max-width: 900px) {
  .chart-hero {
    flex-direction: column;
  }

  .chart-hero-visit {
    flex-basis: auto;
  }
}
</style>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
git add do_derma/public/js/chart/components/shell/ChartHero.vue
git commit -m "feat(chart): hero card with the visit box and readiness line

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Wire the shell into `DermaChart.vue`

**Files:**
- Modify: `do_derma/public/js/chart/DermaChart.vue`
- Delete: `do_derma/public/js/chart/components/DermaEncounterHeader.vue`

**Interfaces:**
- Consumes: `ChartHero`, `ClinicalStrip`, `SectionTabs`, `SectionCard` (Tasks 3–5); payload `clinical_profile` and the `"clinical profile"` context error (Task 1); existing `readiness`, `readinessBlockers`, `setActiveSection`, `assessmentModeToggleVisible`, `assessmentModeLocked`, `assessmentPanel`, `requestAssessmentModeChange`, `assessmentModeShortLabel`, `procedureCount`, `photoCount`, `prescriptionCount`.

- [ ] **Step 1: Replace the imports**

Replace `import DermaEncounterHeader from "./components/DermaEncounterHeader.vue"` with:

```js
import ChartHero from "./components/shell/ChartHero.vue"
import ClinicalStrip from "./components/shell/ClinicalStrip.vue"
import SectionTabs from "./components/shell/SectionTabs.vue"
import SectionCard from "./components/shell/SectionCard.vue"
```

- [ ] **Step 2: Drop the tab hints**

Replace `SECTION_TABS` with:

```js
const SECTION_TABS = [
  { key: "assessment", label: __("Assessment") },
  { key: "procedures", label: __("Procedures") },
  { key: "photos", label: __("Photos") },
  { key: "prescriptions", label: __("Prescription") },
  { key: "review", label: __("Review") },
]
```

- [ ] **Step 3: Add the shell computeds and the readiness jump**

Add directly below the `readinessEnforcement` computed:

```js
const clinicalProfile = computed(() => data.value.clinical_profile || null)
const isClinicalProfileDegraded = computed(() => (data.value.context_errors || []).includes("clinical profile"))
// Both readiness engines read procedure marks, so a blocker is cleared on Procedures.
const blockedSections = computed(() => (readinessBlockers.value.length ? ["procedures", "review"] : []))
const sectionTabCounts = computed(() => ({
  procedures: procedureCount.value,
  photos: photoCount.value,
  prescriptions: prescriptionCount.value,
}))
const filledSections = computed(() => (assessmentPanel.isFilled ? ["assessment"] : []))
const activeSectionLabel = computed(() => SECTION_TABS.find((tab) => tab.key === activeSection.value)?.label || "")

function openReadiness() {
  setActiveSection(readinessBlockers.value.length ? "procedures" : "review")
}
```

`prescriptionCount` (line ~831) is declared below this spot. That is fine: computed bodies run lazily, after setup.

- [ ] **Step 4: Replace the header and tab bar in the template**

Replace the whole `<DermaEncounterHeader ... />` element and the whole `<section class="derma-section-bar" ...> ... </section>` block (template lines ~34–115) with:

```vue
      <ChartHero
        :patient="patient"
        :appointment="appointment"
        :encounter="encounter"
        :practitioner-name="currentPractitionerName"
        :insurance-label="insuranceStatusLabel"
        :has-session-context="hasSessionContext"
        :completing="completingSession"
        :pending="completionPending"
        :can-reopen="Boolean(reopenPermissions.can_reopen_encounter)"
        :reopening="reopeningSession"
        :alerts="encounterAlertItems"
        :latest-encounter="data.latest_encounter || ''"
        :visit-date="data.visit_date || ''"
        :visit-time="data.visit_time || ''"
        :readiness="readiness"
        @complete="completeSession"
        @reopen="reopenSession"
        @open-latest="openLatestVisit"
        @alert-action="handleEncounterAlert"
        @open-readiness="openReadiness"
      />

      <ClinicalStrip
        :profile="clinicalProfile"
        :is-degraded="isClinicalProfileDegraded"
        :patient="patient.name || ''"
        @retry="refresh"
      />

      <SectionTabs
        :tabs="SECTION_TABS"
        :active="activeSection"
        :counts="sectionTabCounts"
        :filled="filledSections"
        :blocked="blockedSections"
        @select="setActiveSection"
      />
```

- [ ] **Step 5: Wrap the section chain in `SectionCard` and move the mode toggle**

Directly after `<main class="derma-console-main">` insert:

```vue
          <SectionCard :label="activeSectionLabel">
            <template v-if="assessmentModeToggleVisible" #actions>
              <div
                class="tab-mode-toggle"
                data-test="assessment-mode-toggle"
                role="group"
                :aria-label="__('Assessment format')"
                :data-locked="assessmentModeLocked ? 'true' : 'false'"
                :title="assessmentModeLocked ? __('The format is locked after submission.') : ''"
              >
                <button
                  v-for="toggleMode in assessmentPanel.availableModes"
                  :key="toggleMode"
                  type="button"
                  class="ghost small"
                  :disabled="assessmentModeLocked"
                  :data-test="`assessment-mode-${toggleMode.toLowerCase()}`"
                  :data-active="assessmentPanel.mode === toggleMode ? 'true' : 'false'"
                  @click="requestAssessmentModeChange(toggleMode)"
                >{{ assessmentModeShortLabel(toggleMode) }}</button>
              </div>
            </template>
```

and directly before `</main>` insert `          </SectionCard>`.

Update the comment above `assessmentModeToggleVisible` (it talks about an inactive tab's hint) to:

```js
// The format switch sits in the Assessment card header, so it shows only on that section.
```

- [ ] **Step 6: Delete the old header**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
git rm do_derma/public/js/chart/components/DermaEncounterHeader.vue
grep -rn "DermaEncounterHeader\|allergyText\|section.hint" do_derma/public/js/chart
```

Expected: no output.

- [ ] **Step 7: Build and confirm it compiles**

```bash
cd /Users/hameed/Developer/bench-v16
bench build --app do_derma 2>&1 | tail -15
```

Expected: the build finishes listing `derma_chart.bundle.*.js` and `.css` with no `error`. Then restart the web server (see "Test commands").

- [ ] **Step 8: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
git add -A do_derma/public/js/chart
git commit -m "feat(chart): Patient Overview shell on the derma chart

The hero, clinical strip, stateful tabs and section card replace the
encounter header and the hint-line tab bar. Readiness moves into the hero's
This-visit box; a blocker dots Procedures and Review. The assessment format
switch moves from the tab into the Assessment card header.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Browser verification of behaviour

**Files:** none changed unless a check fails. Fix in the owning component and amend with a new commit.

- [ ] **Step 1: Log in**

```bash
cd /Users/hameed/Developer/bench-v16
bench --site dermaone.localhost browse --user Administrator   # prints a port-8002 ?sid= URL
```

If nothing listens on 8002, start `bench serve --port 8002`. If any request returns 503 QueueOverloaded, drain with `bench worker --queue default --burst`.

- [ ] **Step 2: Check each behaviour on `/app/derma-chart` with a patient selected from the health sidebar**

| Check | Expected |
|---|---|
| Patient with no history | Strip shows "Not recorded" in all three columns and "History not yet reviewed". No "Update history" link (do_health does not export the opener yet) |
| Patient with allergies, a critical condition and an isotretinoin medication (add them on the Patient form) | Allergy chips red; condition and medication chips amber; medication chip title shows the risk class |
| A readiness blocker (a product-consuming mark with an expired lot) | Hero reads "1 blocker(s)" in red; red dots on Procedures and Review; clicking the line opens Procedures |
| Warnings only | Hero reads "{n} warning(s)" in amber; clicking opens Review; no tab dots |
| Nothing pending | Hero reads "Ready to complete" in green |
| Block enforcement with a blocker | Completing is refused with today's dialog |
| An older encounter (open from Previous Visits) | Amber banner above the hero; "Open latest visit" opens the latest |
| Submitted encounter | Status pill "Completed" (green); Reopen button or the completed note per permission |
| Assessment tab | Card header reads ASSESSMENT with the SOAP / H&P / Structured switch on the right; switching works; locked after submission |
| Other tabs | Card header shows the label; panel toolbars (New Procedure, New Consent) unchanged inside |
| `do_health.openMedicalHistoryPanel = () => {}` in the console, then re-render (switch tabs) | "Update history →" appears |

- [ ] **Step 3: Record results**

Note any failure, fix it, rebuild, re-check, and commit the fix as `fix(chart): ...`.

---

### Task 8: Remove dead CSS and do the visual pass

**Files:**
- Modify: `do_derma/public/js/chart/derma_chart.bundle.css`

- [ ] **Step 1: List candidate selectors and confirm zero users**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma/do_derma/public/js/chart
for cls in derma-encounter-header encounter-visit-strip encounter-visit-pill encounter-open-latest encounter-patient encounter-status-strip encounter-chip encounter-actions encounter-alert-chips encounter-alert-chip encounter-completed-note is-latest-visit is-previous-visit derma-section-bar derma-section-tabs tab-tick tab-count; do
  users=$(grep -rln -- "$cls" --include="*.vue" --include="*.jsx" --include="*.js" . | grep -v node_modules | wc -l | tr -d ' ')
  echo "$cls $users"
done
```

Delete rules only for classes that print `0`. `tab-mode-toggle` is still used (Task 6) and stays. `patient-avatar` is not on the list, because other components may use it.

- [ ] **Step 2: Delete those rule blocks, checking brace depth first**

For each rule to delete, run:

```bash
python3 - <<'EOF'
import re, sys
css = open("derma_chart.bundle.css").read()
depth = 0
for number, line in enumerate(css.splitlines(), 1):
    if re.search(r"\.(derma-encounter-header|encounter-[a-z-]+|derma-section-(bar|tabs)|tab-tick|tab-count|is-(latest|previous)-visit)\b", line) and "{" in line:
        print(number, depth, line.strip())
    depth += line.count("{") - line.count("}")
EOF
```

Depth `0` means top level. Depth `1` means inside an `@media` block. Delete each listed block whole. If a selector list mixes a dead class with a live one, remove only the dead selector from the list. When an `@media` block becomes empty, delete it too. Do not touch the early-closing `@media` itself.

- [ ] **Step 3: Rebuild, restart, run the theme tests**

```bash
cd /Users/hameed/Developer/bench-v16
bench build --app do_derma 2>&1 | tail -5
bench --site dermaone.localhost run-tests --module do_derma.tests.test_chart_theme 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"
```

Expected: build OK; `Ran 3 tests` / `OK`. Restart the web server.

- [ ] **Step 4: Visual pass**

At 1280, 1600 and 1920 px, with desk in light mode and then in dark mode (user menu → Toggle Theme):
- the hero, strip, tabs and card read like the Patient Overview (grey canvas, white cards, uppercase labels, pills)
- the chart stays light in dark mode
- no element overflows horizontally; tabs wrap rather than clip
- the Procedures toolbar (New Consent, New Procedure) is fully visible inside the card

Take a screenshot at each width for the PR description.

- [ ] **Step 5: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
git add do_derma/public/js/chart/derma_chart.bundle.css
git commit -m "refactor(chart): drop styles of the retired encounter header and tab bar

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Full suite diff

- [ ] **Step 1: Run the do_derma suite on the branch**

The tree must be clean apart from untracked `.serena/`.

```bash
cd /Users/hameed/Developer/bench-v16
RESULTS=$(mktemp -d)
bench --site dermaone.localhost run-tests --app do_derma 2>&1 | grep -E "^\s*(FAIL|ERROR)\s" | sort > "$RESULTS/branch.txt"
```

- [ ] **Step 2: Compare against `main`**

```bash
git -C apps/do_derma checkout main
bench build --app do_derma >/dev/null
bench --site dermaone.localhost run-tests --app do_derma 2>&1 | grep -E "^\s*(FAIL|ERROR)\s" | sort > "$RESULTS/main.txt"
git -C apps/do_derma checkout feat/derma-chart-overview-skin
bench build --app do_derma >/dev/null
comm -13 "$RESULTS/main.txt" "$RESULTS/branch.txt"
```

Expected: no lines, meaning no failure on the branch that is not also on `main`. The `main` set is the standing baseline in "Test commands" (it varies with site data). Restart the web server afterwards.

---

## Not in this plan

- do_health exporting `openMedicalHistoryPanel` on `window.do_health`. That's a separate one-line do_health PR the user approves on its own. The chart picks it up with no change.
- Phase 2: dark mode, moving panel toolbars into the card header, and panel internals onto `--chart-*`.
