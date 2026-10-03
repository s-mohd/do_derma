# Prescription tab restyle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Prescription tab's embedded desk Table grid with a native Vue table in the chart vocabulary, keeping rows always editable and the server untouched.

**Architecture:** `components/prescription/PrescriptionPanel.vue` owns the draft rows, the header (count, status, Add, Save), ordered rows, validation and the payload. `components/prescription/PrescriptionRow.vue` renders one editable line plus its optional comment line, and mounts a desk `Link` control in whichever cell is being picked (the `ConsumablesEditor.vue` pattern). `DermaChart.vue` only changes its import path.

**Tech Stack:** Vue 3 SFC (`<script setup>`), Frappe desk controls (`frappe.ui.form.make_control`), Python `unittest` source tests and `IntegrationTestCase` server tests run through `bench run-tests`.

**Spec:** `.planning/specs/2026-10-03-derma-prescription-restyle.md`

## Global Constraints

- Branch `feat/derma-prescription-restyle`; commit after every task; messages end with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- No change to `do_derma/api.py` or any server module.
- Component styles use `--chart-*` tokens only; no hex colours (`TestChartComponentColours`).
- Every `<Teleport>` is `<Teleport defer to="#chart-section-actions">` (`test_teleports_target_the_section_card`).
- Save is the tab's only `primary` button; Add medication is `ghost small`.
- No `overflow` wrapper around the table: it would clip the Link controls' dropdowns.
- Keep comments short; no file-top comments; no abbreviations in names (repo `CLAUDE.md`).
- Run a single test with `--test <bare_method_name>`; a class name silently runs nothing.
- Judge the full suite by diffing failures against the known `main` set, not by green.
- Lint changed Python files only with `pipx run ruff check <files>` and `pipx run ruff format <files>`.

## Review Focus

1. Picking a second medication before the first lookup returns: the slower first response must not overwrite the second's defaults. Pinned by `test_a_stale_medication_lookup_is_ignored` (Task 3).
2. Pressing Esc inside an open picker: the picker closes, focus lands on that cell's button, and desk's global Esc handler never sees the key. Pinned by `test_pickers_keep_escape_from_desk` (Task 2) and the browser check (Task 4).
3. Saving with a half-filled row (medication but no duration): nothing is sent and the cell is flagged; an all-blank row is silently dropped. Pinned by `test_save_names_the_first_gap_and_drops_blank_rows` (Task 3).
4. Re-saving a loaded row: fields the table never shows (`interval`, `interval_uom`, …) survive. Pinned by `test_a_resent_row_keeps_fields_the_tab_does_not_show` (Task 1) and `test_save_keeps_fields_the_table_does_not_show` (Task 3).
5. Double-clicking Save, or saving with nothing changed: the button is disabled while saving and while clean. Pinned by `test_save_waits_for_a_change` (Task 3).

---

## File structure

| File | Responsibility |
|---|---|
| Create `do_derma/public/js/chart/components/prescription/PrescriptionRow.vue` | One draft line: link cells, repeats input, comment toggle and line, delete, comment hover preview, picker mounting |
| Create `do_derma/public/js/chart/components/prescription/PrescriptionPanel.vue` | Draft state, header teleport, table shell, ordered rows, empty states, medication lookup, validation, payload |
| Delete `do_derma/public/js/chart/components/PrescriptionPanel.vue` | Replaced |
| Modify `do_derma/public/js/chart/DermaChart.vue:581` | Import path |
| Modify `do_derma/tests/test_chart_theme.py` (append) | `TestPrescriptionRow`, `TestPrescriptionPanelRestyle` |
| Modify `do_derma/tests/test_encounter_tabs.py` (`TestDermaPrescriptions`) | Resent-row regression |

---

### Task 1: Server guard for fields the table does not show

**Files:**
- Modify: `do_derma/tests/test_encounter_tabs.py` (inside `class TestDermaPrescriptions`, after `test_rows_replace_the_previous_set`)

**Interfaces:**
- Consumes: `api.set_derma_prescriptions(payload, encounter)`, `PrescriptionHelpers._row(**extra)`
- Produces: nothing new; pins the server half of "spread the original row".

This guards existing behaviour, so it is expected to pass on first run. If it fails, stop: the client's spread rule would not be enough and the spec needs revisiting.

- [ ] **Step 1: Add the test**

```python
	def test_a_resent_row_keeps_fields_the_tab_does_not_show(self):
		"""The tab resends each loaded row whole, so hidden fields survive a comment edit."""
		encounter = self._make_encounter(self._make_patient())
		saved = api.set_derma_prescriptions(
			payload=json.dumps([self._row(interval=2, interval_uom="Day")]), encounter=encounter.name
		)
		resent = {**saved["drug_prescription"][0], "comment": "After meals"}
		saved = api.set_derma_prescriptions(payload=json.dumps([resent], default=str), encounter=encounter.name)
		row = saved["drug_prescription"][0]
		self.assertEqual((row["interval"], row["interval_uom"], row["comment"]), (2, "Day", "After meals"))
```

- [ ] **Step 2: Run it**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_encounter_tabs --test test_a_resent_row_keeps_fields_the_tab_does_not_show`
Expected: `Ran 1 test` … `OK`

- [ ] **Step 3: Lint and commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
pipx run ruff check do_derma/tests/test_encounter_tabs.py && pipx run ruff format do_derma/tests/test_encounter_tabs.py
git add do_derma/tests/test_encounter_tabs.py
git commit -m "test(prescriptions): a resent row keeps the fields the tab does not show

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `PrescriptionRow.vue`

**Files:**
- Create: `do_derma/public/js/chart/components/prescription/PrescriptionRow.vue`
- Modify: `do_derma/tests/test_chart_theme.py` (append at end of file)

**Interfaces:**
- Consumes: global `.chart-pill`, `.chart-label`, `.chart-spinner` (in `derma_chart.bundle.css`); `frappe.ui.form.make_control`.
- Produces: component `PrescriptionRow` with
  - props: `row` (`{ key, original, values, linkedItems: string[], lookup: number, filling: boolean }`, `values` keys = `medication, drug_code, dosage, period, dosage_form, number_of_repeats_allowed, comment`), `readOnly: Boolean`, `openField: String` (`""` or one of `medication | drug_code | dosage | period | dosage_form`), `commentOpen: Boolean`, `missing: string[]`
  - emits: `update(field, value)`, `open-picker(field)`, `close-picker()`, `toggle-comment()`, `remove()`
  - renders two root `<tr>`s (line, optional comment line); cells assume a 6-column table.

- [ ] **Step 1: Write the failing tests** — append to `do_derma/tests/test_chart_theme.py`:

```python
PRESCRIPTION_DIR = CHART_DIR / "components" / "prescription"
PRESCRIPTION_PANEL = PRESCRIPTION_DIR / "PrescriptionPanel.vue"
PRESCRIPTION_ROW = PRESCRIPTION_DIR / "PrescriptionRow.vue"


class TestPrescriptionRow(TestCase):
	"""One editable prescription line in the chart vocabulary (spec 2026-10-03)."""

	def test_link_cells_mount_desk_link_controls(self):
		_, script, _ = get_component_parts(PRESCRIPTION_ROW)
		self.assertIn("frappe.ui.form.make_control", script)
		self.assertIn('fieldtype: "Link"', script)
		self.assertIn("only_select: 1", script)
		self.assertNotIn('"Table"', script)

	def test_pickers_keep_escape_from_desk(self):
		template, _, _ = get_component_parts(PRESCRIPTION_ROW)
		hosts = re.findall(r'<div[^>]*class="picker-host"[^>]*>', template)
		self.assertEqual(len(hosts), 3)
		for host in hosts:
			self.assertIn("@keydown.escape.stop", host)

	def test_drug_code_sits_under_the_medication(self):
		template, _, _ = get_component_parts(PRESCRIPTION_ROW)
		medication = get_element(template, '<td class="medication-cell"')
		self.assertIn('data-test="prescription-choose-item"', medication)
		self.assertIn("row.linkedItems.length > 1", medication)
		self.assertIn('class="chart-spinner"', medication)

	def test_comment_and_delete_live_in_the_actions_cluster(self):
		template, _, _ = get_component_parts(PRESCRIPTION_ROW)
		actions = get_element(template, '<td class="row-actions"')
		for hook in ("prescription-comment", "prescription-delete"):
			self.assertIn(f'data-test="{hook}"', actions)
		self.assertIn('class="comment-preview"', actions)
		self.assertIn('data-test="prescription-comment-input"', template)

	def test_delete_turns_red_only_on_hover(self):
		_, _, style = get_component_parts(PRESCRIPTION_ROW)
		self.assertNotRegex(style, r"\.icon-btn\.danger \{")
		self.assertRegex(
			style, r"\.icon-btn\.danger:hover:not\(:disabled\)[^{]*\{[^}]*var\(--chart-danger-text\)"
		)
```

- [ ] **Step 2: Run to see them fail**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_chart_theme --test test_link_cells_mount_desk_link_controls`
Expected: ERROR, `FileNotFoundError` for `PrescriptionRow.vue`.

- [ ] **Step 3: Create the component**

`do_derma/public/js/chart/components/prescription/PrescriptionRow.vue`:

```vue
<template>
  <tr ref="rowElement" class="prescription-row" data-test="prescription-row">
    <td class="medication-cell">
      <div
        v-if="openField === 'medication'"
        :ref="setPickerHost"
        class="picker-host"
        @keydown.escape.stop="closePicker('medication')"
      ></div>
      <button
        v-else
        type="button"
        class="cell-input medication-name"
        :class="{ 'is-empty': !row.values.medication, 'is-missing': missing.includes('medication') }"
        data-field="medication"
        data-test="prescription-medication"
        :disabled="readOnly"
        @click="emit('open-picker', 'medication')"
      >
        {{ row.values.medication || __("Choose medication") }}
      </button>
      <div
        v-if="openField === 'drug_code'"
        :ref="setPickerHost"
        class="picker-host"
        @keydown.escape.stop="closePicker('drug_code')"
      ></div>
      <button
        v-else-if="row.linkedItems.length > 1 && !readOnly"
        type="button"
        class="drug-code-link"
        data-field="drug_code"
        data-test="prescription-choose-item"
        @click="emit('open-picker', 'drug_code')"
      >
        {{ row.values.drug_code || __("Choose item") }}
      </button>
      <small v-else-if="row.values.drug_code" class="drug-code">{{ row.values.drug_code }}</small>
      <span v-if="row.filling" class="filling" data-test="prescription-filling">
        <span class="chart-spinner" aria-hidden="true"></span>
        {{ __("Filling in dosage and duration...") }}
      </span>
    </td>
    <td v-for="column in LINK_COLUMNS" :key="column.field">
      <div
        v-if="openField === column.field"
        :ref="setPickerHost"
        class="picker-host"
        @keydown.escape.stop="closePicker(column.field)"
      ></div>
      <button
        v-else
        type="button"
        class="cell-input"
        :class="{ 'is-empty': !row.values[column.field], 'is-missing': missing.includes(column.field) }"
        :data-field="column.field"
        :data-test="`prescription-${column.field}`"
        :disabled="readOnly"
        @click="emit('open-picker', column.field)"
      >
        {{ row.values[column.field] || (readOnly ? "—" : column.placeholder) }}
      </button>
    </td>
    <td>
      <input
        type="number"
        min="0"
        step="1"
        class="cell-input repeats-input"
        data-test="prescription-repeats"
        :value="row.values.number_of_repeats_allowed"
        :disabled="readOnly"
        :aria-label="__('Repeats')"
        @input="emit('update', 'number_of_repeats_allowed', $event.target.value)"
      />
    </td>
    <td class="row-actions">
      <button
        v-if="!readOnly || row.values.comment"
        type="button"
        class="icon-btn"
        data-test="prescription-comment"
        :aria-label="__('Comment')"
        :aria-expanded="commentOpen ? 'true' : 'false'"
        @click="hidePreview(); emit('toggle-comment')"
        @mouseenter="showPreview"
        @focus="showPreview"
        @mouseleave="hidePreview"
        @blur="hidePreview"
      >
        <i class="fa-regular fa-comment"></i>
        <span v-if="row.values.comment" class="note-dot"></span>
      </button>
      <button
        v-if="!readOnly"
        type="button"
        class="icon-btn danger"
        data-test="prescription-delete"
        :title="__('Remove medication')"
        :aria-label="__('Remove medication')"
        @click="emit('remove')"
      >
        <i class="fa-regular fa-trash-can"></i>
      </button>
      <div v-if="preview" class="comment-preview" role="tooltip" :style="previewStyle">
        <span class="chart-label">{{ __("Comment") }}</span>
        <p>{{ preview.text }}</p>
      </div>
    </td>
  </tr>
  <tr v-if="commentOpen" class="comment-row">
    <td colspan="6">
      <textarea
        class="comment-input"
        rows="2"
        data-test="prescription-comment-input"
        :value="row.values.comment"
        :disabled="readOnly"
        :placeholder="__('Instructions for the patient or pharmacist')"
        @input="emit('update', 'comment', $event.target.value)"
      ></textarea>
    </td>
  </tr>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue"

const __ = window.__ || ((text) => text)

const LINK_OPTIONS = {
  medication: "Medication",
  drug_code: "Item",
  dosage: "Prescription Dosage",
  period: "Prescription Duration",
  dosage_form: "Dosage Form",
}
const LINK_COLUMNS = [
  { field: "dosage", placeholder: __("Dosage") },
  { field: "period", placeholder: __("Duration") },
  { field: "dosage_form", placeholder: __("Form") },
]
const PREVIEW_DELAY_MS = 250
const PREVIEW_GAP_PX = 8

const props = defineProps({
  row: { type: Object, required: true },
  readOnly: { type: Boolean, default: false },
  openField: { type: String, default: "" },
  commentOpen: { type: Boolean, default: false },
  missing: { type: Array, default: () => [] },
})

const emit = defineEmits(["update", "open-picker", "close-picker", "toggle-comment", "remove"])

const rowElement = ref(null)
const preview = ref(null)
let pickerHost = null
let previewTimer = null

watch(
  () => props.openField,
  async (field) => {
    if (!field) return
    await nextTick()
    mountPicker(field)
  },
  { immediate: true }
)

onBeforeUnmount(hidePreview)

function setPickerHost(element) {
  pickerHost = element || null
}

function mountPicker(field) {
  if (!pickerHost || !window.frappe?.ui?.form?.make_control) return
  pickerHost.innerHTML = ""
  const control = frappe.ui.form.make_control({
    parent: pickerHost,
    df: {
      fieldtype: "Link",
      fieldname: field,
      options: LINK_OPTIONS[field],
      placeholder: __(LINK_OPTIONS[field]),
      only_select: 1,
      get_query: field === "drug_code" ? () => ({ filters: { name: ["in", props.row.linkedItems] } }) : undefined,
      change: () => {
        emit("update", field, control.get_value() || "")
        closePicker(field)
      },
    },
    render_input: true,
  })
  // `set_value` would fire `change` and close the picker at once.
  control.$input?.val(props.row.values[field] || "")
  control.$input?.focus()
}

function closePicker(field) {
  emit("close-picker")
  nextTick(() => rowElement.value?.querySelector(`[data-field="${field}"]`)?.focus())
}

function showPreview(event) {
  const text = props.row.values.comment
  if (!text || props.commentOpen) return
  const anchor = event.currentTarget.getBoundingClientRect()
  clearTimeout(previewTimer)
  previewTimer = setTimeout(
    () => {
      preview.value = { text, anchor }
    },
    event.type === "focus" ? 0 : PREVIEW_DELAY_MS
  )
}

function hidePreview() {
  clearTimeout(previewTimer)
  preview.value = null
}

// Opens to the left of the icon, and upward in the lower half so it never runs off the window.
const previewStyle = computed(() => {
  const anchor = preview.value?.anchor
  if (!anchor) return {}
  const style = { right: `${window.innerWidth - anchor.left + PREVIEW_GAP_PX}px` }
  if (anchor.top > window.innerHeight / 2) {
    style.bottom = `${window.innerHeight - anchor.bottom}px`
  } else {
    style.top = `${anchor.top}px`
  }
  return style
})
</script>

<style scoped>
.cell-input {
  display: block;
  width: 100%;
  min-height: 30px;
  padding: 5px 8px;
  border: 1px solid var(--chart-border);
  border-radius: 6px;
  background: var(--chart-surface);
  color: var(--chart-text);
  font-size: 13px;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
}

.cell-input:hover:not(:disabled),
.cell-input:focus-visible {
  border-color: var(--chart-accent);
  outline: none;
}

.cell-input.is-empty {
  color: var(--chart-muted);
}

.cell-input.is-missing {
  border-color: var(--chart-danger-text);
  background: var(--chart-danger-soft);
}

.cell-input:disabled {
  padding-left: 0;
  border-color: transparent;
  background: transparent;
  cursor: default;
}

.medication-name {
  font-weight: 600;
}

.repeats-input {
  cursor: text;
}

.drug-code,
.drug-code-link {
  display: block;
  margin-top: 3px;
  color: var(--chart-muted);
  font-size: 12px;
}

.drug-code-link {
  padding: 0;
  border: 0;
  background: none;
  color: var(--chart-accent-strong);
  text-decoration: underline dotted;
  cursor: pointer;
}

.filling {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  color: var(--chart-muted);
  font-size: 12px;
}

.picker-host :deep(.frappe-control) {
  margin-bottom: 0;
}

.picker-host :deep(.control-label) {
  display: none;
}

.row-actions {
  white-space: nowrap;
  text-align: right;
}

.icon-btn {
  position: relative;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--chart-muted);
  font-size: 13px;
  cursor: pointer;
}

.icon-btn:hover:not(:disabled),
.icon-btn:focus-visible {
  background: var(--chart-surface-muted);
  color: var(--chart-text);
}

.icon-btn.danger:hover:not(:disabled),
.icon-btn.danger:focus-visible {
  background: var(--chart-danger-soft);
  color: var(--chart-danger-text);
}

.note-dot {
  position: absolute;
  top: 5px;
  right: 5px;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--chart-ok);
}

/* Fixed: a positioned cell ancestor must not clip it. */
.comment-preview {
  position: fixed;
  z-index: 1050;
  width: min(320px, calc(100vw - 32px));
  padding: 10px 12px;
  border: 1px solid var(--chart-border);
  border-radius: 10px;
  background: var(--chart-surface);
  box-shadow: var(--chart-shadow);
  text-align: left;
  white-space: normal;
  pointer-events: none;
}

.comment-preview p {
  margin: 4px 0 0;
  color: var(--chart-text);
  font-size: 13px;
  line-height: 1.45;
  white-space: pre-line;
}

.comment-input {
  width: 100%;
  min-height: 56px;
  padding: 6px 8px;
  border: 1px solid var(--chart-border);
  border-radius: 6px;
  background: var(--chart-surface);
  color: var(--chart-text);
  font-size: 13px;
  resize: vertical;
}

.comment-input:focus {
  border-color: var(--chart-accent);
  outline: none;
}
</style>
```

- [ ] **Step 4: Run the row tests**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_chart_theme`
Expected: the five `TestPrescriptionRow` tests pass; `test_component_styles_carry_no_hex` and `test_teleports_target_the_section_card` still pass. (Filter with `grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"`.)

- [ ] **Step 5: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
pipx run ruff check do_derma/tests/test_chart_theme.py && pipx run ruff format do_derma/tests/test_chart_theme.py
git add do_derma/public/js/chart/components/prescription/PrescriptionRow.vue do_derma/tests/test_chart_theme.py
git commit -m "feat(prescriptions): an editable prescription line with in-cell link pickers

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `PrescriptionPanel.vue` in its folder

**Files:**
- Create: `do_derma/public/js/chart/components/prescription/PrescriptionPanel.vue`
- Delete: `do_derma/public/js/chart/components/PrescriptionPanel.vue`
- Modify: `do_derma/public/js/chart/DermaChart.vue:581`
- Modify: `do_derma/tests/test_chart_theme.py` (append after `TestPrescriptionRow`)

**Interfaces:**
- Consumes: `PrescriptionRow` (Task 2 props/emits exactly as listed there); `DermaChart.vue` props `loading, saving, error, hasSessionContext, hasEncounter, encounterName, rows, readOnly` and the `save` listener (unchanged).
- Produces: `emit("save", rows)` where `rows` is an array of `{ ...original, ...values }` objects with blank rows dropped — the same contract `savePrescriptionPanel(rows)` consumes today.

- [ ] **Step 1: Write the failing tests** — append to `do_derma/tests/test_chart_theme.py`:

```python
PRESCRIPTION_HOOKS = (
	"prescription-panel",
	"prescription-save",
	"prescription-add",
	"prescription-row",
	"prescription-ordered-row",
	"prescription-comment",
	"prescription-error",
)


class TestPrescriptionPanelRestyle(TestCase):
	"""The Prescription tab is a native table in the chart vocabulary (spec 2026-10-03)."""

	def test_the_panel_lives_in_its_folder(self):
		self.assertTrue(PRESCRIPTION_PANEL.exists())
		self.assertFalse((CHART_DIR / "components" / "PrescriptionPanel.vue").exists())
		self.assertIn(
			'import PrescriptionPanel from "./components/prescription/PrescriptionPanel.vue"',
			(CHART_DIR / "DermaChart.vue").read_text(),
		)

	def test_no_desk_grid(self):
		template, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		self.assertNotIn("make_control", script)
		self.assertNotIn('"Table"', script)
		self.assertIn('<table class="prescription-table"', template)
		self.assertIn("<PrescriptionRow", template)

	def test_add_and_save_sit_in_the_card_header(self):
		template, _, _ = get_component_parts(PRESCRIPTION_PANEL)
		header = get_element(template, '<Teleport defer to="#chart-section-actions">')
		self.assertRegex(header, r'class="ghost small"\s+data-test="prescription-add"')
		self.assertRegex(header, r'class="primary small"\s+data-test="prescription-save"')
		self.assertEqual(template.count("primary"), 1)

	def test_status_is_a_header_pill(self):
		template, script, style = get_component_parts(PRESCRIPTION_PANEL)
		for label in ("Finalized", "Saving...", "Unsaved changes"):
			self.assertIn(f'__("{label}")', script)
		self.assertNotIn("status-note", template + style)
		self.assertNotIn("Prescriptions are read-only", template + script)

	def test_ordered_rows_share_the_table(self):
		template, _, _ = get_component_parts(PRESCRIPTION_PANEL)
		ordered = get_element(template, '<tr v-for="row in orderedRows"')
		self.assertIn('data-tone="ok"', ordered)
		self.assertIn('__("Ordered")', ordered)
		self.assertNotIn('data-test="prescription-ordered"', template)

	def test_every_hook_exists(self):
		markup = PRESCRIPTION_PANEL.read_text() + PRESCRIPTION_ROW.read_text()
		for hook in PRESCRIPTION_HOOKS:
			self.assertIn(f'data-test="{hook}"', markup)

	def test_a_stale_medication_lookup_is_ignored(self):
		_, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		self.assertIn("const token = ++draft.lookup", script)
		self.assertIn("if (token !== draft.lookup) return", script)

	def test_save_keeps_fields_the_table_does_not_show(self):
		_, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		self.assertIn("({ ...draft.original, ...draft.values })", script)

	def test_save_names_the_first_gap_and_drops_blank_rows(self):
		_, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		self.assertIn('__("Row {0}: {1} is required.")', script)
		self.assertIn("drafts.value.filter((draft) => !isBlank(draft))", script)
		self.assertIn("if (validationError.value) return", script)

	def test_save_waits_for_a_change(self):
		template, _, _ = get_component_parts(PRESCRIPTION_PANEL)
		start = template.index('data-test="prescription-save"')
		save = template[start : template.index(">", start)]
		self.assertIn("saving", save)
		self.assertIn("!isDirty", save)
```

- [ ] **Step 2: Run to see them fail**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_chart_theme --test test_the_panel_lives_in_its_folder`
Expected: FAIL, `False is not true`.

- [ ] **Step 3: Create the panel**

`do_derma/public/js/chart/components/prescription/PrescriptionPanel.vue`:

```vue
<template>
  <section class="workspace-panel prescription-panel" data-test="prescription-panel">
    <Teleport defer to="#chart-section-actions">
      <span v-if="hasEncounter && !loading" class="chart-pill" data-tone="neutral" data-test="prescription-count">
        {{ rowCount }}
      </span>
      <span v-if="statusPill" class="chart-pill" :data-tone="statusPill.tone" data-test="prescription-status">
        {{ statusPill.label }}
      </span>
      <template v-if="canEdit">
        <button
          type="button"
          class="ghost small"
          data-test="prescription-add"
          :disabled="loading || saving"
          @click="addRow"
        >
          <i class="fa-solid fa-plus" aria-hidden="true"></i>
          {{ __("Add medication") }}
        </button>
        <button
          type="button"
          class="primary small"
          data-test="prescription-save"
          :disabled="loading || saving || !isDirty"
          @click="save"
        >
          {{ saving ? __("Saving...") : __("Save") }}
        </button>
      </template>
    </Teleport>

    <p v-if="errorText" class="error-text" role="alert" data-test="prescription-error">{{ errorText }}</p>

    <div v-if="loading" class="empty-state">{{ __("Loading prescriptions...") }}</div>
    <div v-else-if="!hasSessionContext" class="empty-state">
      {{ __("Prescriptions are visit-scoped. Select or start an appointment session first.") }}
    </div>
    <div v-else-if="!hasEncounter" class="empty-state">{{ __("No encounter found for this session.") }}</div>
    <p v-else-if="!rowCount" class="empty-line">
      {{ __("No medications prescribed for this visit.") }}
      <button v-if="canEdit" type="button" class="ghost small" @click="addRow">
        <i class="fa-solid fa-plus" aria-hidden="true"></i>
        {{ __("Add medication") }}
      </button>
    </p>
    <table v-else class="prescription-table">
      <colgroup>
        <col class="col-medication" />
        <col class="col-dosage" />
        <col class="col-duration" />
        <col class="col-form" />
        <col class="col-repeats" />
        <col class="col-actions" />
      </colgroup>
      <thead>
        <tr>
          <th class="chart-label">{{ __("Medication") }}</th>
          <th class="chart-label">{{ __("Dosage") }}</th>
          <th class="chart-label">{{ __("Duration") }} <span class="required-mark">*</span></th>
          <th class="chart-label">{{ __("Form") }}</th>
          <th class="chart-label">{{ __("Repeats") }}</th>
          <th class="chart-label"><span class="sr-only">{{ __("Actions") }}</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in orderedRows" :key="row.medication_request" class="ordered-row" data-test="prescription-ordered-row">
          <td>
            <span class="medication-name">{{ row.medication || row.drug_name || row.drug_code }}</span>
            <small v-if="row.drug_code" class="drug-code">{{ row.drug_code }}</small>
          </td>
          <td>{{ row.dosage || "—" }}</td>
          <td>{{ row.period || "—" }}</td>
          <td>{{ row.dosage_form || "—" }}</td>
          <td>{{ row.number_of_repeats_allowed || "—" }}</td>
          <td class="ordered-cell">
            <span class="chart-pill" data-tone="ok" :title="row.medication_request">{{ __("Ordered") }}</span>
          </td>
        </tr>
        <PrescriptionRow
          v-for="draft in drafts"
          :key="draft.key"
          :row="draft"
          :read-only="!canEdit"
          :open-field="openPicker?.key === draft.key ? openPicker.field : ''"
          :comment-open="openComment === draft.key"
          :missing="showMissing ? getRequiredGaps(draft) : []"
          @update="(field, value) => updateField(draft, field, value)"
          @open-picker="(field) => (openPicker = { key: draft.key, field })"
          @close-picker="openPicker = null"
          @toggle-comment="openComment = openComment === draft.key ? null : draft.key"
          @remove="removeRow(draft)"
        />
      </tbody>
    </table>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue"
import PrescriptionRow from "./PrescriptionRow.vue"

const __ = window.__ || ((text) => text)

const VALUE_FIELDS = [
  "medication",
  "drug_code",
  "dosage",
  "period",
  "dosage_form",
  "number_of_repeats_allowed",
  "comment",
]
const REQUIRED_FIELDS = { medication: __("Medication"), period: __("Duration") }

const props = defineProps({
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  error: { type: String, default: "" },
  hasSessionContext: { type: Boolean, default: false },
  hasEncounter: { type: Boolean, default: false },
  encounterName: { type: String, default: "" },
  rows: { type: Array, default: () => [] },
  readOnly: { type: Boolean, default: false },
})

const emit = defineEmits(["save"])

let nextKey = 0
const drafts = ref([])
const snapshot = ref("")
const openPicker = ref(null)
const openComment = ref(null)
const showMissing = ref(false)

const canEdit = computed(() => props.hasSessionContext && props.hasEncounter && !props.readOnly)
const orderedRows = computed(() => (props.rows || []).filter((row) => row.medication_request))
const rowCount = computed(() => orderedRows.value.length + drafts.value.length)
const isDirty = computed(() => JSON.stringify(getPayload()) !== snapshot.value)

const statusPill = computed(() => {
  if (!props.hasEncounter) return null
  if (props.readOnly) return { label: __("Finalized"), tone: "neutral" }
  if (props.saving) return { label: __("Saving..."), tone: "neutral" }
  if (isDirty.value) return { label: __("Unsaved changes"), tone: "caution" }
  return null
})

const validationError = computed(() => {
  if (!showMissing.value) return ""
  const index = drafts.value.findIndex((draft) => getRequiredGaps(draft).length)
  if (index < 0) return ""
  const field = getRequiredGaps(drafts.value[index])[0]
  return __("Row {0}: {1} is required.")
    .replace("{0}", orderedRows.value.length + index + 1)
    .replace("{1}", REQUIRED_FIELDS[field])
})

const errorText = computed(() => validationError.value || props.error)

watch(() => props.rows, resetDrafts, { immediate: true })

function makeDraft(original = {}) {
  const values = Object.fromEntries(VALUE_FIELDS.map((field) => [field, original[field] ?? ""]))
  return { key: ++nextKey, original, values, linkedItems: [], lookup: 0, filling: false }
}

function resetDrafts() {
  drafts.value = (props.rows || []).filter((row) => !row.medication_request).map((row) => makeDraft(row))
  snapshot.value = JSON.stringify(getPayload())
  openPicker.value = null
  openComment.value = null
  showMissing.value = false
}

function isBlank(draft) {
  return VALUE_FIELDS.every(
    (field) => !draft.values[field] || (field === "number_of_repeats_allowed" && !Number(draft.values[field]))
  )
}

function getRequiredGaps(draft) {
  if (isBlank(draft)) return []
  return Object.keys(REQUIRED_FIELDS).filter((field) => !draft.values[field])
}

function getPayload() {
  return drafts.value.filter((draft) => !isBlank(draft)).map((draft) => ({ ...draft.original, ...draft.values }))
}

function addRow() {
  const draft = makeDraft()
  drafts.value.push(draft)
  openPicker.value = { key: draft.key, field: "medication" }
}

function removeRow(draft) {
  drafts.value = drafts.value.filter((entry) => entry.key !== draft.key)
  if (openPicker.value?.key === draft.key) openPicker.value = null
  if (openComment.value === draft.key) openComment.value = null
}

function updateField(draft, field, value) {
  if (field === "medication") return applyMedication(draft, value)
  draft.values[field] = value
}

async function applyMedication(draft, medication) {
  if (medication === draft.values.medication) return
  const token = ++draft.lookup
  draft.values = { ...draft.values, medication, drug_code: "", dosage: "", period: "", dosage_form: "" }
  draft.original = { ...draft.original, drug_name: "" }
  draft.linkedItems = []
  if (!medication) return
  draft.filling = true
  try {
    const [itemsResponse, defaultsResponse] = await Promise.all([
      frappe.call("healthcare.healthcare.doctype.patient_encounter.patient_encounter.get_medications", {
        medication,
      }),
      frappe.db.get_value("Medication", medication, [
        "default_prescription_dosage",
        "default_prescription_duration",
        "dosage_form",
      ]),
    ])
    if (token !== draft.lookup) return
    draft.linkedItems = (itemsResponse?.message || []).map((entry) => entry?.item).filter(Boolean)
    const defaults = defaultsResponse?.message || {}
    draft.values = {
      ...draft.values,
      drug_code: draft.linkedItems.length === 1 ? draft.linkedItems[0] : "",
      dosage: defaults.default_prescription_dosage || "",
      period: defaults.default_prescription_duration || "",
      dosage_form: defaults.dosage_form || "",
    }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn("Failed to apply medication defaults", error)
    if (token === draft.lookup) {
      frappe.show_alert({ message: __("Could not fill in this medication's defaults."), indicator: "red" })
    }
  } finally {
    if (token === draft.lookup) draft.filling = false
  }
}

function save() {
  if (!canEdit.value || props.saving || props.loading) return
  showMissing.value = true
  if (validationError.value) return
  showMissing.value = false
  emit("save", getPayload())
}
</script>

<style scoped>
.error-text {
  margin: 0 0 8px;
  color: var(--chart-danger-text);
  font-size: 12px;
}

.empty-state {
  padding: 14px;
  border: 1px dashed var(--chart-border-strong);
  border-radius: 10px;
  background: var(--chart-surface-muted);
  color: var(--chart-text-soft);
  font-size: 13px;
}

.empty-line {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  color: var(--chart-muted);
  font-size: 13px;
}

.prescription-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.col-medication {
  width: 32%;
}

.col-dosage {
  width: 17%;
}

.col-duration,
.col-form {
  width: 15%;
}

.col-repeats {
  width: 10%;
}

.col-actions {
  width: 11%;
}

.prescription-table th {
  padding: 8px 10px;
  border-bottom: 1px solid var(--chart-border);
  text-align: left;
}

.required-mark {
  color: var(--chart-danger-text);
}

.prescription-table :deep(td) {
  padding: 8px 10px;
  border-bottom: 1px solid var(--chart-surface-muted);
  color: var(--chart-text);
  font-size: 13px;
  vertical-align: top;
}

.prescription-table :deep(.medication-name) {
  font-weight: 600;
}

.prescription-table :deep(.drug-code) {
  display: block;
  margin-top: 3px;
  color: var(--chart-muted);
  font-size: 12px;
}

.ordered-cell {
  text-align: right;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
```

- [ ] **Step 4: Point `DermaChart.vue` at it and delete the old file**

In `do_derma/public/js/chart/DermaChart.vue` replace

```js
import PrescriptionPanel from "./components/PrescriptionPanel.vue"
```

with

```js
import PrescriptionPanel from "./components/prescription/PrescriptionPanel.vue"
```

Then: `git rm do_derma/public/js/chart/components/PrescriptionPanel.vue`

- [ ] **Step 5: Run the chart tests**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_chart_theme 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"`
Expected: `OK` (all `TestPrescriptionRow` and `TestPrescriptionPanelRestyle` tests pass; hex and teleport tests stay green).

- [ ] **Step 6: Build**

Run: `cd /Users/hameed/Developer/bench-v16 && bench build --app do_derma`
Expected: build succeeds with no Vue compile errors. Then restart the web server (after a build every `/assets/do_derma/...` URL 404s until it restarts): find the `frappe serve --port 8002` PID whose cwd is this bench (`lsof -a -p PID -d cwd`), kill it, and re-run `nohup bench serve --port 8002 >> logs/serve-8002.log 2>&1 &`.

- [ ] **Step 7: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
pipx run ruff check do_derma/tests/test_chart_theme.py && pipx run ruff format do_derma/tests/test_chart_theme.py
git add -A do_derma/public/js/chart/components/prescription do_derma/public/js/chart/components/PrescriptionPanel.vue do_derma/public/js/chart/DermaChart.vue do_derma/tests/test_chart_theme.py
git commit -m "feat(prescriptions): a native table replaces the desk grid

Draft rows are always editable; Add medication and Save live in the card
header with count and status pills; ordered rows share the table with an
Ordered pill. A stale medication lookup is ignored, half-filled rows block
the save, blank rows are dropped, and each row is resent whole so fields
the table does not show survive.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Browser verification

**Files:** none, unless a defect is found (fix it in the owning component, add a source test for it, commit as `fix(prescriptions): …`).

**Interfaces:** none.

- [ ] **Step 1: Log in.** `cd /Users/hameed/Developer/bench-v16 && bench browse dermaone.localhost --user Administrator` prints a port-8002 `?sid=` URL. Open it with `agent-browser`, then `http://dermaone.localhost:8002/app/derma-chart?appointment=APT-2026-9474` and click the Prescription tab. If any request 503s, drain the queue: `bench worker --queue default --burst`.

- [ ] **Step 2: Add and save.** At 1600×1000 in light mode, click Add medication. The Medication picker opens focused. Pick a medication: the in-row spinner shows, then dosage, duration and form fill. Status reads `Unsaved changes`. Click Save. Reload and confirm the row is still there, and check the database:
  `bench --site dermaone.localhost mariadb -e "select medication, period, dosage from \`tabDrug Prescription\` where parent='HLC-ENC-2026-18379'"`

- [ ] **Step 3: Stale lookup.** On a new row, pick medication A and immediately pick medication B. The row ends with B's defaults.

- [ ] **Step 4: Validation.** Clear Duration on a row and click Save. The Duration cell turns danger-toned and `Row N: Duration is required.` shows. Nothing is sent (check the network log). Add a blank row and save with a valid set: the blank row is not stored.

- [ ] **Step 5: Edit, comment, delete, Esc.** Change a dosage. Open the comment, type, close it, and hover the icon: the preview shows. Open a picker and press Esc: the picker closes and the cell button has focus (`document.activeElement.dataset.field`). Delete a row and save.

- [ ] **Step 6: Read-only and ordered.** Find a submitted encounter with a `medication_request` row:
  `bench --site dermaone.localhost mariadb -e "select p.parent, e.appointment from \`tabDrug Prescription\` p join \`tabPatient Encounter\` e on e.name=p.parent where e.docstatus=1 and p.medication_request is not null limit 1"`.
  If none exists, set `medication_request` on a row of a submitted encounter inside `bench console` and roll back at the end. Check that all rows are text, there is no Add or Save, the `Finalized` pill shows, and the `Ordered` pill shows.

- [ ] **Step 7: Viewports and themes.** Repeat a glance at 1280 and 1600, light and dark (`document.documentElement.dataset.theme = "dark"`). Check for no horizontal overflow, no light islands, and that picker dropdowns are not clipped. Take before/after screenshots into `$CLAUDE_JOB_DIR/tmp`.

- [ ] **Step 8: Clean up.** Delete the rows added on `HLC-ENC-2026-18379` through the tab itself and save. Confirm with the Step 2 query that the encounter is back to its starting rows.

---

### Task 5: Suite and lint

**Files:** none.

- [ ] **Step 1: Full suite**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --app do_derma 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"`
Expected: the only failures are names already failing on `main` (see the bench quirks memory). Any new name is a regression and must be fixed before finishing.

- [ ] **Step 2: Lint the changed Python**

Run: `cd /Users/hameed/Developer/bench-v16/apps/do_derma && pipx run ruff check do_derma/tests/test_chart_theme.py do_derma/tests/test_encounter_tabs.py`
Expected: no new findings.
