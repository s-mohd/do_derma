# Assessment Tab Restyle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the derma chart's Assessment tab match the restyled Procedures tab (header actions, one filled button, pills and labels, flat sections) and show better content (real table rows, previous-visit format and procedures, other-format pills, quieter status, compact dictation result).

**Architecture:** Server: `assessment.get_preview_text` renders table rows, and `previous_visits._build_visit` adds `mode_label` and `procedures` through a `load_procedures` callable supplied by `api.get_previous_visits`. Client: edits in place in the five `components/assessment/*.vue` files, the Assessment block of `DermaChart.vue`, and the matching rules in `derma_chart.bundle.css`. One stack rule in the bundle owns the dividers between sections.

**Tech Stack:** Vue 3 SFC (built by `bench build`), Frappe desk, Python `unittest` via `bench run-tests`.

**Spec:** `.planning/specs/2026-10-03-derma-assessment-restyle.md`

## Global Constraints

- Branch `feat/derma-assessment-restyle` (spec committed in ecbc1ca), stacked on `feat/derma-procedures-restyle`.
- Component styles read `--chart-*` tokens only; no hex colours (`test_component_styles_carry_no_hex`).
- `.chart-pill` with `data-tone` neutral (no attribute) | accent | ok | info | caution | danger. `.chart-label` is the small uppercase label.
- Teleports only target `#chart-section-actions` with `defer` (`test_teleports_target_the_section_card`).
- Keep every existing `data-test` hook listed in `ASSESSMENT_HOOKS` (Task 4). New hooks may be added.
- One filled (`primary`) button in the tab: Edit / Save. `Start Assessment` (empty state only) stays `primary`.
- `get_previous_visits` keeps its keys; it only adds `mode_label` and `procedures` per visit. Visit eligibility is unchanged.
- Repo Python is tab-indented. Lint changed Python with `pipx run ruff check` / `pipx run ruff format`.
- Commit messages: conventional type prefix, ending with
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Commands

Run from `/Users/hameed/Developer/bench-v16`:

- Theme tests: `bench --site dermaone.localhost run-tests --module do_derma.tests.test_chart_theme 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)"`
- Previous-visit tests: `bench --site dermaone.localhost run-tests --module do_derma.tests.test_previous_visits 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)"`
- Assessment tests: same with `do_derma.tests.test_assessment`.
- `--test ClassName` is a silent no-op on this bench; always run the whole module.
- Build: `bench build --app do_derma`, then restart the 8002 web server (after a build every `/assets/do_derma/...` URL 404s until the server restarts).
- Browser login: `bench --site dermaone.localhost browse --user Administrator` prints a port-8002 `?sid=` URL. Open the chart with
  `frappe.route_options = {patient: "PAT-2017-10285", encounter: "HLC-ENC-2026-18379"}; frappe.set_route("derma-chart")`. The page scrolls inside `.main-section`, not the window.

## Review Focus

1. **A format pill offers a format the clinic has since disabled.** If SOAP has content but is no longer in `availableModes`, clicking would call a server that refuses. Pills for unavailable formats render as inert `<span>`s. Pinned in Task 5 (`test_other_format_pills_switch_through_the_confirm_prompt`).
2. **A long AI diagnosis runs out of its pill.** `.chart-pill` is `nowrap`, so a sentence-long diagnosis would overflow the section at 1280. The result pills wrap. Pinned in Task 7 (`test_dictation_result_is_pills_and_toggles`).
3. **A toggle stays open on a stale block.** With "Arabic note" open, a new dictation whose result has no Arabic note would leave the toggle state pointing at nothing. The open toggle resets whenever the summary changes. Pinned in Task 7.
4. **Two procedures with the same title in one previous visit** (two Aerolase sessions) would give duplicate Vue keys and drop a pill. Keys use the index. Pinned in Task 3 (`test_previous_visit_header_shows_format_and_procedures`).
5. **Header buttons linger while the tab has no encounter or is loading.** Teleported Print/Edit/Save render only when `hasEncounter && !loading`. Pinned in Task 4 (`test_edit_save_and_print_live_in_the_card_header`).

---

## File Structure

| File | Change |
|---|---|
| `do_derma/assessment.py` | `_preview_text` → public `get_preview_text`; tables render their rows (Task 1) |
| `do_derma/previous_visits.py` | `get_page` / `_build_visit` take `load_procedures`; visits carry `mode_label`, `procedures` (Task 2) |
| `do_derma/api.py` | `_load_visit_procedure_titles(doc)`; passed to `get_page` (Task 2) |
| `do_derma/public/js/chart/components/assessment/PreviousVisitsPanel.vue` | Header pills, flat section, label `dt` (Task 3) |
| `do_derma/public/js/chart/components/assessment/AssessmentPanel.vue` | Teleported header actions, status pill, advice section, other-format pills, no footer (Tasks 4, 5) |
| `do_derma/public/js/chart/DermaChart.vue` | `mode-locked` / `@switch-mode` wiring (Task 5); Drawings button and card class (Task 8) |
| `do_derma/public/js/chart/components/assessment/SoapNoteFields.vue`, `StructuredAssessmentFields.vue` | Label headings, plain read text, chart inputs (Task 6) |
| `do_derma/public/js/chart/components/assessment/VoiceScribe.vue` | Ghost Dictate, pill and toggle result (Task 7) |
| `do_derma/public/js/chart/derma_chart.bundle.css` | Previous-visit spacing (Task 3), voice rules (Task 7), stack dividers and Drawings header (Task 8) |
| `do_derma/tests/test_assessment.py`, `test_previous_visits.py`, `test_chart_theme.py` | New tests per task |

---

### Task 1: Table fields preview their rows

**Files:**
- Modify: `do_derma/assessment.py:257-304` (`get_preview`, `_preview_text`)
- Test: `do_derma/tests/test_assessment.py`

**Interfaces:**
- Produces: `assessment.get_preview_text(row: dict, value: Any) -> str` (public; replaces `_preview_text`). Table rows join as `"<field> <field>; <field> <field>"`.

- [ ] **Step 1: Write the failing test.** Append to `do_derma/tests/test_assessment.py` (plain `TestCase`, no site data needed beyond translation):

```python
DIAGNOSIS_TABLE = {
	"fieldtype": "Table",
	"fieldname": "diagnosis",
	"fields": [
		{"fieldname": "code", "label": "Code", "fieldtype": "Data"},
		{"fieldname": "description", "label": "Description", "fieldtype": "Data"},
	],
}


class TestPreviewText(IntegrationTestCase):
	def test_a_table_previews_its_rows_not_a_count(self):
		rows = [{"code": "L29.8", "description": "Other pruritus"}, {"code": "L21.0", "description": ""}]
		self.assertEqual(assessment.get_preview_text(DIAGNOSIS_TABLE, rows), "L29.8 Other pruritus; L21.0")

	def test_a_table_of_empty_rows_previews_nothing(self):
		self.assertEqual(assessment.get_preview_text(DIAGNOSIS_TABLE, [{"code": "", "description": " "}]), "")
		self.assertEqual(assessment.get_preview_text(DIAGNOSIS_TABLE, []), "")

	def test_a_text_field_previews_plain_text(self):
		self.assertEqual(assessment.get_preview_text({"fieldtype": "Text Editor"}, "<p>Dry &amp; flaky.</p>"), "Dry & flaky.")
```

- [ ] **Step 2: Run the assessment tests; expect the three new tests to ERROR** with `AttributeError: module 'do_derma.assessment' has no attribute 'get_preview_text'`.

- [ ] **Step 3: Implement.** In `do_derma/assessment.py` replace `_preview_text` and its call in `get_preview`:

```python
def get_preview(encounter_doc) -> list[dict[str, str]]:
	"""The documented format's filled fields as label and plain text."""
	layout = get_layout(get_assessment_mode(encounter_doc))
	values = serialize_values(encounter_doc, layout)
	preview = []
	for row in layout:
		text = get_preview_text(row, values.get(row.get("fieldname")))
		if text:
			preview.append({"label": _(row.get("label") or row.get("fieldname")), "value": text})
	return preview
```

```python
def get_preview_text(row: dict[str, Any], value: Any) -> str:
	"""One line per field; a table lists its filled rows, separated by semicolons."""
	if row.get("fieldtype") in TABLE_FIELD_TYPES:
		return "; ".join(" ".join(pair["value"] for pair in pairs) for pairs in get_table_rows(row, value))
	return get_field_text(row.get("fieldtype"), value)
```

- [ ] **Step 4: Run assessment and previous-visit tests; expect all to pass** (`test_preview_is_label_and_plain_text` still passes).

- [ ] **Step 5: Lint and commit.**

```bash
pipx run ruff check do_derma/assessment.py do_derma/tests/test_assessment.py
pipx run ruff format do_derma/assessment.py do_derma/tests/test_assessment.py
git add do_derma/assessment.py do_derma/tests/test_assessment.py
git commit -m "feat(assessment): previous visits preview a table's rows, not its row count

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Previous visits carry their format and procedures

**Files:**
- Modify: `do_derma/previous_visits.py:17-43` (`get_page`), `:122-133` (`_build_visit`)
- Modify: `do_derma/api.py:4589-4614` (add `_load_visit_procedure_titles`, pass it)
- Test: `do_derma/tests/test_previous_visits.py`

**Interfaces:**
- Consumes: `api._get_visit_summary_procedures(doc) -> list[dict]` (existing; `title` key, cancelled excluded).
- Produces: each visit dict gains `mode_label: str` and `procedures: list[str]`. `previous_visits.get_page(patient, current_encounter, start, page_length, load_drawings, load_procedures)`.

- [ ] **Step 1: Write the failing tests.** Append to `do_derma/tests/test_previous_visits.py`:

```python
class TestPreviousVisitHeader(PrescriptionHelpers, IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.patient = self._make_patient()

	def _assessed(self, mode, fieldname, text="Mild erythema."):
		encounter = self._make_encounter(self.patient)
		encounter.db_set(assessment.MODE_FIELD, mode)
		encounter.db_set(fieldname, text)
		return encounter

	def _structured_text_field(self):
		for row in assessment.get_structured_layout():
			if row.get("is_value_field") and row.get("fieldtype") in TEXT_TYPES:
				return row["fieldname"]
		self.skipTest("This site's structured layout has no text field.")

	def _visits(self):
		return {visit["encounter"]: visit for visit in api.get_previous_visits(self.patient)["visits"]}

	def test_each_visit_names_its_format(self):
		if not assessment.soap_is_supported():
			self.skipTest("SOAP custom fields are not installed on this site")
		structured = self._assessed(assessment.STRUCTURED, self._structured_text_field())
		soap = self._assessed(assessment.SOAP, assessment.SOAP_FIELDS[0])

		visits = self._visits()

		self.assertEqual(visits[structured.name]["mode_label"], "Structured Assessment")
		self.assertEqual(visits[soap.name]["mode_label"], "SOAP Note")

	def test_each_visit_lists_its_procedures_without_cancelled_ones(self):
		field = api._get_clinical_procedure_encounter_field()
		if not field:
			self.skipTest("Clinical Procedure has no encounter link on this site.")
		encounter = self._assessed(assessment.STRUCTURED, self._structured_text_field())
		kept, cancelled = (self._make_clinical_procedure(self.patient) for _ in range(2))
		for procedure in (kept, cancelled):
			procedure.db_set(field, encounter.name)
		cancelled.db_set("docstatus", 2)

		titles = self._visits()[encounter.name]["procedures"]

		summary = api.get_visit_summary(encounter.name)["procedures"]
		self.assertEqual(titles, [row["title"] for row in summary])
		self.assertEqual(len(titles), 1)

	def test_a_visit_with_only_procedures_is_still_not_listed(self):
		field = api._get_clinical_procedure_encounter_field()
		if not field:
			self.skipTest("Clinical Procedure has no encounter link on this site.")
		encounter = self._make_encounter(self.patient)
		self._make_clinical_procedure(self.patient).db_set(field, encounter.name)

		self.assertEqual(self._visits(), {})
```

- [ ] **Step 2: Run the previous-visit tests; expect the first two to fail with `KeyError: 'mode_label'` / `KeyError: 'procedures'`.** The third already passes; it guards eligibility.

- [ ] **Step 3: Implement.** In `do_derma/previous_visits.py`:

```python
def get_page(
	patient: str,
	current_encounter: str | None,
	start: int,
	page_length: int,
	load_drawings: Callable[[str], list[dict[str, Any]]],
	load_procedures: Callable[[Any], list[str]],
) -> dict[str, Any]:
```

and inside its loop `visit = _build_visit(row, load_drawings, load_procedures)`. Then:

```python
def _build_visit(row, load_drawings, load_procedures) -> dict[str, Any] | None:
	drawings = load_drawings(row.name)
	doc = frappe.get_doc("Patient Encounter", row.name)
	preview = assessment.get_preview(doc)
	if not drawings and not preview:
		return None
	return {
		"encounter": row.name,
		"visit_date": row.visit_date,
		"practitioner_name": row.practitioner_name or row.practitioner or "",
		"mode_label": _(assessment.MODE_LABELS[assessment.get_assessment_mode(doc)]),
		"procedures": load_procedures(doc),
		"drawings": drawings,
		"assessment": preview,
	}
```

(`_` is already imported in `previous_visits.py`; check the imports and add `from frappe import _` if not.) In `do_derma/api.py`, after `_load_visit_drawings`:

```python
def _load_visit_procedure_titles(doc) -> list[str]:
	return [row["title"] for row in _get_visit_summary_procedures(doc)]
```

and pass it as the last argument of `previous_visits.get_page(...)` in `get_previous_visits`.

- [ ] **Step 4: Run previous-visit tests; expect all to pass** (`test_a_capped_scan_hands_on_to_load_more` still passes, so the paging contract is unchanged).

- [ ] **Step 5: Lint and commit.**

```bash
pipx run ruff check do_derma/previous_visits.py do_derma/tests/test_previous_visits.py
pipx run ruff format do_derma/previous_visits.py do_derma/tests/test_previous_visits.py
git add do_derma/previous_visits.py do_derma/api.py do_derma/tests/test_previous_visits.py
git commit -m "feat(previous-visits): each visit names its format and its procedures

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

(Do not run `ruff format` on `api.py`: it has pre-existing findings; lint only the lines you changed by eye.)

---

### Task 3: Previous visits header pills and flat section

**Files:**
- Modify: `do_derma/public/js/chart/components/assessment/PreviousVisitsPanel.vue:1-60`, script constants
- Modify: `do_derma/public/js/chart/derma_chart.bundle.css:646-700` (`.previous-visit*`)
- Test: `do_derma/tests/test_chart_theme.py`

**Interfaces:**
- Consumes: visit `mode_label`, `procedures` (Task 2).
- Produces: `ASSESSMENT_DIR`, `get_component_parts(path)` helpers in `test_chart_theme.py`, used by Tasks 4–8.

- [ ] **Step 1: Add helpers and the failing test** to `do_derma/tests/test_chart_theme.py`. Replace `get_panel_parts` with a general helper and keep the old name:

```python
def get_component_parts(path: Path) -> tuple[str, str, str]:
	"""Template, script and scoped style of a single-file component."""
	template, rest = path.read_text().split("<script setup>", 1)
	script, style = rest.split("<style scoped>", 1)
	return template, script, style


def get_panel_parts() -> tuple[str, str, str]:
	"""Template, script and scoped style of the procedure panel."""
	return get_component_parts(PROCEDURE_PANEL)
```

At the end of the file:

```python
ASSESSMENT_DIR = CHART_DIR / "components" / "assessment"


class TestAssessmentRestyle(TestCase):
	"""The Assessment tab wears the chart's shared vocabulary (spec 2026-10-03)."""

	def test_previous_visit_header_shows_format_and_procedures(self):
		template, script, _ = get_component_parts(ASSESSMENT_DIR / "PreviousVisitsPanel.vue")
		header = get_element(template, '<article v-for="visit in visits"')
		self.assertIn('data-test="previous-visit-mode"', header)
		self.assertIn("visit.procedures.slice(0, PROCEDURE_PILLS)", header)
		self.assertRegex(header, r':key="`\$\{visit\.encounter\}-procedure-\$\{index\}`"')
		self.assertIn("visit.procedures.length - PROCEDURE_PILLS", header)
		self.assertIn("const PROCEDURE_PILLS = 3", script)
		self.assertIn('<dt class="chart-label">', template)
		self.assertNotIn("chart-inner-card", template)
```

- [ ] **Step 2: Run theme tests; expect `test_previous_visit_header_shows_format_and_procedures` to FAIL.**

- [ ] **Step 3: Implement.** In `PreviousVisitsPanel.vue`, change the root class to `class="chart-annotation-history previous-visits"` (drop `chart-inner-card`). Replace the visit header:

```vue
      <header>
        <b>{{ formatDate(visit.visit_date) }}</b>
        <small>{{ visit.practitioner_name }}</small>
        <span v-if="visit.mode_label" class="chart-pill" data-test="previous-visit-mode">{{ visit.mode_label }}</span>
        <span
          v-for="(title, index) in visit.procedures.slice(0, PROCEDURE_PILLS)"
          :key="`${visit.encounter}-procedure-${index}`"
          class="chart-pill"
          data-test="previous-visit-procedure"
        >{{ title }}</span>
        <span v-if="visit.procedures.length > PROCEDURE_PILLS" class="chart-pill">+{{ visit.procedures.length - PROCEDURE_PILLS }}</span>
        <button
          type="button"
          class="ghost small"
          data-test="previous-visit-summary"
          @click="summaryEncounter = visit.encounter"
        >
          {{ __("View Summary") }}
        </button>
      </header>
```

Change `<dt>{{ field.label }}</dt>` to `<dt class="chart-label">{{ field.label }}</dt>`. In the script, beside `PREVIEW_FIELDS`: `const PROCEDURE_PILLS = 3`.

In `derma_chart.bundle.css`, edit the existing rules:

```css
.previous-visit {
  display: grid;
  gap: 10px;
  padding: 12px 0;
  border-top: 1px solid var(--chart-border);
}

.previous-visit > header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 8px;
}

.previous-visits-actions {
  display: flex;
  gap: 8px;
}
```

and narrow `.previous-visit > header small, .previous-visit-assessment dt { color: ... }` to `.previous-visit > header small { color: var(--chart-muted); }` (the `dt` now takes `.chart-label`).

- [ ] **Step 4: Run theme tests; expect all to pass.**

- [ ] **Step 5: Commit.**

```bash
git add do_derma/public/js/chart/components/assessment/PreviousVisitsPanel.vue do_derma/public/js/chart/derma_chart.bundle.css do_derma/tests/test_chart_theme.py
git commit -m "feat(previous-visits): visit headers show the format and procedures as pills

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Header actions, status pill and advice section

**Files:**
- Modify: `do_derma/public/js/chart/components/assessment/AssessmentPanel.vue` (template, script, style)
- Test: `do_derma/tests/test_chart_theme.py`

**Interfaces:**
- Produces: `headerStatus` computed in `AssessmentPanel.vue`; `ASSESSMENT_HOOKS` and `get_assessment_sources()` in the test file (used by Tasks 5–8).

- [ ] **Step 1: Write the failing tests.** Add to `test_chart_theme.py`, above `TestAssessmentRestyle`:

```python
ASSESSMENT_HOOKS = (
	"assessment-mode-toggle", "assessment-section", "assessment-start", "assessment-panel",
	"assessment-error", "assessment-other-format", "assessment-advice", "assessment-advice-toggle",
	"assessment-advice-language", "assessment-print", "assessment-edit", "assessment-save",
	"annotate-consultation", "annotation-resume", "annotation-delete",
	"previous-visits", "previous-visit", "previous-visit-summary", "previous-visit-show-all",
	"previous-visits-more", "previous-visits-collapse",
	"voice-scribe", "voice-start", "voice-stop", "voice-pause", "voice-mic", "voice-silence",
	"voice-meter", "voice-refine", "voice-result", "voice-waveform",
)


def get_assessment_block() -> str:
	"""The Assessment tab's markup inside DermaChart.vue."""
	chart = (CHART_DIR / "DermaChart.vue").read_text()
	return chart.split("<template v-if=\"activeSection === 'assessment'\">", 1)[1].split(
		"<template v-else-if=\"activeSection === 'procedures'\">", 1
	)[0]


def get_assessment_sources() -> str:
	return get_assessment_block() + "".join(path.read_text() for path in ASSESSMENT_DIR.glob("*.vue"))
```

and inside `TestAssessmentRestyle`:

```python
	def test_every_hook_survives(self):
		sources = get_assessment_sources() + (CHART_DIR / "DermaChart.vue").read_text()
		for hook in ASSESSMENT_HOOKS:
			self.assertIn(f'data-test="{hook}"', sources)

	def test_edit_save_and_print_live_in_the_card_header(self):
		template, script, style = get_component_parts(ASSESSMENT_DIR / "AssessmentPanel.vue")
		teleport = get_element(template, '<Teleport defer to="#chart-section-actions"')
		self.assertIn('<template v-if="hasEncounter && !loading">', teleport)
		for hook in ("assessment-print", "assessment-edit", "assessment-save", "assessment-status"):
			self.assertIn(f'data-test="{hook}"', teleport)
		self.assertNotIn("assessment-footer", template + style)
		self.assertNotIn("Read-only. Choose Edit to continue documenting.", script)
		self.assertNotIn('__("No changes")', script)
		self.assertIn('__("Unsaved changes")', script)

	def test_advice_print_choice_sits_with_the_advice(self):
		template, _, _ = get_component_parts(ASSESSMENT_DIR / "AssessmentPanel.vue")
		advice = get_element(template, '<section v-if="hasAdvice" class="advice-block"')
		self.assertIn('data-test="assessment-advice-toggle"', advice)
		self.assertIn('data-test="assessment-advice-language"', advice)

	def test_the_assessment_panel_is_not_a_card_in_a_card(self):
		_, _, style = get_component_parts(ASSESSMENT_DIR / "AssessmentPanel.vue")
		self.assertNotRegex(get_rule_body(style, ".assessment-panel {"), r"border:|background:")
```

(`get_rule_body(css, selector_start)` already exists in this file.)

- [ ] **Step 2: Run theme tests; expect the three new layout tests to FAIL** (`test_every_hook_survives` passes today and must keep passing).

- [ ] **Step 3: Implement the template.** In `AssessmentPanel.vue`:

1. As the first child of `<section class="assessment-panel">`:

```vue
    <Teleport defer to="#chart-section-actions">
      <template v-if="hasEncounter && !loading">
        <span
          v-if="headerStatus"
          class="chart-pill"
          :data-tone="saving ? null : 'caution'"
          data-test="assessment-status"
        >{{ headerStatus }}</span>
        <button
          v-if="canPrint"
          type="button"
          class="ghost small"
          data-test="assessment-print"
          :title="__('Print this note on the clinic letterhead')"
          @click="printNote"
        >
          {{ __("Print") }}
        </button>
        <button
          v-if="!editMode && canEdit"
          type="button"
          class="primary small"
          data-test="assessment-edit"
          @click="$emit('request-edit')"
        >
          {{ __("Edit") }}
        </button>
        <button
          v-else-if="editMode"
          type="button"
          class="primary small"
          data-test="assessment-save"
          :disabled="saving || !isDirty"
          @click="submitDraft"
        >
          {{ saving ? __("Saving...") : __("Save") }}
        </button>
      </template>
    </Teleport>
```

2. `<p v-if="submittedNote" class="status-note">` becomes `<p v-if="submittedNote" class="chart-pill status-note">`.

3. Replace the `<details ... assessment-advice>` block **and** the whole `<footer class="assessment-footer">` with:

```vue
      <section v-if="hasAdvice" class="advice-block" data-test="assessment-advice">
        <header class="advice-head">
          <strong class="chart-label">{{ __("Patient advice") }}</strong>
          <label v-if="canPrint" class="advice-toggle" data-test="assessment-advice-toggle" :title="__('Optional: add the patient advice block to the printed note')">
            <input type="checkbox" :checked="includeAdvice" :disabled="togglingAdvice" @change="toggleAdvice($event.target.checked)" />
            {{ __("Include in print") }}
          </label>
          <select
            v-if="canPrint && includeAdvice"
            class="advice-language"
            data-test="assessment-advice-language"
            :value="adviceLanguage"
            :disabled="togglingAdvice"
            :title="__('Which advice prints: Auto follows the language the report is written in')"
            @change="setAdviceLanguage($event.target.value)"
          >
            <option value="Auto">{{ __("Auto (report language)") }}</option>
            <option value="English">{{ __("English") }}</option>
            <option value="Arabic">{{ __("Arabic") }}</option>
            <option value="Both">{{ __("Both") }}</option>
          </select>
        </header>
        <details>
          <summary>{{ __("Show advice") }}</summary>
          <pre v-if="patientAdvice">{{ patientAdvice }}</pre>
          <pre v-if="patientAdviceAr" dir="rtl">{{ patientAdviceAr }}</pre>
          <small>{{ __("Edit the text on the Patient Encounter form.") }}</small>
        </details>
      </section>
```

- [ ] **Step 4: Implement the script.** Delete `footerStatus`. Add:

```js
const headerStatus = computed(() => {
  if (props.saving) return __("Saving...")
  return props.editMode && isDirty.value ? __("Unsaved changes") : ""
})
```

- [ ] **Step 5: Implement the style.** Replace `.assessment-panel`, `.status-note`, `.assessment-footer`, `.footer-status` and `.advice-block` rules with:

```css
.assessment-panel {
  display: grid;
  gap: 14px;
}

.status-note {
  justify-self: start;
  white-space: normal;
  margin: 0;
}

.advice-block {
  display: grid;
  gap: 8px;
  font-size: 12px;
}

.advice-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 14px;
}

.advice-block summary {
  cursor: pointer;
  color: var(--chart-text-soft);
}
```

Keep `.error-text`, `.empty-state`, `.advice-toggle`, `.advice-language`, `.advice-block pre`, `.advice-block small`. Delete `.advice-block`'s old border/background version.

- [ ] **Step 6: Run theme tests; expect all to pass.**

- [ ] **Step 7: Commit.**

```bash
git add do_derma/public/js/chart/components/assessment/AssessmentPanel.vue do_derma/tests/test_chart_theme.py
git commit -m "feat(assessment): Edit, Save and Print move to the card header; status only while editing

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Other-format pills switch through the confirm prompt

**Files:**
- Modify: `do_derma/public/js/chart/components/assessment/AssessmentPanel.vue`
- Modify: `do_derma/public/js/chart/DermaChart.vue:108-135` (`<AssessmentPanel ...>` props/events)
- Test: `do_derma/tests/test_chart_theme.py`

**Interfaces:**
- Consumes: `requestAssessmentModeChange(target)` and `assessmentModeLocked` in `DermaChart.vue` (existing).
- Produces: `AssessmentPanel` prop `modeLocked: Boolean`, event `switch-mode(mode: string)`.

- [ ] **Step 1: Write the failing test** in `TestAssessmentRestyle`:

```python
	def test_other_format_pills_switch_through_the_confirm_prompt(self):
		template, script, _ = get_component_parts(ASSESSMENT_DIR / "AssessmentPanel.vue")
		row = get_element(template, '<div v-if="!editMode && otherModesWithContent.length" class="other-formats"')
		self.assertIn('data-test="assessment-other-format"', row)
		self.assertIn('<span v-if="isModeInert(otherMode)" class="chart-pill" data-tone="caution"', row)
		self.assertIn("@click=\"emit('switch-mode', otherMode)\"", row)
		self.assertIn("props.modeLocked || !props.availableModes.includes(mode)", script)
		self.assertIn('"switch-mode"', script)
		self.assertNotIn("otherFormatNote", script)
		block = get_assessment_block()
		self.assertIn(':mode-locked="assessmentModeLocked"', block)
		self.assertIn('@switch-mode="requestAssessmentModeChange"', block)
```

- [ ] **Step 2: Run theme tests; expect it to FAIL.**

- [ ] **Step 3: Implement.** In `AssessmentPanel.vue` replace the `<p v-if="!editMode && inactiveModeHasContent" ...>` paragraph with:

```vue
      <div v-if="!editMode && otherModesWithContent.length" class="other-formats" data-test="assessment-other-format">
        <template v-for="otherMode in otherModesWithContent" :key="otherMode">
          <span v-if="isModeInert(otherMode)" class="chart-pill" data-tone="caution" :data-test="`assessment-other-format-${otherMode.toLowerCase()}`">
            {{ otherFormatLabel(otherMode) }}
          </span>
          <button
            v-else
            type="button"
            class="chart-pill"
            data-tone="caution"
            :data-test="`assessment-other-format-${otherMode.toLowerCase()}`"
            :title="__('Switch this visit to {0}').replace('{0}', __(MODE_LABELS[otherMode]))"
            @click="emit('switch-mode', otherMode)"
          >
            {{ otherFormatLabel(otherMode) }}
          </button>
        </template>
      </div>
```

Script changes:

```js
const SHORT_LABELS = { SOAP: "SOAP", HP: "H&P", Structured: "Structured" }
```

Add the prop `modeLocked: { type: Boolean, default: false },` and change the emits to
`defineEmits(["request-edit", "save", "advice-toggled", "advice-language", "switch-mode"])`.
Delete `inactiveModeHasContent` and `otherFormatNote`; add:

```js
function isModeInert(mode) {
  return props.modeLocked || !props.availableModes.includes(mode)
}

function otherFormatLabel(mode) {
  return __("{0} has content").replace("{0}", __(SHORT_LABELS[mode] || mode))
}
```

Style:

```css
.other-formats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
```

In `DermaChart.vue` on `<AssessmentPanel`, add `:mode-locked="assessmentModeLocked"` and `@switch-mode="requestAssessmentModeChange"`.

- [ ] **Step 4: Run theme tests; expect all to pass.**

- [ ] **Step 5: Commit.**

```bash
git add do_derma/public/js/chart/components/assessment/AssessmentPanel.vue do_derma/public/js/chart/DermaChart.vue do_derma/tests/test_chart_theme.py
git commit -m "feat(assessment): other formats with content are pills that offer the switch

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Note fields read as labels and text

**Files:**
- Modify: `do_derma/public/js/chart/components/assessment/SoapNoteFields.vue` (template `soap-label`, style)
- Modify: `do_derma/public/js/chart/components/assessment/StructuredAssessmentFields.vue` (template `fields-section-title`, style)
- Test: `do_derma/tests/test_chart_theme.py`

- [ ] **Step 1: Write the failing test** in `TestAssessmentRestyle`:

```python
	def test_note_fields_use_labels_plain_text_and_chart_inputs(self):
		soap, _, soap_style = get_component_parts(ASSESSMENT_DIR / "SoapNoteFields.vue")
		self.assertIn('class="soap-label chart-label"', soap)
		self.assertNotRegex(get_rule_body(soap_style, ".soap-readonly {"), r"background|border")
		self.assertIn("background: var(--chart-surface);", get_rule_body(soap_style, ".soap-input {"))

		structured, _, structured_style = get_component_parts(ASSESSMENT_DIR / "StructuredAssessmentFields.vue")
		self.assertIn('class="fields-section-title chart-label"', structured)
		self.assertIn("text-transform: uppercase;", get_rule_body(structured_style, ".field-control-host:deep(.control-label) {"))
		self.assertIn("background: transparent;", get_rule_body(structured_style, ".field-control-host:deep(.like-disabled-input) {"))
		self.assertNotIn("--control-bg", soap_style + structured_style)
```

- [ ] **Step 2: Run theme tests; expect it to FAIL.**

- [ ] **Step 3: Implement `SoapNoteFields.vue`.** Template: `<span class="soap-label chart-label">`. Style: delete the `.soap-label` rule and `.soap-input:focus` rule (the shared `:focus-visible` rule draws the ring), and set:

```css
.soap-input {
  width: 100%;
  resize: vertical;
  padding: 8px 10px;
  font: inherit;
  color: var(--chart-text);
  background: var(--chart-surface);
  border: 1px solid var(--chart-border-strong);
  border-radius: 8px;
}

.soap-readonly {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--chart-text);
  white-space: pre-wrap;
}
```

- [ ] **Step 4: Implement `StructuredAssessmentFields.vue`.** Template: `<h4 v-if="section.label" class="fields-section-title chart-label">`. Style: reduce `.fields-section-title` to `{ margin: 0; }`, and replace the control rules:

```css
.field-control-host:deep(.control-label) {
  margin-bottom: 6px;
  color: var(--chart-muted);
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.field-control-host:deep(textarea.form-control),
.field-control-host:deep(input.form-control),
.field-control-host:deep(.control-input .form-control),
.field-control-host:deep(.table-multiselect.form-control) {
  background: var(--chart-surface);
  border: 1px solid var(--chart-border-strong);
  border-radius: 8px;
}

.field-control-host:deep(.like-disabled-input) {
  min-height: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--chart-text);
  font-size: 13px;
  line-height: 1.5;
}
```

(The `.control-label` values copy `.chart-label`'s, because desk renders that label and the chart cannot add a class to it.)

- [ ] **Step 5: Run theme tests; expect all to pass.**

- [ ] **Step 6: Commit.**

```bash
git add do_derma/public/js/chart/components/assessment/SoapNoteFields.vue do_derma/public/js/chart/components/assessment/StructuredAssessmentFields.vue do_derma/tests/test_chart_theme.py
git commit -m "feat(assessment): note fields read as labels and plain text; edits use chart inputs

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Dictation result as pills and toggles

**Files:**
- Modify: `do_derma/public/js/chart/components/assessment/VoiceScribe.vue` (template lines 3-12 and 60-85, script)
- Modify: `do_derma/public/js/chart/derma_chart.bundle.css:3399-3490` (voice rules)
- Test: `do_derma/tests/test_chart_theme.py`

- [ ] **Step 1: Write the failing test** in `TestAssessmentRestyle`:

```python
	def test_dictation_result_is_pills_and_toggles(self):
		template, script, _ = get_component_parts(ASSESSMENT_DIR / "VoiceScribe.vue")
		result = get_element(template, '<div v-if="summary && [\'idle\', \'ready\', \'failed\'].includes(state)" class="voice-result"')
		self.assertNotIn("<details", result)
		self.assertNotIn("<code", result)
		self.assertIn('data-test="voice-icd10"', result)
		self.assertIn(":aria-expanded=", result)
		self.assertRegex(template, r'class="ghost small"\s+data-test="voice-start"')
		self.assertRegex(script, r'watch\(summary, \(\) => \{\s+openExtra\.value = ""')
		css = CHART_CSS.read_text()
		self.assertIn("white-space: normal;", get_rule_body(css, ".voice-result-head .chart-pill {"))
		self.assertNotIn(".voice-result-head code", css)
		self.assertNotRegex(get_rule_body(css, ".voice-scribe {"), r"border:|background:")
```

- [ ] **Step 2: Run theme tests; expect it to FAIL.**

- [ ] **Step 3: Implement the template.** The start button's class becomes `class="ghost small"` (keep `data-test="voice-start"` on the next line). Replace the `voice-result` block with:

```vue
    <div v-if="summary && ['idle', 'ready', 'failed'].includes(state)" class="voice-result" data-test="voice-result">
      <div class="voice-result-head">
        <span v-if="summary.diagnosis" class="chart-pill" data-test="voice-diagnosis">{{ summary.diagnosis }}</span>
        <span v-else class="voice-hint">{{ __("No diagnosis suggested") }}</span>
        <span v-if="summary.icd10" class="chart-pill" data-test="voice-icd10">{{ summary.icd10 }}</span>
        <button
          v-if="summary.followup_en || summary.followup_ar"
          type="button"
          class="ghost small"
          data-test="voice-followup-toggle"
          :aria-expanded="openExtra === 'followup' ? 'true' : 'false'"
          @click="toggleExtra('followup')"
        >
          {{ __("WhatsApp follow-up") }}
        </button>
        <button
          v-if="summary.soap_ar"
          type="button"
          class="ghost small"
          data-test="voice-arabic-toggle"
          :aria-expanded="openExtra === 'arabic' ? 'true' : 'false'"
          @click="toggleExtra('arabic')"
        >
          {{ __("Arabic note") }}
        </button>
      </div>
      <div v-if="openExtra === 'followup'" class="voice-followups">
        <div v-if="summary.followup_en">
          <pre>{{ summary.followup_en }}</pre>
          <button type="button" class="ghost small" @click="copy(summary.followup_en)">{{ __("Copy English") }}</button>
        </div>
        <div v-if="summary.followup_ar" dir="rtl">
          <pre>{{ summary.followup_ar }}</pre>
          <button type="button" class="ghost small" @click="copy(summary.followup_ar)">{{ __("نسخ العربية") }}</button>
        </div>
      </div>
      <pre v-if="openExtra === 'arabic'" dir="rtl">{{ summary.soap_ar }}</pre>
    </div>
```

- [ ] **Step 4: Implement the script.** Add `watch` to the `vue` import, and after `const summary = computed(...)`:

```js
const openExtra = ref("")
watch(summary, () => {
  openExtra.value = ""
})

function toggleExtra(name) {
  openExtra.value = openExtra.value === name ? "" : name
}
```

- [ ] **Step 5: Implement the CSS** in `derma_chart.bundle.css`. Change `.voice-scribe` to:

```css
.voice-scribe {
  display: grid;
  gap: 10px;
}
```

Delete `.voice-result-head code { ... }` and `.voice-result details summary { ... }`. Add after `.voice-result-head`:

```css
.voice-result-head .chart-pill {
  white-space: normal;
}
```

- [ ] **Step 6: Run theme tests; expect all to pass.**

- [ ] **Step 7: Commit.**

```bash
git add do_derma/public/js/chart/components/assessment/VoiceScribe.vue do_derma/public/js/chart/derma_chart.bundle.css do_derma/tests/test_chart_theme.py
git commit -m "feat(voice): dictation result shows pills and toggles; Dictate is a ghost button

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Flat sections and the Drawings button

**Files:**
- Modify: `do_derma/public/js/chart/DermaChart.vue:136-160` (Drawings `<section>` and its button)
- Modify: `do_derma/public/js/chart/derma_chart.bundle.css` (`.clinical-soap-stack` rules near line 534; delete `.encounter-annotation-history` at line 856)
- Test: `do_derma/tests/test_chart_theme.py`

- [ ] **Step 1: Write the failing tests** in `TestAssessmentRestyle`:

```python
	def test_one_filled_button_in_the_tab(self):
		block = get_assessment_block()
		self.assertNotIn('class="primary', block)
		for name in ("VoiceScribe.vue", "PreviousVisitsPanel.vue", "SoapNoteFields.vue", "StructuredAssessmentFields.vue"):
			self.assertNotIn('class="primary', (ASSESSMENT_DIR / name).read_text(), name)
		panel, _, _ = get_component_parts(ASSESSMENT_DIR / "AssessmentPanel.vue")
		primaries = re.findall(r'class="primary[^"]*"\s+data-test="([\w-]+)"', panel)
		self.assertCountEqual(primaries, ["assessment-start", "assessment-edit", "assessment-save"])

	def test_sections_sit_flat_with_rules_between(self):
		block = get_assessment_block()
		self.assertNotIn("chart-inner-card", block)
		self.assertIn('<i v-else class="fa-regular fa-pen-to-square" aria-hidden="true"></i>', block)
		css = CHART_CSS.read_text()
		self.assertIn("border-top: 1px solid var(--chart-border);", get_rule_body(css, ".clinical-soap-stack > * + * {"))
		self.assertNotIn(".encounter-annotation-history {", css)
```

The `primaries` regex needs `data-test` directly after `class`; Start Assessment, Edit and Save all have that order (Task 4 keeps it).

- [ ] **Step 2: Run theme tests; expect both to FAIL.**

- [ ] **Step 3: Implement `DermaChart.vue`.** The Drawings section becomes `<section class="chart-annotation-history encounter-annotation-history">`, without `chart-inner-card`. Its button:

```vue
                    <button
                      type="button"
                      class="ghost small"
                      data-test="annotate-consultation"
                      :disabled="annotationStudioBusy || isEncounterLocked"
                      :title="isEncounterLocked ? __('Reopen the encounter to draw.') : ''"
                      @click="openAnnotationStudio({ annotation: null })"
                    >
                      <span v-if="annotationStudioBusy" class="chart-spinner" aria-hidden="true"></span>
                      <i v-else class="fa-regular fa-pen-to-square" aria-hidden="true"></i>
                      {{ annotationStudioBusy ? __("Opening...") : __("Annotate Consultation") }}
                    </button>
```

- [ ] **Step 4: Implement the CSS.** In `derma_chart.bundle.css`, after the `.clinical-notes-grid, .clinical-soap-stack { min-width: 0; }` rule:

```css
.clinical-soap-stack > * + * {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--chart-border);
}

.clinical-soap-stack .chart-annotation-history > header {
  padding: 0 0 8px;
  border-bottom: 0;
}
```

Delete the `.encounter-annotation-history { margin-top: 12px; }` rule. `.clinical-soap-stack .chart-annotation-history > header` (0,2,1) outranks the later `.chart-annotation-history > header { padding: 10px 12px }` (0,1,1), so order does not matter. Run `test_chart_theme`'s structure tests (`TestChartStylesheetStructure`), which flag shadowed declarations.

- [ ] **Step 5: Run theme tests; expect all to pass.**

- [ ] **Step 6: Commit.**

```bash
git add do_derma/public/js/chart/DermaChart.vue do_derma/public/js/chart/derma_chart.bundle.css do_derma/tests/test_chart_theme.py
git commit -m "feat(assessment): sections sit flat on the card; Annotate Consultation is a ghost button

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Build, browser verification, suite, lint

**Files:** none planned; fixes found here get their own commit with a test where one can pin it.

- [ ] **Step 1: Build** `bench build --app do_derma`, then restart the 8002 server.

- [ ] **Step 2: Layout.** On HLC-ENC-2026-18379 at 1280, 1600 and 1920, in light and then dark (desk theme toggle), screenshot each to `$CLAUDE_JOB_DIR/tmp`. Check:
  - the header reads format switch · Print · Edit;
  - no nested card borders inside the section card;
  - one filled button;
  - no horizontal overflow at 1280;
  - no light patches under dark.

- [ ] **Step 3: Read and edit in all three formats.** Switch formats with the toggle. For each format:
  - **Read mode:** labels are uppercase and values are plain text.
  - **Edit:** inputs are white with a border.
  - **Status pill:** typing shows "Unsaved changes" and Save saves; "Saving..." shows briefly.

  Revert every edit (save the original text back).

- [ ] **Step 4: Other-format pills.** In read mode, click a `… has content` pill:
  - the confirm prompt appears;
  - Cancel keeps the format;
  - OK switches and opens edit mode.

  Switch back afterwards.

- [ ] **Step 5: Dictation result.** With the saved summary:
  - the diagnosis and ICD pills wrap rather than overflow at 1280;
  - the WhatsApp and Arabic toggles open one block at a time, and `aria-expanded` follows.

- [ ] **Step 6: Advice.** Tick Include in print, change the language, then revert both. Confirm in the DB with `frappe.db.get_value("Patient Encounter", "HLC-ENC-2026-18379", ["custom_derma_print_patient_advice", "custom_derma_patient_advice_language"])`.

- [ ] **Step 7: Previous visits.**
  - Real diagnoses show instead of `row(s)`.
  - Each visit has a format pill and procedure pills.
  - View Summary opens.
  - Load more, then Collapse, still work.

- [ ] **Step 8: Submitted encounter.** Pick a submitted encounter from `frappe.get_all("Patient Encounter", {"docstatus": 1}, limit=5)` and check:
  - no Edit unless an Allow-on-Submit field exists;
  - other-format pills are `<span>`s;
  - the submitted note shows as a neutral pill.

- [ ] **Step 9: Suite.** Run `bench --site dermaone.localhost run-tests --app do_derma 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"`. Compare the failing names with the known baseline in the test-quirks memory; there must be no new names.

- [ ] **Step 10: Lint.** Run `pipx run ruff check` and `pipx run ruff format --check` on `do_derma/tests/test_chart_theme.py do_derma/tests/test_previous_visits.py do_derma/tests/test_assessment.py do_derma/assessment.py do_derma/previous_visits.py`. Fix anything they report and commit it as `style(tests): format the assessment restyle tests`.
