# Procedures Tab Polish

Date: 2026-08-13
Status: **Implemented & verified** (2026-08-13) — see [Verification](#verification)

## Goal

The Procedures tab shows how many procedures the visit holds, its note tooling
actually works, row actions read as icons, and a procedure can carry several
annotations with a deliberate choice of which one to open. From the request:
"show number of added procedures", "note template and save note are not
working", "show actions as icons, remove use chart action, allow adding
multiple annotations to one procedure".

## Decisions

- **New `Derma Note Template` doctype backs the picker** → the existing dialog
  UI was built for a template library, and the doctype it pointed at (`Dental
  Note Template`) exists nowhere in the bench → reusing only the per-template
  sentence field was rejected as it kills the shared library the dialog implies.
- **Notes write `custom_derma_notes`, never core `notes`** → healthcare marks
  `Clinical Procedure.notes` **`set_only_once`**, so any edit after insert
  throws `CannotChangeConstantError` — the second root cause of "save note not
  working" (found by the new round-trip test). The derma note outranks the core
  field on read; the core field stays as a legacy fallback.
- **Price overrides persist via four `custom_derma_*` fields** (user-confirmed)
  → the panel already wrote `price_override` / `no_charge` / `price_list` /
  `price_override_reason` and the endpoint silently dropped all of them; hiding
  the UI was rejected in review.
- **Annotate opens a picker when ≥1 annotation exists** (user-confirmed) →
  resume-newest-and-overwrite was the old behaviour and made a second drawing
  per procedure impossible; always-new was rejected because editing a specific
  past drawing is the common case.
- **Use Chart removed** → its only effect was Photos-tab filtering with zero
  feedback on the procedures list; no e2e referenced it.

## Current State (verified, pre-change)

- Tab hint: `DermaChart.vue:622` static `Treatment`; `procedureCount` existed
  unused for this purpose at `:773`.
- Note picker: `ProcedurePanel.vue:1141-1147` linked `Dental Note Template`
  (no such DocType in any app); fetch errors swallowed to a misleading
  "Selected template has no text."; `fetchDentalNoteTemplate` returned a bare
  `""` when unnamed (type bug).
- Save Note: unawaited `saveRow(row, {silent:true})`, unconditional green toast
  (`:1175-1185`); every silent failure path invisible; **and the write target
  itself rejects edits** (`notes` is `set_only_once`,
  `healthcare/.../clinical_procedure.json:180`).
- Prefill corruption: `DermaChart.vue` normalizeProcedureRow put the computed
  `derma_detail_text` summary into `notes`.
- Actions: text buttons Use Chart / Annotate / Delete (`:383-398`); Delete's
  label untranslated, no data-test.
- Multiple annotations: backend supports N per procedure (child table
  `custom_annotations`); the sole blocker was `latestAnnotationForAnchor`
  always resuming `[0]` (`DermaChart.vue`), so every save overwrote the newest.
- Price fields: written by the panel, absent from the doctype, silently dropped
  by `update_clinical_procedure_fields` (`api.py:2333`).

## Non-Goals

- No billing-sync work (`sync_derma_billables` stays a stub behind its toggle).
- No change to the annotation studio itself (spec C).
- Lab-case actions and their dead emits stay as-is behind `enable_lab_cases`.
- The Photos tab loses its procedure-scoped filter source (Use Chart was the
  only setter of `activeProcedureName`); it defaults to Visit scope.

## Design

### 1. Doctype — `do_derma/do_derma/doctype/derma_note_template/`
`title` (Data, reqd, unique, autoname `field:title`), `note` (Small Text, reqd),
`disabled` (Check). Permissions mirror Derma Procedure Category (SM/HC admin
write, practitioner read).

### 2. Custom fields — `do_derma/schema.py`
On Clinical Procedure: `custom_derma_notes` (Small Text) + Derma Billing section
+ `custom_derma_price_list` (Link Price List), `custom_derma_price_override`
(Currency), `custom_derma_no_charge` (Check),
`custom_derma_price_override_reason` (Small Text). `_get_derma_procedures`
selects them schema-defensively (`_select_existing_fields`).

### 3. Panel — `ProcedurePanel.vue`
`PROCEDURE_UPDATE_FIELD_MAP` translates client row keys → doc fieldnames at the
one call site (`saveRow`), which now returns `Promise<boolean>`; Save Note
awaits it, keeps the dialog open and shows red on failure. `fetchNoteTemplate`
reads `Derma Note Template.note`, alerts on failure, returns `null` so callers
can bail. The procedure template's `custom_derma_note_template` sentence (in
every client row via `DERMA_TEMPLATE_FIELDS`) is the preview/apply default when
no library template is picked. Actions column: Annotate = pencil icon +
count badge (keeps `data-test="procedure-annotate"`), Delete = trash icon
(`data-test="procedure-delete"`, tooltip + aria-label); Use Chart deleted.

### 4. Chart shell — `DermaChart.vue`
Procedures tab gets a `tab-count` badge (`data-test="procedures-tab-count"`,
sibling `<i>` so the tab-spine `button > span` label assertion holds).
`normalizeProcedureRow`: notes = `custom_derma_notes || notes` (summary text
dropped), plus `note_sentence_template` and the price fields mapped to client
keys. `annotateProcedure`: 0 annotations → studio fresh (`annotation: null` is
an explicit fresh-start signal to `openAnnotationStudio`); ≥1 →
`openProcedureAnnotationPicker` dialog (thumbnail, date, legend, Edit per row,
"New Annotation" primary; `on_hide` removes the wrapper so hooks never stack).
`activateProcedure` deleted.

What stays unchanged: `update_clinical_procedure_fields` (gates via
`_ensure_clinical_access`), the annotation studio, delete endpoint, billing sync.

## Security

No new endpoint. The new doctype is reached only through `frappe.client.get`,
which enforces its DocPerms (practitioner read). Writes still ride
`update_clinical_procedure_fields` → `_ensure_clinical_access` +
`has_permission("write")`; `TestProcedureFieldUpdates.test_is_gated` covers it.

## Acceptance Criteria

- Procedures tab shows the visit's procedure count; hidden at zero.
- Note dialog: picker lists Derma Note Templates; apply/append works; the
  procedure's own sentence is offered by default; save reports truthfully and
  an amended note survives a second save and a reload.
- Price override / no charge / price list / reason survive a reload.
- Annotate on a procedure with drawings opens the picker; New Annotation
  creates a second Health Annotation; Edit resumes the chosen one.
- Existing anchoring guarantees hold (resume in place, no duplicate on re-save).

## Phases

1. Schema + doctype + endpoint round-trip tests. Exit: `run-tests` green.
2. Panel + chart shell UI. Exit: manual pass on dermaone.localhost.
3. E2E updates (anchoring picker flow, icon badge). Exit: suite green.

## Open Questions

- Should legacy core `notes` content be migrated into `custom_derma_notes`?
  Default: no — read fallback covers display, and a patch can do it later if
  editing legacy notes becomes a need.

## Reconciliation — what changed vs the plan

- The plan assumed notes could keep writing the core `notes` field. The first
  full test run threw `CannotChangeConstantError` — healthcare marks it
  `set_only_once` — so `custom_derma_notes` was added and became the write
  target and read priority (`api.py` `_row_notes` precedence flipped too).
- The picker dialog needed `on_hide` wrapper removal: Frappe keeps hidden
  modals in the DOM, so a re-opened picker stacked duplicate data-test hooks
  (caught by a strict-mode e2e failure).

## Verification

- **Integration**: `bench --site dermaone.localhost run-tests --app do_derma` —
  **81 tests OK** (new: `TestProcedureFieldUpdates` ×3 incl. the
  set_only_once regression and the gate, `TestDermaNoteTemplate` ×1). The
  RED run surfaced the set_only_once failure that reshaped the design.
- **Migrate**: `bench --site dermaone.localhost migrate` clean — creates the
  doctype and six custom fields.
- **E2E**: full suite `npx playwright test` — **44 passed (5.3m)**, including
  the rewritten `annotation-anchoring` picker flow and icon-badge assertion.
- **Lint**: `pipx run ruff check` clean on changed files; `format --check`
  clean except pre-existing space-indentation of `tests/test_api.py`
  (whole-file churn deliberately avoided).
- **Build**: `bench build --app do_derma` clean.
- **Manual (browser, 2026-08-14)**, demo patient `DEMO Amina Haddad` on
  encounter `HLC-ENC-2026-03138`: count badge shows `3` and hides at zero; row
  actions are pencil+trash icons with an annotation-count badge and no Use
  Chart; the note dialog's picker offers "Create a new **Derma Note
  Template**"; the editor opens with the real note, not the computed summary;
  **Save Note persisted to `custom_derma_notes`** (previously `null`, and
  previously impossible on the `set_only_once` core field); the annotation
  picker lists the existing drawing with thumbnail, date and legend plus New
  Annotation, and creating one left the procedure holding **two** annotations.
  One cosmetic defect found and fixed: the tab count badge overlapped the
  "Procedures" label (padding added for decorated tabs).

## Files to touch (summary)

| File | Change |
|---|---|
| `do_derma/do_derma/doctype/derma_note_template/*` | *(new)* doctype |
| `do_derma/schema.py` | Clinical Procedure custom fields |
| `do_derma/api.py` | select new fields; note precedence in `_row_notes` helper |
| `do_derma/public/js/chart/components/ProcedurePanel.vue` | note dialog fixes, saveRow promise+map, icon actions |
| `do_derma/public/js/chart/DermaChart.vue` | tab count, row normalization, annotation picker, drop activateProcedure |
| `do_derma/public/js/chart/derma_chart.bundle.css` | tab-count, picker styles |
| `do_derma/tests/test_api.py` | round-trip + gate + doctype tests |
| `e2e/tests/annotation-anchoring.spec.ts` | picker-aware helper, badge assertion |
