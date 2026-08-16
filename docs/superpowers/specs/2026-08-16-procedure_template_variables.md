# One Owner For Procedure Template Variables

Date: 2026-08-16
Status: **Implemented & verified** (2026-08-17). Phase 1 deviated on
where an explicit `"required": false` is believed, on how much of the category's unread machinery
had to go with the five fields, and on shipping one patch rather than two; Phase 2 deviated on
where the required list under test comes from; Phase 3 deviated on who owns `required` in the
save payload and on where the builder lives; Phase 4 added a studio change the plan did not
have — a server-only gate refused the map the studio itself had chosen — see
[Reconciliation](#reconciliation--what-changed-vs-the-plan) and [Verification](#verification).

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

- `save_derma_template_variables` and `get_derma_template_variables` are new whitelisted endpoints
  and **each calls `_ensure_clinical_access()` first**. `TestClinicalAccessGate` gains a case per
  endpoint (`test_template_variable_writes_are_gated`, `test_template_variable_reads_are_gated`)
  proving a user without a clinical role gets `frappe.PermissionError`.
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

**Phase 1 — one owner.** ✅ Shipped 2026-08-16. Materialisation patch, deletion of the hard-coded
table and the decorative category fields, honest `required: false`, plus the first tests these
functions have ever had.
*Exit:* `_get_template_variables` reads one JSON field and two flags, and a clinic-named category
behaves identically to before the change.

**Phase 2 — the clinician sees it.** ✅ Shipped 2026-08-16. Asterisks and the missing-count line in
`VariableEditor`.
*Exit:* a required field is visible in the chart at the moment of charting, not at procedure
creation.

**Phase 3 — the builder.** ✅ Shipped 2026-08-16. `get_derma_template_variables` /
`save_derma_template_variables`, collision validation, the builder in the config workspace, locked
flag-derived rows.
*Exit:* a variable set can be authored end to end without typing JSON.

**Phase 4 — scope enforcement and cleanup.** ✅ Shipped 2026-08-17. `allowed_body_templates`
enforced in `save_chart_mark` and `create_procedure_from_mark`, the studio opening on a map the
anchor's procedure allows; `custom_derma_allowed_body_regions` deleted.
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

## Reconciliation — what changed vs the plan

### Phase 1 (2026-08-16)

- **An explicit `"required": false` is believed unless a safety flag owns the field.** Design §3
  sketched `row_required = bool(declared) if declared is not None else fieldname in required`,
  which lets a row call `lot_no` optional while product tracking is on. That contradicts this
  spec's own second decision *and* the server: `_validate_marks_ready_for_procedure`
  (`api.py:3241-3255`) re-checks `product_name` and `lot_no` from the flag itself, so such a
  template would promise something Clinical Procedure creation refuses. `_get_template_variables`
  now passes a `locked` set — the fieldnames owned by `product_tracking` / `device_settings`, named
  by the new `SAFETY_FLAG_REQUIRED_SOURCES` — into `_parse_template_variable_schema`, and
  `_variable_is_required` resolves the three cases in one place. A flag-derived field stays
  required; every other row is believed.
- **A template that contradicts itself now raises `unenforced_required_fields`.** Believing an
  explicit `false` means a template listing `dose` in `custom_derma_required_fields` while its own
  variables row calls `dose` optional no longer enforces it anywhere — and spec 2's warning, "a
  required field the chart cannot enforce", is exactly that statement. Before this phase the OR at
  `api.py:981` flipped the row back to true and the contradiction was silent. Covered by
  `test_reports_a_field_the_template_lists_and_its_own_json_opts_out_of`. Fixing it is Phase 3's
  builder, which owns both fields at once.
- **The category's five unread fields took their whole reader chain with them.** Spec 2 Phase 2
  predicted `_select_existing_fields` would degrade `unread_fields` to `[]` "with no code change
  here". True, but a list that can only ever be empty is dead code, so `CATEGORY_UNREAD_FLAGS`,
  `CATEGORY_UNREAD_FIELDS`, `_category_unread_fields`, the payload key, the panel's "Read by
  nothing" column and its footnote are deleted instead. `config-category-unread-field` is the one
  `data-test` hook this spec removes, and it named a badge that can no longer render.
- **Categories no longer carry a rail count at all.** Spec 2 Phase 4 counted them by
  `unread_fields`, which is gone, so `get_config_health` returns three keys rather than four.
  `App.vue` renders the badge on `v-if="health[tool.key]"`, so a missing key is already "no badge";
  a fourth key pinned at zero would have been a rule that cannot fire pretending to be one that can.
- **`category_name_defaults` is deleted from the warning vocabulary**, with its two panel labels.
  It named a defect that no longer exists — its integration test is now
  `test_a_clinic_named_category_grants_no_requirements`, asserting the opposite.
- **One patch, not two.** The plan listed `cleanup_derma_category_requirement_fields.py` beside the
  materialisation patch. The five category fields are *standard* fields on a do_derma-owned
  doctype, so deleting them from `derma_procedure_category.json` is the whole deletion — schema
  sync does it, and there is no `Custom Field` row to remove. The cleanup patch the plan named is
  still needed for `custom_derma_allowed_body_regions`, which **is** a Custom Field; it lands with
  Phase 4, which is where that field's deletion belongs.
- **The materialisation patch only reads templates that carry a category.** The plan walked every
  `Clinical Procedure Template` through `_select_existing_fields`. A template with no category
  cannot gain anything from the category-name table, so the query filters on
  `custom_derma_category` being set and selects three columns.
- **`_is_unreadable_variable_schema` became `_is_unreadable_json(raw, parsed)`**, shared by the
  config panel and the patch. Both ask the same question — configured text that parses to nothing,
  with `[]`, `{}` and `null` as honest empties — and the patch had grown its own copy, sentinel set
  included. The two safety-flag source names are now `PRODUCT_TRACKING_SOURCE` /
  `DEVICE_SETTINGS_SOURCE` for the same reason: `SAFETY_FLAG_REQUIRED_SOURCES` and
  `_required_field_owners` must never drift, or a rename silently unlocks a safety field.
- **The category-name table lives in the patch as `CATEGORY_NAME_REQUIRED_FIELDS`,** a dict rather
  than the chain of `if`s `_category_required_fields` used. It is seed data for one migration, and
  it dies with the patch.
- **A `requirements_section` holding one note field became `note_section`.** Removing the five
  fields left a Section Break labelled "Requirements" with only `note_sentence_template` under it.
- **`_get_categories` (the chart's reader) lost the five fields too**, not just the config reader.
  It fetched them into `context["categories"]`, where `categorySettings()`
  (`DermaChart.vue:2211-2214`) reads only `default_body_template` — so they crossed the wire on
  every chart load and were read by nothing at either end.

### Phase 2 (2026-08-16)

- **The spec under test owns the required list for its own run, instead of `demo_seed.py` growing a
  template.** The Files table proposed a demo template with required fields "for the browser specs",
  but the browser specs resolve fixtures by the `E2E ` prefix and never read demo data — a demo
  template would have been unreachable from Playwright. `template-variables.spec.ts` instead writes
  `custom_derma_required_fields: ["plane"]` onto `E2E Filler` in `beforeEach` and restores `[]` in
  `afterEach`, which keeps `e2e_seed.py` untouched (a non-goal of this spec) and keeps the 40 specs
  that assert exact counts against it seeing the fixture they expect. `workers: 1` /
  `fullyParallel: false` is what makes the borrow safe against concurrency; a killed run leaves the
  borrowed value behind, and re-running the seeder repairs it. `plane` is the variable under test
  rather than the seeded `product` because it is one of the mark's own fieldnames, so what the
  studio writes is what the creation gate reads.
- **`variableKey(field)` is now one function, used by all four call sites.** The studio derived a
  variable's storage key four times: `VariableEditor` with a `normalizeFieldname(label)` fallback,
  and `updateProcedureValue`, `updatePartValue` and the value-seeding effect without it. A field
  carrying neither `variable_name` nor `fieldname` was rendered under a real key and written under
  `undefined`. The missing-count needs the same key the editor renders under, so the duplication had
  to go before it could be counted at all.
- **The note names the missing variables, not just how many.** The plan's line was "2 required
  fields missing"; the rendered line is "2 required variable(s) missing: Plane, Lot No" — *variable*
  because that is the word CONTEXT.md fixes and *field* is on its Avoid list. The count alone makes
  the clinician scan the form for asterisks they have already scrolled past.
- **The note renders only while something is missing, and never claims completeness.** A green "All
  required fields filled." was written first and deleted: the studio's values are keyed by the
  variable's own fieldname, while the creation gate resolves each required name through
  `_mark_variable_value`'s alias map (`api.py:3275-3290`) onto the mark's fields — `product` reads
  `product_name`, `lot` reads `lot_no`, `site` reads `body_region`. A template whose JSON names a
  variable `product` therefore stores nothing the gate can see, so a success line would have
  promised something Clinical Procedure creation refuses. The absence of a warning is the weakest
  claim that is still true. **Naming a variable outside the mark's own fieldnames is a live defect
  this phase does not fix** — the collision belongs to Phase 3's builder, which owns the fieldname
  at authoring time; `missingRequiredVariables`' docstring names it at the seam.
- **Three `data-test` hooks, not one.** Design §6 promised the asterisk "its own new hook". The row
  needs one too (`annotation-variable-row`, carrying `data-fieldname` / `data-required`) or a spec
  cannot say *which* variable is starred, and the note carries `data-missing-count` so the count is
  assertable without parsing prose. No existing hook changed.
- **The note is per editor, and the editor is per mark only while a mark is selected.** Values live
  under `procedureValues[procedureName]`; selecting a saved mark replaces them with that mark's
  (`handleMarkSelected`), and before any selection the count speaks for the values that the next
  mark will be stamped with. The "Selected Area" editor renders no note at all —
  `Derma Template Part Variable` has no `required` column.

### Phase 3 (2026-08-16)

- **`required_fields` is not a parameter of the save endpoint.** Design §4 sketched
  `save_derma_template_variables(template, variables, required_fields=None)`, which is two owners of
  "required" inside one payload — a row could say `required: true` while the list left it out, and
  the endpoint would have had to pick a winner. The signature is `(template, variables)`: the rows
  are the only place a clinician marks a variable required, and the server derives
  `custom_derma_required_fields` from them. The two fields on the document therefore converge on
  every save, which is what closes the `unenforced_required_fields` warning Phase 1 introduced.
- **A locked row stores no `required` key at all.** Forcing `required: true` into the JSON for a
  field a safety flag owns would keep it required after the flag was switched off — the flag's
  answer frozen into the row, which is the defect Phase 1 removed from the category table. Omitting
  the key means the row makes no claim, so `_variable_is_required` falls through to the owners:
  required while the flag is on, optional the moment it is off. The endpoint still forces `required`
  **true in the payload it returns**, because that is what the chart renders.
- **A deleted flag-owned row is not re-appended on write, only on read.** `_get_template_variables`
  already appends any required fieldname `_default_derma_variable` knows, so a builder that drops
  `device` writes JSON without it and reads it straight back. Adding a second re-append inside the
  write would have been a second owner of the same rule.
- **`_locked_required_sources(template_row)` is the one place a lock is derived.** Phase 1 computed
  the locked set inline in `_get_template_variables`; the payload needs the flag's *name* per
  fieldname for the badge, and two copies of "which flag owns this field" would drift.
- **The builder is its own component, not a section of `ProcedureTemplatesPanel.vue`.** The panel is
  a list; the builder is a form with its own load, validation and save state. `TemplateVariableBuilder.vue`
  replaces the table while it is open and the panel keeps only `editing` — the template name.
- **`variableFieldname()` moved to `public/js/shared/variable_fieldname.js`.** The builder previews
  the fieldname a label collapses to, and the studio already had `normalizeFieldname` doing exactly
  that. Copying it into the config bundle would have put three implementations of one rule (the
  third being `_variable_fieldname` in `api.py`) in the repo; the studio now imports the shared one.
  It stays a preview: **the server re-derives every fieldname through `_variable_fieldname` and is
  the only gate.**
- **`App.vue` no longer flips `loading` on a refresh.** Saving emits `changed`, the workspace
  re-reads the overview so the row's counts and warnings update — and the old `loading.value = true`
  swapped the whole panel for the loading status, unmounting the builder that asked for the refresh.
  The initial `ref(true)` still covers the first load. This was found by the e2e spec, not by review.
- **The endpoint that reads is new too.** Design §5 described only the writer, but the builder needs
  the resolved set — including the required fields that have no row of their own and the lock
  sources — which no existing payload carries. `get_derma_template_variables` returns exactly what
  the builder renders, `VARIABLE_FIELDTYPES` included, so the type dropdown cannot offer a type
  `_normalize_variable_type` would silently rewrite.
- **A `Select` with no options is refused** (Open Question default), and the options box only renders
  for `Select`. Contents stay free text.
- **The fieldname preview reads the stored fieldname first, exactly as the server does.**
  `_validated_variable_rows` resolves `_variable_fieldname(row.get("fieldname") or label)`, so a
  relabelled row keeps the key the chart already stores values under — re-keying `product_name` to
  `product_device` because its label reads "Product / Device" would orphan every value recorded so
  far. `fieldnameOf(row)` mirrors that precedence, so the preview, `data-fieldname`, the client's
  collision check and the write all name the same field. Covered by
  `test_relabelling_a_variable_keeps_its_fieldname` and the browser's relabel case.
- **A locked row keeps its label and type editable.** Only the required checkbox and the Remove
  button are locked, which is what the safety flag actually owns; a clinic that calls `lot_no`
  "Batch Number" is still requiring `lot_no`.
- **An unreadable `variables` payload is refused, not treated as empty.** The first draft passed
  `_parse_json(value, [])`, whose fallback would have silently cleared a template's whole variable
  set and its required list. Covered by
  `test_an_unreadable_payload_is_refused_rather_than_clearing_the_set`.
- **Saving drops a required fieldname that has no row and that `_default_derma_variable` does not
  know.** Such a name was reported by Phase 1 as `unenforced_required_fields` — required by the
  document, enforced nowhere — so the builder resolving the contradiction by removal is the point
  of the phase, not a loss.
- **Still open after this phase:** a variable named outside the mark's own fieldnames can be marked
  required, and the creation gate resolves required names through `_mark_variable_value`'s alias map
  onto the mark's fields — so `custom_field_of_my_own` can be required and never fillable. The
  builder now owns the fieldname at authoring time, which is where that check belongs; it is not
  written here because it needs the mark's field list, which is spec 1's territory.

### Phase 4 (2026-08-17)

- **The studio opens on a body map the anchor's procedure allows, which the plan did not ask for.**
  Design §7 was a server check alone, and it broke eight browser specs on the first run with
  *"E2E Freehand Graft cannot be charted on DEMO Face Map."* — the studio had opened on whichever
  image-carrying map came first for the patient's sex, which has nothing to do with the procedure
  being charted. **A gate that refuses the map the app itself chose is not enforcement, it is a
  broken chart.** `scopedTemplates` now narrows the default to the maps the anchor's own
  `Clinical Procedure Template` allows — the same *narrow, never to nothing* rule the sex and
  category pickers already use — and the picker still lists every map, so the clinician can go
  anywhere and hear the refusal from the server.
- **Scoping the default beat switching the map when a procedure is armed.** The first attempt
  moved the canvas at arming time. It re-broke `annotation-canvas.spec.ts:175` (the previous map's
  base64 image stayed in the scene's `files`, which `stripTemplateImagePayload` only clears for the
  template elements still present — the 193 MB defect that spec exists to prevent) and
  `annotation-resume.spec.ts:82` (fit measured across two maps: 90% then 98%). Choosing the map
  before the first load makes both moot: **one template image is ever loaded, so there is nothing
  stale to strip and nothing to refit.** The consultation studio, which has no anchor procedure,
  keeps whatever map it opens on and relies on the refusal.
- **Both writes are gated, not just `save_chart_mark`.** `create_procedure_from_mark`
  (`api.py:3290`) copies `body_template` out of its own `values` payload onto the mark and saves it
  with `ignore_permissions=True`, so the check runs there too, against the `Clinical Procedure
  Template` doc it has already loaded. A mark whose map was allowed when it was placed and
  forbidden by the time it is promoted is refused at promotion.
- **One reader of the allowed list per layer, not three.** The check landed as a third parser
  beside `DermaChart.vue`'s (case-sensitive, name-or-title) and the studio's — three rules for one
  field, so a map matched by title in the chart could be refused by the server. `variableFieldname`
  set the precedent in Phase 3, so `public/js/shared/allowed_body_templates.js` now owns the
  frontend rule for both, mirroring `_ensure_body_template_allowed`. The name-or-title branch is
  gone: `Derma Body Template` autonames `field:title`, so it never named two things.
- **The allowed list is read case-insensitively, and only against the body template's name.**
  `Derma Body Template` autonames `field:title`, so its name *is* its title and the chart's
  name-or-title matching had one meaning all along. The list itself is free text in a Small Text
  field, so `_ensure_body_template_allowed` folds case and `_split_csv` drops the spacing —
  `"  E2E FACE MAP ,"` allows `E2E Face Map`. Rejected: an exact match, which turns a typo into a
  chart nobody can mark.
- **The annotation fan-out swallows the refusal, deliberately.**
  `_sync_chart_marks_for_annotation` (`api.py:2616`) calls `save_chart_mark` inside a `try` that
  logs and moves on, so a forbidden pairing loses that one mark to the Error Log rather than
  failing the whole annotation save. It sends no `body_template` of its own, so in practice only
  the category default can reach the check from there.
- **A mark update that names neither field is not re-checked.** The gate binds where the pairing is
  chosen — placement and promotion. `persistMarkVariables` sends `{name, patient, …values}`, so
  typing a variable into an existing mark does not re-litigate the map it was placed on.
- **The patch is `cleanup_derma_allowed_body_regions.py`, not the
  `cleanup_derma_category_requirement_fields.py` the plan named.** Phase 1 already deleted the
  category's five fields with the doctype JSON, so the field name is what is left to say.
  `seed_derma_v2_defaults.py` no longer *creates* `custom_derma_allowed_body_regions` either — a
  fresh site creating a Custom Field for the next patch to delete would be theatre — and the three
  patches that used it as an `insert_after` anchor now point at
  `custom_derma_allowed_body_templates`.
- **`_template_defaults` fetches the allowed list**, so the check reuses the row `save_chart_mark`
  already reads instead of a second `frappe.db.get_value` per mark.

## Verification

### Phase 1

Integration (Frappe's runner, real site with `healthcare` + `do_health`):

```
bench --site dermaone.localhost run-tests --module do_derma.tests.test_template_variables
→ Ran 31 tests, OK
bench --site dermaone.localhost run-tests --module do_derma.tests.test_config_workspace
→ Ran 36 tests, OK (skipped=1)
bench --site dermaone.localhost run-tests --app do_derma
→ Ran 197 tests in 34.2s, OK (skipped=1)
```

`test_template_variables.py` is the first coverage these functions have ever had: the owner list
(template, both flags, first-owner-wins, and a clinic-named category now granting nothing), the
variables list (explicit `false` believed, a missing key inheriting the required set, a flag-derived
field that cannot be declared optional, a required field with no row of its own, an unknown
fieldname reaching nothing), every tolerated JSON shape including the unreadable one,
`_parse_required_fields` in all four shapes, the creation gate's four throw paths, and the patch
(materialising the table's set, keeping the declared fields first, a second run writing nothing,
an unreadable value left untouched, a flag's fields staying out of what is written, and a
clinic-named category as a no-op). Post-review, `test_config_workspace.py` gained the case where a
template's required list and its own variables row disagree.

Migrate:

```
bench --site dermaone.localhost migrate → clean; Derma Procedure Category fields are now
                                          title … default_body_template, note_section,
                                          note_sentence_template; the materialisation patch ran
                                          and 9 templates on this site carry required fields
```

Browser:

```
npx playwright test e2e/tests/config-workspace.spec.ts                        → 12 passed (22.2s)
npx playwright test e2e/tests/annotation-badges.spec.ts \
                   e2e/tests/annotation-freehand.spec.ts                      → 11 passed (2.9m)
```

The two badge suites are acceptance criterion 11: they render `derma_variables` through the parser
this phase changed, unchanged. The categories spec now asserts the template count only.

Build and lint:

```
bench build --app do_derma          → derma_config.bundle.css 4.54 Kb
pipx run ruff check do_derma/       → All checks passed
pipx run ruff format do_derma/      → 3 files reformatted, then clean
```

**Not yet run:** the full Playwright suite — Phase 1 changes no chart code, and the one known
failure (`annotation-anchoring.spec.ts:228`) predates it and is tracked by spec 1. Acceptance
criteria 4-8 belong to Phases 2-4 and are unimplemented.

### Phase 2

Browser (the only layer this phase changes):

```
npx playwright test e2e/tests/template-variables.spec.ts                       → 3 passed (27.2s)
npx playwright test e2e/tests/annotation-badges.spec.ts \
                   e2e/tests/annotation-freehand.spec.ts                       → 11 passed (2.8m)
```

`template-variables.spec.ts` covers acceptance criterion 6 in both halves: the asterisk on `plane`
with `product` carrying `data-required="0"` and no asterisk, the note counting 1 missing and
disappearing once the variable is filled, and — the *and saved* half — two marks placed either side
of filling it, read back from `Derma Chart Mark` as `["", "Subdermal"]`. The badge and freehand
suites are criterion 11 — they drive the same `VariableEditor` unchanged.

Python and lint (unchanged this phase, run to prove no regression):

```
bench --site dermaone.localhost run-tests --app do_derma  → Ran 197 tests in 36.7s, OK (skipped=1)
```

Build:

```
bench build --app do_derma → derma_chart.bundle.H6Y4DNQS.css 33.98 Kb; no bundle filename changed
```

Post-run, `E2E Filler.custom_derma_required_fields` reads `[]` again, confirming the spec restored
the fixture.

**Not yet run:** the full Playwright suite. Acceptance criteria 4, 5, 7 and 8 belong to Phases 3-4
and are unimplemented.

### Phase 3

Integration (Frappe's runner):

```
bench --site dermaone.localhost run-tests --module do_derma.tests.test_template_variables
→ Ran 47 tests, OK
bench --site dermaone.localhost run-tests --module do_derma.tests.test_api
→ Ran 45 tests, OK
bench --site dermaone.localhost run-tests --app do_derma
→ Ran 215 tests in 29.9s, OK (skipped=1)
```

`TestTemplateVariableBuilder` (16 cases) covers the reader (a template's rows, the flag named on a
locked row, an unknown template refused), the writer (the chart reading back what the builder wrote,
a JSON-encoded payload, an empty set clearing the field, a relabel keeping its fieldname, a
fieldname outside the 22 known ones) and every refusal (collision naming both labels, a variable
with no label, a `Select` with no options, an unreadable payload refused rather than clearing the
set). Acceptance criterion 5 is two cases: a flag-owned variable saved optional comes back required,
and a deleted one comes back at all. Criterion 8 is `TestClinicalAccessGate`'s two cases, one per
new endpoint.

Browser:

```
npx playwright test e2e/tests/config-variable-builder.spec.ts \
                   e2e/tests/config-workspace.spec.ts           → 16 passed (24.0s)
npx playwright test e2e/tests/template-variables.spec.ts        → 3 passed (27.2s)
npx playwright test e2e/tests/annotation-badges.spec.ts \
                   e2e/tests/annotation-freehand.spec.ts        → 11 passed (2.9m)
```

`config-variable-builder.spec.ts` is criteria 4, 5 and "authored end to end": a variable added and
marked required in the browser, read back from `Clinical Procedure Template` as
`["product", "plane", "needle_gauge"]` with `custom_derma_required_fields` `["needle_gauge"]`; a new
row colliding with an existing one, naming both and disabling Save; a relabelled row saved under the
fieldname it already had; and `lot_no` rendered locked under *Product tracking* with no Remove
button while the flag is on. It borrows `E2E Filler` and restores its seeded JSON, required list and
flag in `afterEach`, the same borrow-and-restore Phase 2 used.
The two studio suites are criterion 11 — they exercise `variableKey`, which now imports the shared
`variableFieldname`.

Build and lint:

```
bench build --app do_derma        → derma_config.bundle.GXJFOM4T.css 5.13 Kb; no bundle filename changed
pipx run ruff check do_derma/     → All checks passed
pipx run ruff format do_derma/    → 1 file reformatted, then clean
```

**Not yet run at the time:** the full Playwright suite — Phase 4 ran it and reports it below.

### Phase 4

Integration (Frappe's runner):

```
bench --site dermaone.localhost run-tests --module do_derma.tests.test_body_template_scope
→ Ran 10 tests, OK
bench --site dermaone.localhost run-tests --app do_derma
→ Ran 225 tests in 26.0s, OK (skipped=1)
```

`test_body_template_scope.py` covers acceptance criterion 7 in both directions — a map outside the
list refused with both names in the message, an allowed map saved, an empty list permitting
everything, a mark with no procedure template unrestricted, and the list read the way a clinic
types it (`"  E2E FACE MAP ,"`) — plus the second write path (`create_procedure_from_mark` refusing
a mark whose stored map has left the list) and the cleanup patch (the Custom Field gone, a second
run a no-op, `DERMA_TEMPLATE_FIELDS` no longer selecting it). The gate tests were watched to fail
first: with `api.py` stashed, 3 of them fail with *ValidationError not raised*.

Migrate:

```
bench --site dermaone.localhost migrate → clean; Clinical Procedure Template.custom_derma_allowed_body_regions
                                          is gone (has_field False, no Custom Field row)
```

Browser:

```
npx playwright test                                → 90 passed, 1 failed (10.4m)
npx playwright test e2e/tests/body-template-scope.spec.ts \
                   e2e/tests/annotation-canvas.spec.ts \
                   e2e/tests/annotation-resume.spec.ts  → 12 passed (2.5m)
```

The one failure is `annotation-anchoring.spec.ts` *"keeps a dragged treatment area at its drawn
size across resume"* — the known failure that predates this spec and belongs to spec 1. This is
the first **full** Playwright run any phase of this spec has recorded, which is what caught the two
regressions the first design of the studio change caused (see Reconciliation).

Build and lint:

```
bench build --app do_derma        → no bundle filename changed
pipx run ruff check do_derma/     → All checks passed
pipx run ruff format do_derma/    → 81 files left unchanged
```

## Files to touch (summary)

| File | Change |
|---|---|
| `do_derma/api.py` | *(Phase 1)* delete `_category_required_fields` and the category's unread machinery; honest `required` via `_variable_is_required` + `SAFETY_FLAG_REQUIRED_SOURCES`; `get_config_health` drops the categories key. *(Phase 3)* `get_derma_template_variables` / `save_derma_template_variables`, `_validated_variable_rows`, `_locked_required_sources`, `VARIABLE_FIELDTYPES`. Later: `allowed_body_templates` check; `DERMA_TEMPLATE_FIELDS` entry removed |
| `do_derma/do_derma/doctype/derma_procedure_category/derma_procedure_category.json` | *(Phase 1)* drop five unread fields; `requirements_section` becomes `note_section` |
| `do_derma/patches/materialize_derma_template_required_fields.py` | *(new, Phase 1)* |
| `do_derma/patches/cleanup_derma_allowed_body_regions.py` | *(new, Phase 4)* deletes the Custom Field; Phase 1's doctype JSON already took the category's five |
| `do_derma/patches/seed_derma_v2_defaults.py`, `upgrade_derma_template_variables.py`, `cleanup_derma_procedure_template_fields.py` | *(Phase 4)* stop creating `custom_derma_allowed_body_regions` and anchor on `custom_derma_allowed_body_templates` |
| `do_derma/tests/test_body_template_scope.py` | *(new, Phase 4)* the mark gate and the cleanup patch |
| `e2e/tests/body-template-scope.spec.ts` | *(new, Phase 4)* creates a second body map of its own, and deletes it again |
| `do_derma/patches.txt` | one entry in Phase 1, one in Phase 4 |
| `public/js/config/panels/ProcedureTemplatesPanel.vue` | *(Phase 1)* the `category_name` labels go; *(Phase 3)* a Variables button per row opens the builder, and a save emits `changed` |
| `public/js/config/panels/TemplateVariableBuilder.vue` | *(new, Phase 3)* the row grid: label / fieldname preview / type / options / required, locked rows badged with their flag |
| `public/js/shared/variable_fieldname.js` | *(new, Phase 3)* one `variableFieldname()` for the builder and the studio, mirroring `_variable_fieldname` |
| `public/js/shared/allowed_body_templates.js` | *(new, Phase 4)* one reader of the allowed list for the chart and the studio, mirroring `_ensure_body_template_allowed` |
| `public/js/chart/DermaChart.vue` | *(Phase 4)* `ensureSelectedBodyTemplate` reads the shared helper; the name-or-title match goes |
| `public/js/config/App.vue` | *(Phase 3)* a refresh no longer unmounts the panel that asked for it |
| `public/js/config/derma_config.bundle.css` | *(Phase 3)* `.config-builder` |
| `e2e/tests/config-variable-builder.spec.ts` | *(new, Phase 3)* borrows `E2E Filler` and restores it |
| `do_derma/tests/test_api.py` | *(Phase 3)* the access-gate case for the new write |
| `public/js/config/panels/CategoriesPanel.vue` | *(Phase 1)* the "Read by nothing" column and its footnote go |
| `do_derma/tests/test_config_workspace.py` | *(Phase 1)* the category-name warning, unread-field and health cases follow the deletion |
| `e2e/tests/config-workspace.spec.ts` | *(Phase 1)* the category spec drops the unread-field badge |
| `public/js/chart/annotation/DermaAnnotationStudio.jsx` | *(Phase 2)* asterisk + missing-count in `VariableEditor`; one `variableKey()` for all four call sites. *(Phase 4)* `scopedTemplates` picks the opening body map |
| `public/js/chart/derma_chart.bundle.css` | *(Phase 2)* `.derma-variable-required` and `.derma-variable-required-note` |
| `do_derma/tests/test_template_variables.py` | *(new)* |
| `e2e/tests/template-variables.spec.ts` | *(new, Phase 2)* — borrows `E2E Filler`'s required list and restores it, rather than seeding demo data the browser specs cannot reach |

`bench build --app do_derma` is **required** (studio and config bundles change). No bundle
filename changes.
