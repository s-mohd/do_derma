# Body Template Areas That Keep What You Type

Date: 2026-08-16
Status: **Phases 1-2 implemented & verified** (2026-08-16) — Phases 3-4 still **Draft**. Both
shipped phases deviated from the plan; see
[Reconciliation](#reconciliation--what-changed-vs-the-plan) and [Verification](#verification).

## Goal

A clinician draws an area on a body map, fills in *Plane: Subdermal, Units: 2.5*, and that
becomes queryable clinical data attached to the mark — reloadable when the annotation is
reopened, joinable back to the exact region it was drawn on, and safe from a colleague
redrawing the body map next week.

None of that is true today. Area variable values are collected in the annotation studio and
never persisted as data: they render badges, the badges become an HTML string, the string
lands in `annotation_data`. An area left blank disappears entirely. The mark cannot name the
region it sits on, because the studio drops the `template_part` the canvas already computed
and the free text that survives is squeezed through a fixed 15-word vocabulary. And saving the
body map hard-deletes any region absent from the payload, orphaning every mark drawn on it.

This is the first of four specs and **ships first**, because the other three read this model.

## Decisions

- **Area values persist in a new child table on `Derma Chart Mark`** → the point of collecting
  them is to query them later ("every mark where plane = Subdermal"). Trade-off accepted: a new
  doctype plus a patch. Rejected: a JSON column (unqueryable) and routing values through
  `DERMA_MARK_FIELDS` (works only for the 22 fieldnames `_default_derma_variable` already knows,
  so clinic-invented variables would still vanish).
- **The mark gains a Link to `Derma Body Template Part`; `body_region` stays derived** →
  existing reads, reports and history depend on the coarse 15-value vocabulary, so
  `_normalize_derma_body_region` keeps filling it. The Link is the new truth, `region_label`
  keeps the exact name. Rejected: storing the exact part name in `body_region`, which silently
  changes the meaning of every mark ever saved.
- **`save_derma_body_template_parts` never deletes** → a removed region is soft-disabled, full
  stop, with no reference check. Trade-off accepted: the parts table accumulates tombstones from
  draft edits, which the collapsed "Retired areas" list makes visible and restorable. Rejected:
  delete-if-unreferenced, which is one more branch to get wrong on a destructive path.
- **Backfill links parts only where unambiguous** → an idempotent patch sets
  `body_template_part` where `region_label` matches exactly one `part_name` on that mark's
  `body_template`, and leaves it null otherwise. **Area values are not reconstructed** from the
  stored HTML: parsing a presentation format back into clinical values would invent data that
  looks authoritative.
- **The designer stays its own page, reached from the config workspace** (companion screen 3,
  Q1) → smallest change, and the Excalidraw `process.env` shim stays isolated in that page's
  bootstrap. Rejected: an embedded overlay in the Vue config page.
- **Variables stay per-area, with a copy-to-selected-areas action** (companion screen 3, Q2) →
  no new doctype, no migration, `_hydrate_template_parts` untouched. Rejected: shared variable
  sets (new doctype + a second resolution layer) and template-level defaults with per-area
  override (introduces precedence, which is exactly the shape of the required-fields defect).

## Current State (verified)

Verified against `d782a8a`, working tree clean.

### The three doctypes (all owned by `do_derma`)

`Derma Body Template` (`do_derma/do_derma/doctype/derma_body_template/derma_body_template.json`)
autonames on `title`, and carries `view_key`, `gender`, `template_type`, `sequence`, `disabled`,
`image`, `annotation_template` and a `regions_json` Code field. **It has no child table** —
parts are a separate top-level doctype linking back.

`Derma Body Template Part` (`.../derma_body_template_part/derma_body_template_part.json`) is
top-level, hash-named, with `body_template` (Link, reqd), `part_name` (Data, reqd), `disabled`
(Check), `shape_json` (Code, reqd), `color`, `opacity`, and `variables` → a Table of
`Derma Template Part Variable`.

`Derma Template Part Variable` (`.../derma_template_part_variable.json`) is a child table with
exactly three fields: `variable_name` (Data, reqd), `type`
(Select: `Data\nSelect\nFloat\nInt\nDate\nCheck`, reqd), `options` (Small Text).

All three controllers are bare `pass`. **No client script exists on any of them.**

### Where the values go today

`DermaAnnotationStudio.jsx` holds `partValues` at `:331` (`useState({})`, keyed by part name),
written only by `updatePartValue` at `:611-619`, whose sole caller is the Selected Area editor's
`onChange` at `:945`. It is read in three places: `collectBadgeItems` (`:436`, implementation
`:125-163`), the part-styling effect (`:454-461`), and the editor's value binding (`:944`).

It reaches the server **only as rendered HTML**: `badgeItems` → `generateAnnotationDataHTML`
(`:196-218`) → `annotation_data` in the `save_derma_annotation` payload at `:719`, which lands on
the `Health Annotation Table` child row (`api.py:2040`). Areas with no filled values are dropped
before that, at `:151-153`.

**It is not in the mark payload.** `handleMarkPlaced` (`:627-651`) builds its `save_chart_mark`
args explicitly at `:630-649`; `partValues` never appears. `partValues` initialises to `{}`
unconditionally, so reopening a saved annotation shows empty fields.

### Where the region identity goes today

`EmbeddedExcalidraw.jsx:499-501` already computes all three:

```js
body_region: region?.part_name || region?.partName,
region_label: region?.part_name || region?.partName,
template_part: region?.name || region?.partId,
```

The studio forwards `body_region` and `region_label` and **drops `template_part`** — it is not
among the keys at `DermaAnnotationStudio.jsx:630-649`. Then `save_chart_mark` (`api.py:2738-2783`)
runs `body_region` through `_normalize_derma_body_region` (`api.py:1885-1926`), which
substring-matches into a fixed 15-value set and defaults to `"Other"` (`:1926`).

`derma_chart_mark.json:65-68` confirms the shape: `body_template` is a Link to
`Derma Body Template`; `body_view`, `body_region` and `region_label` are plain `Data`.
**There is no Link to `Derma Body Template Part`.** Persisted fields are gated by the
`DERMA_MARK_FIELDS` allowlist (`api.py:78-120`, applied at `:2774-2778`), which contains nothing
part- or variable-shaped.

### The read path (reusable)

`_hydrate_template_parts` (`api.py:463-490`) is the pattern to mirror: one `frappe.get_all` over
a child table filtered `parent in [...]` plus `parenttype`, then per-row expansion into
`{variable_name, fieldname, type, fieldtype, options}` using `_variable_fieldname` (`api.py:738-742`)
and `_normalize_variable_type` (`api.py:745-751`).

`_attach_body_template_parts` (`api.py:441-460`) bulk-fetches parts **filtered `disabled: 0`** —
which matters, because the "Retired areas" list needs the disabled ones.

Both whitelisted endpoints already gate: `get_derma_body_template_parts` (`api.py:493-509`) and
`save_derma_body_template_parts` (`api.py:512-561`) each call `_ensure_clinical_access()` first.

### The destructive save

`api.py:523-529`:

```python
incoming_names = {part.get("name") for part in payload if part.get("name")}
existing = frappe.get_all("Derma Body Template Part", filters={"body_template": body_template}, fields=["name"])
for row in existing:
	if row.name not in incoming_names:
		frappe.delete_doc("Derma Body Template Part", row.name, ignore_permissions=True)
```

Then `doc.set("variables", [])` at `:546` wipes and rebuilds the child table on **every** save, so
child row names and `idx` churn even when nothing changed.

The designer re-zips the response **by array index** (`body-template-editor.bundle.jsx:227-233`):

```js
setParts((current) => current.map((part, index) => ({
  ...part, name: saved[index]?.name || part.name, variables: saved[index]?.variables || part.variables,
})))
```

The response comes from `get_derma_body_template_parts`, which filters `disabled: 0` — so the
moment soft-disable exists, **the index zip is guaranteed to mismatch**. This is the single
riskiest interaction in the spec and is handled in Design §5.

### Region creation is unguarded

`body-template-editor.bundle.jsx:139-161`: any `type === "line"` element not already mapped
becomes a part, gated only by `element.points.length >= 3` (`:143`). No closure check, no
self-intersection check. Template name comes from `?template=` (`:66`) and the bare route renders
an error (`:74-78`).

### Tests

**Zero.** Nothing in `do_derma/tests/` or `e2e/` touches the designer, the two part doctypes,
`save_derma_body_template_parts`, or `partValues`. The only adjacent case is
`test_api.py:387-395`, which patches `api._get_body_templates` to raise and asserts the chart
degrades — it never exercises the real function.

## Non-Goals

- **No change to `_normalize_derma_body_region`.** The 15-value vocabulary and its `"Other"`
  default stay exactly as they are.
- **No reconstruction of historic area values** from `annotation_data` HTML.
- **No change to how annotations are stored.** `Health Annotation` / `Health Annotation Table`
  (do_health) and `_sync_chart_marks_for_annotation` keep their current contract, including the
  four idempotency properties in `CLAUDE.md`.
- **No shared or template-level variable sets.** Per-area only.
- **No change to `Derma Body Template.regions_json`** — it stays whatever it is today; parts are
  the model.
- **No new config UI here.** The workspace that links to the designer is spec 2; this spec
  assumes the designer is still reached by URL until spec 2 Phase 1 lands.
- **`e2e_seed.py` is untouched.** 40 specs assert exact counts against it.
- **No change to `Annotation Template`** (do_health). It remains a pass-through image library.

## Design

Three moves: values become rows on the mark; the mark gains a Link to the part it sits on; and
the body-map save stops destroying things. Everything else follows.

### 1. New child doctype — `do_derma/do_derma/doctype/derma_mark_variable/`

`istable: 1`, module `Do Derma`, four fields. Deliberately flat: this records what was typed,
not what the schema said it should be.

| fieldname | fieldtype | note |
|---|---|---|
| `fieldname` | Data, reqd | normalised through `_variable_fieldname` on write |
| `label` | Data | what the clinician saw |
| `value` | Small Text | stringified; `Check` becomes `"0"`/`"1"` |
| `source` | Select: `Area\nProcedure` | default `Area`; lets a later pass reuse the table |

Attached to `Derma Chart Mark` as `area_variables` (Table) via a `post_model_sync` patch that
follows the house idiom — existence guard, converge-don't-clobber, `module: "Do Derma"`,
targeted `frappe.clear_cache`, modelled on `patches/add_derma_annotation_title_field.py`.

### 2. Write path — `save_chart_mark` (`api.py:2738-2783`)

`DERMA_MARK_FIELDS` is a scalar allowlist and stays that way; the child table is handled
separately, after the existing blind copy:

```python
def _apply_mark_area_variables(doc, raw) -> None:
	"""Replace the mark's area variable rows. Absent key means leave rows alone."""
	if raw is None or not _has_field("Derma Chart Mark", "area_variables"):
		return
	rows = _parse_json(raw, raw if isinstance(raw, list) else [])
	if not isinstance(rows, list):
		return
	doc.set("area_variables", [])
	for row in rows:
		if not isinstance(row, dict):
			continue
		fieldname = _variable_fieldname(row.get("fieldname") or row.get("label"))
		if not fieldname:
			continue
		doc.append("area_variables", {
			"fieldname": fieldname,
			"label": row.get("label") or row.get("variable_name") or fieldname,
			"value": _stringify_variable_value(row.get("value")),
			"source": "Area",
		})
```

**The absent-key rule is the contract**: `save_chart_mark` is called from several places that
know nothing about areas (`persistMarkVariables` at `DermaAnnotationStudio.jsx:602`, the
procedure panel, `carry_forward`). Omitting `area_variables` must never wipe rows; sending `[]`
clears them.

Schema-defensive by `_has_field`, so a site that has not yet migrated silently ignores the key
rather than throwing.

### 3. Read path — mirror `_hydrate_template_parts`

```python
def _hydrate_mark_area_variables(mark_rows: list[dict[str, Any]]) -> None:
	if not mark_rows or not _has_doctype("Derma Mark Variable"):
		return
	names = [row.get("name") for row in mark_rows if row.get("name")]
	rows = frappe.get_all(
		"Derma Mark Variable",
		filters={"parent": ["in", names], "parenttype": "Derma Chart Mark"},
		fields=["parent", "fieldname", "label", "value", "source", "idx"],
		order_by="idx asc",
		limit=2000,
	)
	by_parent: dict[str, list[dict[str, Any]]] = {}
	for row in rows:
		by_parent.setdefault(row["parent"], []).append(
			{"fieldname": row["fieldname"], "label": row["label"], "value": row["value"], "source": row["source"]}
		)
	for mark in mark_rows:
		mark["area_variables"] = by_parent.get(mark.get("name"), [])
```

Called from `_get_marks` so every consumer — chart context, studio resume, procedure panel — sees
the rows without a second round trip.

### 4. Studio — stop dropping, start reloading

`DermaAnnotationStudio.jsx:630-649` gains two keys:

```js
body_template_part: payload.template_part || null,
area_variables: buildAreaVariableRows(payload.template_part_name, partValues, selectedParts),
```

`buildAreaVariableRows` emits one row per **declared** variable on that part, including blanks —
the current `:151-153` drop-if-empty rule is a badge-rendering concern and must not reach
storage, or "measured and found normal" is indistinguishable from "never looked".

Reload is the mirror: where `partValues` initialises `{}` at `:331`, it seeds from the marks
already loaded for the annotation, keyed by part name. `updatePartValue` (`:611-619`) and the
editor binding (`:944-945`) are unchanged.

`persistMarkVariables` (`:602`) keeps sending only procedure variables — it omits
`area_variables`, which under the §2 rule leaves the rows alone.

### 5. Non-destructive part save — `api.py:512-561`

Replace the delete loop at `:523-529` with a soft-disable:

```python
for row in existing:
	if row.name not in incoming_names:
		frappe.db.set_value("Derma Body Template Part", row.name, "disabled", 1, update_modified=False)
```

Stop the child-table churn at `:546` — only rewrite `variables` when the incoming rows differ
from the stored ones (compare the `(variable_name, type, options)` triples in order).

`get_derma_body_template_parts` gains `include_disabled=0`. It keeps its
`_ensure_clinical_access()` gate and keeps returning the same shape; `_attach_body_template_parts`
takes the flag through to its `disabled: 0` filter (`api.py:446-452`).

**The designer must stop zipping by index** (`bundle.jsx:227-233`). The save response is keyed by
`part_name`, and the client merges by that key, falling back to `localId` for rows that have not
been named yet. With soft-disable in place the index zip would silently reassign every row's
`name` to a different region — the exact failure this spec exists to prevent.

### 6. Designer guardrails — `bundle.jsx:139-161`

Region creation gains three checks before a part row is created: at least 3 points, closed
(first and last within a small tolerance), and non-self-intersecting. A failing shape stays on
the canvas and shows inline feedback; it does not become a part. Existing parts are never
re-validated on load — an already-stored bad polygon keeps working.

Retired areas render in a collapsed list with **Restore** (sets `disabled: 0`), fed by
`get_derma_body_template_parts(..., include_disabled=1)`.

Copy-to-areas is a client-side action: take the selected part's `variables` array and assign it
to the other selected parts before save. No new endpoint.

### 7. Part Link on the mark + backfill

New field on `Derma Chart Mark`: `body_template_part`, Link → `Derma Body Template Part`,
inserted after `region_label`, shipped in `derma_chart_mark.json` (as-built; see
Reconciliation). Added to `DERMA_MARK_FIELDS` so the existing blind copy at `api.py:2773-2778`
carries it — which means the annotation fan-out can also set it from client-authored
`customData.variables`, so `save_chart_mark` drops a part that does not belong to the payload's
own `body_template` (`_resolve_mark_template_part`).

Backfill patch, idempotent and safe on a site missing either doctype:

```python
def execute():
	if not (frappe.db.exists("DocType", "Derma Body Template Part") and _has_field("Derma Chart Mark", "body_template_part")):
		return
	marks = frappe.get_all("Derma Chart Mark",
		filters={"body_template_part": ["in", ["", None]], "region_label": ["!=", ""]},
		fields=["name", "body_template", "region_label"], limit=0)
	for mark in marks:
		matches = frappe.get_all("Derma Body Template Part",
			filters={"body_template": mark.body_template, "part_name": mark.region_label}, pluck="name")
		if len(matches) == 1:
			frappe.db.set_value("Derma Chart Mark", mark.name, "body_template_part", matches[0], update_modified=False)
```

Ambiguous or unmatched marks keep a null link — no guessing.

**What stays unchanged:** `_normalize_derma_body_region`, `body_region`, `region_label`,
`DERMA_MARK_FIELDS` as a scalar allowlist, the annotation storage contract, and every existing
`data-test` attribute.

## Security

- No new whitelisted endpoint. `save_chart_mark`, `get_derma_body_template_parts` and
  `save_derma_body_template_parts` each already call `_ensure_clinical_access()` first
  (`api.py:2740`, `:495`, `:514`); the new `include_disabled` argument does not change that.
- Area variable values are **patient clinical data**. They are read only through `_get_marks`,
  which is reached from already-gated endpoints, and written only through `save_chart_mark`.
- Values are stored as text and rendered by Vue, which escapes by default. **The one place they
  must be escaped by hand is print** — `printing/render.py` escapes every value because Frappe's
  print Jinja environment does not autoescape. If a later pass prints area variables, that rule
  applies.
- Regression test: `TestClinicalAccessGate` gains a case asserting a user without a clinical role
  cannot reach `get_derma_body_template_parts`, which is currently untested.

## Acceptance Criteria

1. Typing a value on an area and saving the annotation stores one `Derma Mark Variable` row per
   declared variable on the mark for that area — including the ones left blank.
2. Reopening that annotation shows the values in the Selected Area editor.
3. A mark placed on an area has `body_template_part` set to that part; `body_region` still holds
   the coarse vocabulary value and `region_label` still holds the exact part name.
4. A `save_chart_mark` call that omits `area_variables` leaves existing rows untouched; one that
   sends `[]` clears them.
5. Removing a region in the designer and saving sets `disabled: 1`. No `Derma Body Template Part`
   row is deleted by that endpoint under any input.
6. After a save that soft-disables a region, every remaining part in the designer still shows its
   own `name` and variables — no cross-assignment.
7. Saving a body map without touching variables leaves the child rows' `name` and `idx` unchanged.
8. An open or self-intersecting outline does not become a part and shows inline feedback.
9. Retired areas appear in a collapsed list and Restore returns them to the canvas.
10. The backfill patch is re-runnable, links only unambiguous matches, and leaves the rest null.
11. **No regression:** a chart with no `Derma Mark Variable` doctype present still renders — the
    `_has_doctype` / `_has_field` guards degrade instead of throwing.
12. **No regression:** existing marks with no part link still render, still print, and still
    promote to a Clinical Procedure.

## Phases

**Phase 1 — values become data.** ✅ **Shipped 2026-08-16.** New doctype, the `area_variables` field,
`_apply_mark_area_variables`, `_hydrate_mark_area_variables`, studio send + reload. Ship with a
Python test module.
*Exit:* type *Plane: Subdermal* on an area, save, reload the page, reopen the annotation, and the
value is there — and `frappe.get_all("Derma Mark Variable", …)` returns it.

**Phase 2 — the mark names its region.** ✅ **Shipped 2026-08-16.** `body_template_part` Link,
studio stops dropping `template_part`, `DERMA_MARK_FIELDS` entry, backfill patch.
*Exit:* a newly placed mark resolves to its `Derma Body Template Part` by Link, and the backfill
links existing unambiguous marks on a migrated site without touching the rest.

**Phase 3 — the body map stops destroying data.** Soft-disable, no child-table churn,
`include_disabled`, designer merges by `part_name`, retired-areas list with Restore.
*Exit:* delete a region that has marks on it, save, and the marks still resolve; the region is
restorable from the collapsed list.

**Phase 4 — guardrails and bulk edit.** Polygon validation at draw time, copy-variables-to-areas,
Playwright coverage on the extended `demo_seed`.
*Exit:* an open outline is refused with feedback; one area's variables can be applied to several
selected areas in one action.

## Open Questions

- **Should `source` distinguish more than Area/Procedure?**
  *Default:* no — two values, `Area` and `Procedure`, with only `Area` written in this spec.
- **Do blank rows count as "documented" for `_is_mark_documented` (`api.py:2901-2908`)?**
  *Default:* no. Documentation status keeps its current definition; area rows do not affect it.
- **What tolerance closes a polygon?**
  *Default:* 2% of the rendered template's smaller dimension, tunable in one constant.
- **Should the studio show a per-area completion indicator?**
  *Default:* not in this spec — the required-field indicator is spec 3's Phase 2.
- **Do we cap `area_variables` rows per mark?**
  *Default:* no hard cap; the hydration query's `limit=2000` mirrors `_hydrate_template_parts`.

## Reconciliation — what changed vs the plan

### Phase 2 (2026-08-16)

- **The field ships in `derma_chart_mark.json`, not a patch**, and sits after `region_label`
  rather than after `body_region` — same reasoning as Phase 1's `area_variables`: the doctype is
  do_derma's own, so a patch would be a second owner of the same schema. Only the backfill is a
  patch (`do_derma.patches.backfill_derma_mark_template_part`).
- **Its label is `Area`, not "Body Template Part".** `CONTEXT.md` fixes *Area* as the term over
  `part_name` / `region_label` / `body_region`; the fieldname keeps the Link target's name.
- **`save_chart_mark` validates the pairing** (`_resolve_mark_template_part`). The plan had the
  Link ride the blind `DERMA_MARK_FIELDS` copy untouched, but that copy is also fed by
  `_sync_chart_marks_for_annotation` from client-authored `customData.variables` — a scene could
  otherwise stamp any part, from any body template, onto a mark. A part that does not exist, or
  belongs to another `body_template`, is dropped rather than stored.
- **Drawn marks resolve their own area** (`EmbeddedExcalidraw.jsx:buildDrawnPlacementPayload`).
  The plan only cited the stamp path at `:499-501`; area- and freehand-drawn marks emitted no
  `body_region` / `region_label` / `template_part` at all, so AC 3 — "a mark placed on an area" —
  would have been false for exactly the marks most literally drawn on one. The centroid is run
  through the existing `findTemplatePartAtPoint` hit-test.
- **The backfill groups its lookups.** The sketch ran one `frappe.get_all` per mark; as-built it
  loads the parts of the affected templates once and matches in memory. Same `len(matches) == 1`
  rule, same null-on-ambiguity outcome.
- **Filters are `["is", "set"]` / `["is", "not set"]`** rather than the sketch's
  `["in", ["", None]]`, which in SQL compares against `NULL` and matches nothing.

### Phase 1 (2026-08-16)

- **No `add_derma_mark_area_variables.py` patch.** The plan shipped `area_variables` through a
  `post_model_sync` patch modelled on `add_derma_annotation_title_field.py`. That idiom exists for
  custom fields on *other apps'* doctypes; `Derma Chart Mark` is do_derma's own, so the field is a
  normal entry in `derma_chart_mark.json` and `bench migrate` creates the column and the child
  table. A patch would have been a second owner of the same schema.
- **Area rows are also written at annotation-save time**, not only when a mark is placed. The plan
  had `handleMarkPlaced` carry the rows, which only covers *type-then-place*. Clinicians place the
  mark and then fill the editor at least as often, so `persistAreaVariables()` walks the marks
  known to sit on each area (`areaMarks` ref — seeded from the loaded marks, extended on every
  placement) and writes the current values back before `save_derma_annotation` runs. A failed area
  write reports once for that area and lets the drawing save; losing the drawing over one value
  would cost more. The cost is one `save_chart_mark` round trip per mark on an area **the
  practitioner edited this session** — a `touchedAreas` ref gates it, so a drawing whose areas
  were only read writes nothing.
- **`_normalize_position` now leaves absent keys absent** (`api.py:360`). It clamped
  `payload.get("x_percent")` unconditionally, so `flt(None) → 0.0`, and any partial
  `save_chart_mark` — the new area write-back, and the pre-existing `persistMarkVariables` —
  moved the mark to the top-left corner. This was the one real defect the code review found;
  `test_a_variables_only_save_leaves_the_mark_where_it_was_placed` pins it, and
  `test_a_position_outside_the_template_is_clamped` keeps the clamp honest.
- **`_apply_mark_area_variables` guards `_has_doctype("Derma Mark Variable")` too**, not only
  `_has_field`, so a site with the field but not the child doctype degrades instead of throwing.
- **`CONTEXT.md` gained `Area` and `Area Variable` entries.** The feature made "Area" a
  first-class term standing over three older field names (`part_name`, `region_label`,
  `body_region`); leaving it undefined would have been a second vocabulary.
- **`buildAreaVariableRows` returns `null`, not `[]`, when the area declares no variables**, so the
  key is omitted rather than sent empty — otherwise placing a mark on a variable-less area would
  clear rows under the §2 absent-key rule.
- **`_hydrate_mark_area_variables` orders `parent asc, idx asc`** (the plan wrote `idx asc`), which
  is what `_hydrate_template_parts` does and what a multi-parent fetch needs. It is also
  **unpaged** rather than the planned `limit=2000`: `_get_marks` already caps the parents at 500,
  and a truncated read would show a mark as missing values it actually has — the exact
  "never looked" ambiguity this spec exists to remove. (Supersedes the Open Question's default.)
- Everything else landed as specified: the child doctype's four fields, the absent-key /
  empty-list contract, `_has_field` and `_has_doctype` guards, and `_get_marks` as the single
  hydration point.

## Verification

Real runs, 2026-08-16, site `dermaone.localhost`.

### Phase 2

**Migrate.** `bench --site dermaone.localhost migrate` — clean; created the `body_template_part`
column and ran `backfill_derma_mark_template_part` against the dev clone's real marks.

**Integration tests.** `bench --site dermaone.localhost run-tests --module
do_derma.tests.test_body_template_areas` — **22 tests, OK** (12 from Phase 1, 10 new). The new
ones cover: a mark stores the part it was placed on while `body_region` still normalises to the
coarse value and `region_label` keeps the exact name (AC 3); the link reads back through
`_get_marks`; a mark placed off any area keeps a null link (AC 12, read path); a part belonging
to another body template is refused; a part that no longer exists is refused; the backfill links
an unambiguous `region_label` (AC 10), leaves an ambiguous one alone, ignores parts of another
template, is re-runnable and never relinks an already-linked mark, and is a no-op on a site
without the field.

**Full suite.** `bench --site dermaone.localhost run-tests --app do_derma` — **112 tests, OK**.

**Code review.** Two-axis review (standards / spec fidelity) against `ea661f7`. Fixed from it:
the unvalidated part link, the `Area` label, the drawn-mark region gap, the backfill's
per-mark query, the duplicated test helper, and the assertion-free backfill test. The spec was
reconciled here rather than left contradicting the code.

**Lint.** `pipx run ruff check do_derma/` and `ruff format --check` — pass.

**Bundles.** `bench build --app do_derma` — done in 1.47s. Two bundles changed
(`derma_chart`, via the studio and the Excalidraw surface); no filename changed.

#### Not yet run (Phase 2)

- No Playwright coverage; still Phase 4.
- No manual browser pass — AC 3 for the **drawn** (area/freehand) path is argued from the code
  path: `buildDrawnPlacementPayload` runs the centroid through the same
  `findTemplatePartAtPoint` hit-test the stamp path uses on the click origin.
- AC 12's *print* and *promote to Clinical Procedure* legs are covered only by the pre-existing
  suite passing, not by a test that pins a null link specifically.

### Phase 1

**Migrate.** `bench --site dermaone.localhost migrate` — clean; created `Derma Mark Variable` and
the `area_variables` table field on `Derma Chart Mark`.

**Integration tests.** `bench --site dermaone.localhost run-tests --module
do_derma.tests.test_body_template_areas` — **12 tests, OK**. They cover: one row per declared
variable including blanks; `Check` stored as `"0"`/`"1"`; omitting the key leaves rows; `[]` clears
them; a JSON-encoded string payload; unnamed rows skipped; `_get_marks` hydration both with and
without rows; a site without `Derma Mark Variable` (marks still read, no key); a site without the
`area_variables` field (key ignored, nothing written); a variables-only save leaving `x_percent` /
`y_percent` where they were (AC 12); an out-of-range placement still clamped to 0-100.

**Security.** `TestClinicalAccessGate.test_body_template_parts_are_gated` (`test_api.py`) asserts a
user with no clinical role gets `frappe.PermissionError` from `get_derma_body_template_parts`, as
the Security section requires. No new whitelisted endpoint was added by this phase.

**Full suite.** `bench --site dermaone.localhost run-tests --app do_derma` — **102 tests, OK**. No
regression in the 89 that predate this phase.

**Code review.** Two-axis review (standards / spec fidelity) against `dee7544`. Everything it
raised is either fixed above (position clamp, unpaged hydration, `_has_doctype` guard, `CONTEXT.md`
vocabulary, pretty-printed doctype JSON, per-save write amplification) or recorded here.

**Lint.** `pipx run ruff check` and `ruff format --check` on `api.py`, the new test module and the
new doctype folder — all pass. (Pre-existing findings elsewhere in the repo were left alone.)

**Bundles.** `bench build --app do_derma` — done in 1.55s. No bundle filename changed, so the
`frappe.require` contract holds.

#### Not yet run (Phase 1)

- No Playwright coverage. `e2e/tests/body-template-areas.spec.ts` is Phase 4 in this spec.
- No manual browser pass through the annotation studio (type a value, save, reopen), so **AC 2 is
  argued from the code path, not observed**: `_get_marks` hydrates → `DermaChart.vue` passes
  `marks` → `seedPartValues` keys by the row's `label`, which is what `VariableEditor` binds on.
- `demo_seed.py` still seeds no area values.
- Known limit, not a defect: `buildAreaVariableRows` resolves the area against the *currently
  selected* template's parts, so values seeded from a mark drawn on a different body template are
  displayed but not re-written. Only areas edited this session are written at all.

## Files to touch (summary)

| File | Change |
|---|---|
| `do_derma/do_derma/doctype/derma_mark_variable/` | *(new)* child doctype |
| `do_derma/do_derma/doctype/derma_chart_mark/derma_chart_mark.json` | `area_variables` Table, `body_template_part` Link |
| `do_derma/api.py` | `_apply_mark_area_variables`, `_hydrate_mark_area_variables`, `_resolve_mark_template_part`, `DERMA_MARK_FIELDS` entry, `include_disabled`, soft-disable + no-churn in `save_derma_body_template_parts` |
| ~~`do_derma/patches/add_derma_mark_area_variables.py`~~ | dropped — the field ships in the doctype JSON, see Reconciliation |
| `do_derma/patches/backfill_derma_mark_template_part.py` | *(new)* idempotent link backfill |
| `do_derma/patches.txt` | two entries, `post_model_sync` |
| `public/js/chart/annotation/DermaAnnotationStudio.jsx` | send `body_template_part` + `area_variables`; seed `partValues` on open |
| `public/js/chart/excalidraw/EmbeddedExcalidraw.jsx` | drawn placements resolve their own area (`findTemplatePartAtPoint`) |
| `public/js/body-template-editor/body-template-editor.bundle.jsx` | merge by `part_name`, polygon validation, retired-areas list, copy-to-areas |
| `do_derma/tests/test_body_template_areas.py` | *(new)* |
| `do_derma/demo_seed.py` | area values + a retired region for the browser specs |
| `e2e/tests/body-template-areas.spec.ts` | *(new)* |

`bench build --app do_derma` is **required** (two bundles change). No `*.bundle.js` filename
changes, so the `frappe.require` contract holds.
