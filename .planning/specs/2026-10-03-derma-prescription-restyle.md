# Derma chart: Prescription tab restyle

Status: agreed 2026-10-03. Branch: `feat/derma-prescription-restyle`, cut from
`feat/derma-assessment-restyle`.
Follows `2026-10-03-derma-procedures-restyle.md` and `2026-10-03-derma-assessment-restyle.md`.

## Goal

The Prescription tab drops the embedded desk Table grid for a native Vue table in the chart
vocabulary (`.chart-label` heads, `.chart-pill` chips, `.ghost small` secondary buttons, one
filled button in the card header). Rows stay always editable. Endpoints, payload shape and
server validation are unchanged.

## Decisions

| Topic | Decision |
|---|---|
| Scope | Option C: replace the desk grid with a native table |
| Editing model | Option A: every draft row is always a line of chart inputs; one Save |
| Drug code | Option A: muted text under the medication; `Choose item` only when the medication links to several items; no column |
| Link fields | Desk `Link` controls (`only_select`), mounted on click in the cell, as `ConsumablesEditor.vue` does |
| Files | `components/prescription/PrescriptionPanel.vue` (rows, save, header) and `components/prescription/PrescriptionRow.vue` (one line and its pickers). The old `components/PrescriptionPanel.vue` is deleted |
| Server | No change to `get_derma_prescriptions` / `set_derma_prescriptions` |

Data note: on dermaone none of the 1,454 Medications has a linked Item, so the old Drug Code
column was empty on every row.

## Layout

### Card header

Left to right, after the `PRESCRIPTION` label:

- Neutral `.chart-pill` with the row count (ordered plus draft).
- Status pill, only when relevant: `Unsaved changes` (caution) or `Saving...` (neutral) while
  editable; `Finalized` (neutral) when read-only. Replaces the orange read-only box.
- `Add medication` (`.ghost small`, plus icon) and `Save` (`.primary small`), teleported to
  `#chart-section-actions`. Both hidden when read-only. Save is the tab's only filled button.

### Table

Native `<table>` in the Procedures look: `.chart-label` column heads, thin `--chart-border`
row rules, no grey header fill.

| Column | Content |
|---|---|
| Medication | Name, 13px semibold. Below it, muted: the drug code if set, or a `Choose item` link when the medication has more than one linked item. Required |
| Dosage | Input-look cell; click mounts a `Link` to Prescription Dosage |
| Duration | Input-look cell; click mounts a `Link` to Prescription Duration. Required marker |
| Form | Input-look cell; click mounts a `Link` to Dosage Form |
| Repeats | Small number input |
| Actions | Borderless cluster: comment icon (dotted when a comment exists; hover previews it, as in Procedures) and delete icon (danger only on `:hover`) |

- **Comment**: the icon toggles a full-width textarea row under the line. One open at a time.
- **Ordered rows** (`medication_request` set) come first, in the same columns as plain text,
  with an `ok` `Ordered` pill in place of the actions cluster. Not editable. Replaces the
  separate "Already ordered" list.
- **Filling defaults**: a `chart-spinner` inside the row being filled, not a banner.

### Empty states

- Encounter with no rows: muted line "No medications prescribed for this visit." and an inline
  `Add medication` ghost button (hidden when read-only).
- No session context / no encounter / loading: today's messages, styled like the Assessment
  empty state.

Dark mode comes from the `--chart-*` tokens; no extra rules.

## Editing and data flow

### State

`PrescriptionPanel` owns `draftRows`, cloned from the non-ordered `props.rows` on load and
after each save, plus a snapshot of their normalised form. `Unsaved changes` means the
normalised drafts differ from the snapshot. Inputs write to the row objects; nothing reads
values back from the DOM.

### Adding

`Add medication` appends an empty row and opens its Medication picker with focus.

### Picking a medication

`applyMedication(row)` keeps today's lookups: `get_medications` and the Medication defaults
(`default_prescription_dosage`, `default_prescription_duration`, `dosage_form`) in parallel,
overwriting dosage, duration and form.

- Each lookup carries a per-row token; a response for a medication the row no longer holds is
  ignored.
- The linked items are kept on the row (client-only, not sent). One item fills `drug_code`;
  several show `Choose item`, which mounts an `Item` link filtered to those items; none leaves
  it blank.
- Clearing the medication clears `drug_code`, dosage, duration and form.
- A failed lookup shows the existing red alert.

### Pickers

One picker open at a time. `@keydown.escape.stop` on the picker host, because Frappe's global
Esc otherwise blurs focus. Closing a picker writes its value to the row.

### Deleting

Removes the draft row immediately, no confirm; nothing is persisted until Save.

### Saving

- Rows with every field empty are dropped from the payload.
- A row with any value but no Medication or no Duration blocks the save: those cells get a
  danger border and one `prescription-error` line names the first problem
  ("Row 2: Duration is required."). Nothing is sent.
- Each payload row is the original row spread with the edited fields, so `name` and fields the
  table does not show (`interval`, `interval_uom`, `dosage_by_interval`, `intent`, `priority`,
  `strength`, `strength_uom`, `drug_name`) survive.
- Server errors render in the same `prescription-error` line.

### Read-only

Submitted encounter: every row is text; no pickers, Add, Save, delete or comment editing
(an existing comment still previews on hover).

### Unchanged

Both endpoints, `_merge_ordered_prescriptions`, `_validate_prescription_rows`, the tab count
badge, and `loadPrescriptionPanel` / `savePrescriptionPanel` in `DermaChart.vue` (only the
import path changes).

## Out of scope

- Guarding unsaved edits when switching tabs (lost today, still lost).
- Any server change.
- Exposing the hidden Drug Prescription fields in the table.

## Testing

Written first and failing.

Source (`test_chart_theme.py`, new `TestPrescriptionPanelRestyle`):

- the panel lives at `components/prescription/PrescriptionPanel.vue`, `DermaChart.vue` imports
  it from there, and `components/PrescriptionPanel.vue` is gone
- no `fieldtype: "Table"` in either file; `make_control` appears only in `PrescriptionRow.vue`
- `Add medication` and `Save` sit inside `<Teleport defer to="#chart-section-actions">`;
  `primary` appears once (Save); Add is `ghost small`
- ordered rows render an `Ordered` pill with `data-tone="ok"`; `prescription-ordered` list
  markup and `status-note` are gone
- delete's danger colour is set only under `:hover`
- picker hosts carry `@keydown.escape.stop`
- styles use `--chart-*` tokens; the hex-colour allowlist test stays green
- `data-test` hooks `prescription-panel`, `prescription-save` remain; `prescription-row`,
  `prescription-add`, `prescription-ordered-row`, `prescription-comment`, `prescription-error`
  exist

Server (`test_api.py`):

- saving a payload row that carries `name` and `interval` keeps `interval` on the stored row

Browser, on `APT-2026-9474` (draft) and a submitted encounter with ordered rows; 1280 and
1600, light and dark:

- add a medication: defaults fill with the in-row spinner; Save; reload; row is in the database
- pick a second medication quickly: the first lookup does not overwrite it
- a row missing Duration blocks Save and flags the cell; an all-blank row is dropped
- edit and delete existing rows; open a comment; hover preview; Esc closes a picker without
  losing focus
- submitted encounter: all text, `Ordered` pill shown
- before/after screenshots; test rows removed afterwards

Suite: diff failures against the known set on `main`; `ruff` via pipx.
