# One Owner For Procedure Template Variables

Date: 2026-08-16
Status: **Draft**

## Goal

A clinic administrator configures what a procedure records — the fields, their types, their
options, and which are required — in a form, and the chart then shows the clinician which fields
matter. Today that configuration is hand-typed JSON in a Code field with no validation until the
chart renders, and the required-field set has **four owners that disagree**, one of which is
decorative and one of which only works if a clinic happened to name its category "Botox".

## Decisions

- **The `Clinical Procedure Template` is the sole owner of required fields** → one place to look.
  A migration patch writes each derma template's currently-resolved set into
  `custom_derma_required_fields` *before* the hard-coded table is deleted, so no site silently
  stops requiring `lot_no`. Rejected: making `Derma Procedure Category.required_fields` the owner
  (adds a layer rather than removing one) and keeping the hard-coded table as an empty-only
  fallback (two owners again).
- **The two safety flags stay authoritative** (companion screen 4, Q1) → `product_tracking_required`
  and `device_settings_required` keep appending their fieldnames, and the builder renders those
  rows locked with a badge naming the source. A clinician cannot delete `lot_no` while tracking is
  on, which keeps the template consistent with the readiness rule that blocks on the same field.
  Trade-off accepted: strictly speaking two mechanisms on one doctype. Rejected: materialising the
  flags' fields once and letting them be deleted — that lets a template call `lot_no` optional
  while readiness still blocks on it.
- **Required is shown in the chart but never blocks placing a mark** (companion screen 4, Q2) →
  asterisks plus a running "2 required fields missing" line. Charting mid-procedure must not be
  refused, or values get recorded late or not at all. The existing throw at Clinical Procedure
  creation stays the real gate. Rejected: blocking the mark, and feeding unfilled fields into
  session blockers (couples this spec to spec 4).
- **`custom_derma_allowed_body_regions` is deleted** → zero readers anywhere in the app, and once
  marks Link to `Derma Body Template Part` (spec 1) the part list already expresses region scope.
- **`custom_derma_allowed_body_templates` becomes a server-side check** → today it is a hint
  buried in a nine-deep auto-select fallback, so nothing stops a Botox template being charted on a
  foot map.

## Current State (verified)

Verified against `d782a8a`, working tree clean. `Clinical Procedure Template` is owned by
**healthcare**; every `custom_derma_*` field on it is created by **do_derma** patches — there is
no `fixtures/` directory in this app, and `hooks.py:30-33` is an *export* selector only.

### The four owners of "required"

`_get_template_variables` (`api.py:626-652`) resolves them in this order (since the config
workspace's Phase 2 it delegates the order to `_required_field_owners`, and the old
`_merge_required_fields` helper is gone — the migration patch sketched below must dedupe itself):

1. `custom_derma_required_fields` JSON on the template (`api.py:636`)
2. `_category_required_fields(custom_derma_category)` (`api.py:630`)
3. `+ ["product_name", "lot_no", "expiry_date"]` if `custom_derma_product_tracking_required` (`:631-632`)
4. `+ ["device", "settings"]` if `custom_derma_device_settings_required` (`:633-634`)

`_category_required_fields` (`api.py:719-735`) matches on the **lowercased category document
name** — `botox`, `filler`, `laser`, `biopsy`, `lesion`, `acne`, `scar`, `pigmentation`. Every
clinic-named category resolves to `[]`, including both seeders' own (`DEMO Aesthetics`,
`E2E Derma <hash>`).

**`Derma Procedure Category.required_fields` is parsed nowhere.** It is fetched at `api.py:386`
and returned as `context["categories"]`; the only frontend consumer is `categorySettings()`
(`DermaChart.vue:2211-2214`), reached from one call site (`:2183`), which reads only
`.default_body_template`. `grep required_fields` across `*.vue`/`*.js`/`*.jsx` returns zero hits.
The same is true of the category's `consent_required`, `before_after_photo_required`,
`product_tracking_required` and `device_settings_required` — only the `custom_derma_*` twins on
the template are ever branched on. `_category_defaults` (`api.py:1515-1526`) does not even fetch
them.

### The JSON field and its parser

`custom_derma_variables_json` is a Code field (`options: "JSON"`), created by
`patches/seed_derma_v2_defaults.py:49-57`. `_parse_template_variable_schema` (`api.py:655-700`)
tolerates: an array of objects (canonical), an array of strings, an object wrapping the list under
`variables` or `fields`, and a JSON-encoded CSV string. Per row it accepts `label` → `variable_name`
→ `fieldname` for the label, and `fieldtype` → `type` for the type, normalised by
`_normalize_variable_type` (`api.py:745-751`) to one of seven values.

Three failure modes, all silent:

- **`"required": false` is flipped back to true** — `:693-694` sets it from the row, then `:697`
  ORs it with membership of the resolved required set.
- **An unknown required fieldname is dropped** — `:643-650` appends only what
  `_default_derma_variable` (`api.py:754-792`, 22 entries) recognises.
- **A real Python list or dict yields zero variables** — `_parse_json` calls `json.loads` on it,
  which raises, and the fallback is `[]`. `_parse_required_fields` (`api.py:703-707`) does not
  share this bug because its fallback is the value itself.

Fieldnames are normalised by `_variable_fieldname` (`api.py:738-742`), which lowercases and
collapses non-alphanumerics — so "Lot No" and "Lot  no." both become `lot_no` with no collision
check anywhere.

### What the clinician sees

`VariableEditor` (`DermaAnnotationStudio.jsx:974-1001`) keys on
`field.variable_name || field.fieldname || normalizeFieldname(field.label)` (`:979`) and types on
`field.type || field.fieldtype || "Data"` (`:981`). **It ignores `required` entirely** — no
asterisk, no gate. The only enforcement is `_validate_marks_ready_for_procedure`
(`api.py:2911-2937`), which throws at Clinical Procedure creation (`api.py:2823`), using the alias
map in `_mark_variable_value` (`api.py:2940-2955`).

### The two allowed-* fields

`custom_derma_allowed_body_templates` is read on exactly one line —
`DermaChart.vue:2177-2194` — and only as the 3rd/4th entry in a nine-deep `||` chain inside
`ensureSelectedBodyTemplate()`. It never filters the picker. `save_chart_mark` (`api.py:2738-2783`)
does no validation at all: it applies defaults, derives `body_view`, normalises `body_region`, then
blind-copies every `DERMA_MARK_FIELDS` key and saves with `ignore_permissions=True`.

`custom_derma_allowed_body_regions` has **zero readers**, backend or frontend. It appears only in
`DERMA_TEMPLATE_FIELDS` (`api.py:131`) and as an `insert_after` anchor in two patches.

### How it is edited today

Desk form only. `hooks.py:25-28` declares `doctype_js` for `Patient Encounter` and
`Clinical Procedure` only; there is no client script, no Vue UI, and no whitelisted write endpoint
for template configuration anywhere.

### Tests

**Zero** cover `_get_template_variables`, `_parse_template_variable_schema`,
`_category_required_fields`, `_parse_required_fields` or `_validate_marks_ready_for_procedure`.
`test_api.py:656-687` exercises `create_procedure_from_mark` with templates carrying no
requirements, so the validator's `missing` list is always empty and both throw paths are untested.
The e2e badge specs (`annotation-badges.spec.ts`, `annotation-freehand.spec.ts`) render
`derma_variables` but seed `custom_derma_required_fields` as `[]`.

## Non-Goals

- **No change to the parser's tolerated input shapes.** `_parse_template_variable_schema` keeps
  accepting everything it accepts today; sites with hand-written JSON keep working.
- **No change to `_validate_marks_ready_for_procedure`** beyond it reading a set with one owner.
  It stays the enforcement point, at the same moment, with the same message.
- **No change to the `_default_derma_variable` table** — the 22 known fieldnames keep their labels,
  types and options.
- **No new marker behaviours.** `custom_derma_marker_behavior` and its substring matching in
  `EmbeddedExcalidraw.jsx:392-417` are untouched.
- **`custom_derma_marker_preset_json` is untouched.**
- **No change to the category's visual fields** (`marker_behavior`, `marker_color`, `marker_label`,
  `default_body_template`, `note_sentence_template`, `workflow`) — only its unread requirement
  fields go.
- **`e2e_seed.py` is untouched.**

## Design

Materialise, then delete. Build the form. Enforce the one scope field worth keeping.

### 1. Migration patch — `materialize_derma_template_required_fields.py`

Runs **before** any deletion, idempotent, safe on a site missing the doctype:

```python
def execute():
	if not frappe.db.exists("DocType", "Clinical Procedure Template"):
		return
	fields = _select_existing_fields("Clinical Procedure Template", DERMA_TEMPLATE_FIELDS)
	for row in frappe.get_all("Clinical Procedure Template", fields=fields):
		resolved = _merge_required_fields(
			_parse_required_fields(row.get("custom_derma_required_fields")),
			_category_required_fields(row.get("custom_derma_category")),
		)
		if not resolved or resolved == _parse_required_fields(row.get("custom_derma_required_fields")):
			continue
		frappe.db.set_value("Clinical Procedure Template", row["name"],
			"custom_derma_required_fields", json.dumps(resolved), update_modified=False)
```

The flags' contributions are deliberately **not** materialised — they stay live, per the decision
above. A converged row is skipped, so a re-run writes nothing.

### 2. Deletions, in a later patch

- `_category_required_fields` (`api.py:719-735`) and its call at `:630` — gone. The dict moves into
  the migration patch as module-local seed data and dies with it.
- `Derma Procedure Category`: drop `required_fields`, `consent_required`,
  `before_after_photo_required`, `product_tracking_required`, `device_settings_required` from the
  doctype JSON, and drop them from the `_get_categories` field list (`api.py:386-390`).
- `custom_derma_allowed_body_regions`: `frappe.delete_doc("Custom Field", …)` guarded by existence,
  plus removal from `DERMA_TEMPLATE_FIELDS` and from the two patches that use it as an
  `insert_after` anchor (they already fall back to `description`).

After this, `_get_template_variables` reads exactly one JSON field and two flags.

### 3. Honest `required` — `api.py:693-697`

```python
	declared = variable.get("required")
	row_required = bool(declared) if declared is not None else fieldname in required
```

An explicitly `false` row stays false; a row that omits the key still inherits membership of the
resolved set. Flag-derived fields are appended by `:643-650` as before, so they cannot be turned
off this way.

### 4. Collision validation — a new gated endpoint

```python
@frappe.whitelist()
def save_derma_template_variables(template: str, variables: str | list, required_fields: str | list = None):
	"""Write the variables schema after validating it the way the runtime reads it."""
	_ensure_clinical_access()
	rows = _parse_json(variables, [])
	seen: dict[str, str] = {}
	for row in rows:
		fieldname = _variable_fieldname(row.get("fieldname") or row.get("label") or row.get("variable_name"))
		if not fieldname:
			frappe.throw(_("Every variable needs a label."))
		if fieldname in seen:
			frappe.throw(_("{0} and {1} both resolve to the fieldname {2}.").format(seen[fieldname], row.get("label"), fieldname))
		seen[fieldname] = row.get("label")
	…
```

Validation runs through **the same `_variable_fieldname` the runtime uses**, so what the builder
accepts is exactly what the chart will resolve. The write goes through
`frappe.get_doc(...).save()` rather than `frappe.db.set_value`, so `Clinical Procedure Template`'s
own controller and permissions run on top of the role gate. `ignore_permissions` is deliberately
**not** used here — unlike the `Health Annotation` writes elsewhere in `api.py`, this doctype's
DocPerms are consistent, so there is nothing to work around.

### 5. The builder — `public/js/config/panels/ProcedureTemplatesPanel.vue`

Mounts into the config workspace (spec 2). A row grid over label / type / options / required, with:

- live fieldname preview and a collision warning before save;
- flag-derived rows rendered **locked** with a badge (`from Product tracking`);
- the resolved required set shown as a summary line.

No `v-html`; every value renders through a Vue template.

### 6. Required, visible in the chart — `DermaAnnotationStudio.jsx:974-1001`

`VariableEditor` reads the `required` flag it already receives on each field and renders an
asterisk plus a per-mark "2 required fields missing" line. **It does not gate anything.** The
`data-test` hooks the badge specs already use are unchanged; the asterisk gets its own new hook.

### 7. Enforcing `allowed_body_templates` — `save_chart_mark` (`api.py:2738-2783`)

After defaults are applied and before the blind copy:

```python
	allowed = _split_csv(template_row.get("custom_derma_allowed_body_templates"))
	if allowed and payload.get("body_template") and payload["body_template"] not in allowed:
		frappe.throw(_("{0} cannot be charted on {1}.").format(template_row.get("template"), payload["body_template"]))
```

Guarded by `_has_field` so a site without the custom field skips the check. An empty or absent
value means "no restriction", exactly as today.

**What stays unchanged:** the parser's tolerated shapes, `_default_derma_variable`, marker
behaviour, the throw at procedure creation, and every existing `data-test` attribute.

## Security

- `save_derma_template_variables` is a new whitelisted endpoint and **calls
  `_ensure_clinical_access()` first**. `TestClinicalAccessGate` gains a case proving a user without
  a clinical role gets `frappe.PermissionError`.
- It writes configuration, not patient data, and saves through `frappe.get_doc(...).save()` so the
  target doctype's own permissions apply on top of the role gate.
- `template` is validated to exist before any write; `variables` is parsed and validated
  server-side, never trusted from the client.
- Labels and options are clinic-authored text rendered back to other users. Vue escapes by
  default, and `printing/render.py` escapes every value by hand because Frappe's print Jinja
  environment does not autoescape — that rule covers any of these values that reach print.
- Enforcing `allowed_body_templates` closes a write that previously accepted any body template
  from any caller.

## Acceptance Criteria

1. After migration, every derma template's `custom_derma_required_fields` contains what
   `_get_template_variables` resolved for it beforehand.
2. A template in a clinic-named category keeps requiring what it required before the hard-coded
   table was deleted.
3. `"required": false` on a row that is not flag-derived stays false in the chart.
4. Two labels normalising to the same fieldname are refused with a message naming both.
5. Flag-derived rows cannot be deleted or unmarked in the builder while the flag is on.
6. The studio shows an asterisk on required fields and a missing-count line — and still lets the
   mark be placed and saved.
7. Saving a mark whose `body_template` is outside the template's allowed list throws; an empty
   allowed list permits everything.
8. A user without a clinical role calling `save_derma_template_variables` gets a `PermissionError`.
9. **No regression:** hand-written `custom_derma_variables_json` in any tolerated shape still
   parses to the same variables.
10. **No regression:** `create_procedure_from_mark` throws for the same missing fields it throws
    for today.
11. **No regression:** the two existing badge e2e specs still pass unchanged.

## Phases

**Phase 1 — one owner.** Materialisation patch, deletion of the hard-coded table and the
decorative category fields, honest `required: false`, plus the first tests these functions have
ever had.
*Exit:* `_get_template_variables` reads one JSON field and two flags, and a clinic-named category
behaves identically to before the change.

**Phase 2 — the clinician sees it.** Asterisks and the missing-count line in `VariableEditor`.
*Exit:* a required field is visible in the chart at the moment of charting, not at procedure
creation.

**Phase 3 — the builder.** `save_derma_template_variables`, collision validation, the panel in the
config workspace, locked flag-derived rows.
*Exit:* a variable set can be authored end to end without typing JSON.

**Phase 4 — scope enforcement and cleanup.** `allowed_body_templates` enforced in
`save_chart_mark`; `custom_derma_allowed_body_regions` deleted.
*Exit:* a procedure cannot be charted on a body map its template forbids.

## Open Questions

- **Should the builder let a clinician invent a fieldname outside the 22 known ones?**
  *Default:* yes — the JSON already supports it; only the required-set append path is limited to
  known fieldnames, and that limitation stays.
- **What happens to a template whose JSON is unparseable at migration time?**
  *Default:* leave it untouched and log it. The patch must not rewrite what it cannot read.
- **Should deleting `custom_derma_allowed_body_regions` archive its values first?**
  *Default:* no. Nothing has ever read them.
- **Does the missing-count line appear per mark or per session?**
  *Default:* per mark, in the Selected Procedure editor. Session-level roll-up belongs to spec 4.
- **Do we validate options for `Select` variables?**
  *Default:* only that a `Select` has at least one option; contents are free text.

## Files to touch (summary)

| File | Change |
|---|---|
| `do_derma/api.py` | delete `_category_required_fields`; honest `required`; `save_derma_template_variables`; `allowed_body_templates` check; `DERMA_TEMPLATE_FIELDS` entry removed |
| `do_derma/do_derma/doctype/derma_procedure_category/derma_procedure_category.json` | drop five unread fields |
| `do_derma/patches/materialize_derma_template_required_fields.py` | *(new)* |
| `do_derma/patches/cleanup_derma_category_requirement_fields.py` | *(new)* |
| `do_derma/patches.txt` | two entries, in that order |
| `public/js/config/panels/ProcedureTemplatesPanel.vue` | the builder (file created by spec 2) |
| `public/js/chart/annotation/DermaAnnotationStudio.jsx` | asterisk + missing-count in `VariableEditor` |
| `do_derma/tests/test_template_variables.py` | *(new)* |
| `do_derma/demo_seed.py` | a template with required fields, for the browser specs |
| `e2e/tests/template-variables.spec.ts` | *(new)* |

`bench build --app do_derma` is **required** (studio and config bundles change). No bundle
filename changes.
