# A Place To Configure Derma

Date: 2026-08-16
Status: **Phases 1-3 implemented & verified** (2026-08-16); Phase 4 remains **Draft**. Phase 1
deviated from the plan on how the designer is opened and on where the page-row patch logic lives;
Phase 2 added a per-field owner and a warning vocabulary the plan did not name; Phase 3 reports the
enforcement mode as read-only and names the client-side gate — see
[Reconciliation](#reconciliation--what-changed-vs-the-plan) and [Verification](#verification).

## Goal

One page where a clinic administrator can see and change how derma charting behaves: which body
maps exist and what areas they have, which procedure templates require which fields, what the
categories are, and how strictly sessions are gated.

Today there is no such place. Configuration is spread across desk forms with raw JSON Code
fields, and **the Body Map Designer has no entry point anywhere in the app** — no workspace, no
sidebar item, no button, no client script. The only way in is typing
`/app/derma-body-template-editor?template=NAME` by hand, and the bare route renders an error
because it also demands the query parameter.

## Decisions

- **A new Vue desk page at `/app/derma-config`** → mirrors the proven `derma_chart` bootstrap and
  lets us build real editing UI, which a Frappe Workspace of shortcuts cannot. Trade-off: a new
  bundle and a `bench build`. Rejected: a Workspace with links (leaves editing on desk forms with
  raw JSON, which is the actual complaint) and a config tab inside `DermaChart.vue` (grows a
  sanctioned-oversized file and mixes clinical work with admin).
- **Left rail of tools, with a table list** (companion screen 2) → scales past four tools and
  reads as an admin console rather than a second chart. Rejected: top tabs (crowd past five) and
  a landing grid (an extra click on every task, forever).
- **The designer stays a separate page**, linked from the rail's body-template table with the
  `?template=` supplied (companion screen 3, Q1) → the Excalidraw `process.env` shim stays
  isolated in that page's bootstrap.
- **The rail links out to the do_health Annotation Template list rather than editing it** →
  do_derma does not own that doctype and treats it strictly as a pass-through.

## Current State (verified)

Verified against `d782a8a`, working tree clean.

### The page bootstrap pattern to copy

`do_derma/do_derma/page/derma_chart/derma_chart.js` is 23 lines: `on_page_load` calls
`frappe.ui.make_app_page`, `on_page_show` (line 15) empties `.layout-main-section` and
`frappe.require`s `["derma_chart.bundle.css", "derma_chart.bundle.js"]`, then constructs
`frappe.ui.DermaChart`. Mounting in `on_page_show` means it remounts on every navigation.

`derma_chart.bundle.js` (19 lines) is a class that `createApp(App).mount(...)` and registers
itself on `frappe.ui`. `App.vue` reads context from `frappe.route_options` and the do_health
sidebar — the config page needs none of that.

`derma_chart.json` is a source-backed `Page` row: `"standard": "Yes"`, `"module": "Do Derma"`,
`"system_page": 0`, **`"roles": []`** — no role restriction on the page itself. Authorization is
entirely `_ensure_clinical_access()` in the API.

`patches/ensure_derma_chart_page.py` is the precedent for shipping a page row to a site without
developer mode: declare a `values` dict, converge field-by-field with a `changed` flag so a no-op
run performs no write, else insert, then `frappe.clear_cache()`. **There is no equivalent patch
for `derma-body-template-editor`.**

### Confirmed absent

An exhaustive sweep for `body-template-editor` outside its own page folder finds only a
documentation row in `CLAUDE.md:124` and a prose comment in `demo_seed.py:56`. Specifically:
**no workspace JSON anywhere in the app** (no `*workspace*.json`, no `Workspace` / `navbar_item`
/ `Portal Menu` reference in any `.py` or `.json`); `derma_sidebar.js` defines exactly one
function, `do_derma.openChart`, which routes to `["derma-chart"]` (`:32`); `hooks.py:25-28`
declares `doctype_js` for only `Patient Encounter` and `Clinical Procedure`; `fixtures`
(`hooks.py:30-33`) covers only `Custom Field` and `Property Setter`, not `Page`.

### What the page needs to read

- Body templates: `_get_body_templates()` (`api.py:398-438`) already returns them with
  `_attach_body_template_parts` (`:441-460`), but **filtered `disabled: 0`** on both templates and
  parts — the config list needs disabled rows too.
- Procedure templates: `DERMA_TEMPLATE_FIELDS` (`api.py:122-142`) with
  `_select_existing_fields("Clinical Procedure Template", …)` (`:594`).
- Categories: `_get_categories()` (`api.py:370-395`).
- Settings: `get_feature_toggles()` (`do_derma/settings.py:29-34`), already in the chart payload
  at `api.py:1740`.

### Frontend contracts

`data-test` attributes are the Playwright selector contract — 59 of them across the Vue
components. Specs never wait on `networkidle`; they wait on a `data-test` element, because the
bundle is lazily `frappe.require`d and the desk holds long-poll sockets open.

## Non-Goals

- **No editing UI in this spec beyond navigation and listing.** The variables builder is spec 3;
  the readiness settings panel is spec 4. This spec ships the shell and the lists they mount into.
- **No change to the Body Map Designer itself** — its guardrails and retired-areas list are spec 1.
- **No change to `DermaChart.vue`.** The chart is untouched.
- **No new doctype.** Everything on this page already exists.
- **No Frappe Workspace, no navbar item, no portal route.**
- **No permission model change.** The page keeps `"roles": []`; the API gate is the boundary.
- **`e2e_seed.py` is untouched.**

## Design

A thin page that reads config through one new gated endpoint and links out to the tools.

### 1. The page — `do_derma/do_derma/page/derma_config/`

`derma_config.json` copies `derma_chart.json` field-for-field with
`"name": "derma-config"`, `"title": "Derma Configuration"`. `derma_config.js` copies
`derma_chart.js`, requiring `["derma_config.bundle.css", "derma_config.bundle.js"]`. No
`window.process` shim — that belongs to the Excalidraw page only.

`patches/ensure_derma_config_page.py` is `ensure_derma_chart_page.py` with the name changed. It
is `post_model_sync` and idempotent. **While we are there, ship the missing
`ensure_derma_body_template_editor_page.py` too** — that page row has never had one, so a
production site that lost it has no route for the button this spec adds.

### 2. The bundle — `public/js/config/derma_config.bundle.js`

Same 19-line shape as `derma_chart.bundle.js`: `createApp(App).mount(...)`, registered as
`frappe.ui.DermaConfig`. New folder `public/js/config/` keeps new code out of the four sanctioned
oversized files.

```
public/js/config/
  derma_config.bundle.js      # mount + frappe.ui registration
  derma_config.bundle.css
  App.vue                     # rail + active panel
  panels/BodyTemplatesPanel.vue
  panels/ProcedureTemplatesPanel.vue
  panels/CategoriesPanel.vue
  panels/ReadinessPanel.vue
```

Files stay well under the 800-line limit; panels split by tool, not by type.

### 3. One read endpoint — `get_derma_config_overview()`

```python
@frappe.whitelist()
def get_derma_config_overview():
	"""Everything the config workspace lists, in one round trip."""
	_ensure_clinical_access()
	return {
		"body_templates": get_config_body_templates(),
		"procedure_templates": get_config_procedure_templates(),
		"categories": _get_categories(),
		"readiness": get_config_readiness(),   # Phase 3; carries the feature toggles
	}
```

`get_config_body_templates()` queries `Derma Body Template` unfiltered and unlimited and carries an
`area_count` plus a `retired_area_count` per template (see
[Reconciliation](#reconciliation--what-changed-vs-the-plan) — it does *not* reuse
`_get_body_templates`, whose `limit=100` / `limit=1000` would silently under-count).
`get_config_procedure_templates()` reuses `_select_existing_fields` over `DERMA_TEMPLATE_FIELDS` so a
site missing any `custom_derma_*` field degrades instead of throwing.

Each section is wrapped in `_safe_derma_context(label, fallback, getter)` so one broken sub-query
logs and returns an empty list rather than blanking the page — the same treatment the chart gives
its context.

### 4. The rail and the table

```
┌─ Configure ──────┐┌──────────────────────────────────────────────┐
│ Body Templates ◀ ││ Body Templates              [+ New template] │
│ Procedure Temp…  ││ ┌──────────┬──────┬────────┬───────┬───────┐ │
│ Categories       ││ │ Title    │ Type │ Gender │ Areas │       │ │
│ Readiness        ││ │ Face — F │ Face │ Female │ 12    │[Design│ │
│ ─────────────    ││ │ Body — A │ Body │ Male   │ 24    │ regio…│ │
│ Annotation Tem…↗ ││ │ Scalp ⊘  │ Scalp│ Female │  6    │  ns →]│ │
└──────────────────┘└──────────────────────────────────────────────┘
```

"Design areas →" opens `derma-body-template-editor` with the template name, so the designer's
`?template=` requirement (`bundle.jsx:111`) is always satisfied. The row action says *area*, not
*region*, because `CONTEXT.md` retires *region* in new UI copy:

```js
window.location.assign(`/app/derma-body-template-editor?template=${encodeURIComponent(template.name)}`)
```

New `data-test` hooks, designed up front because the Playwright specs select on them. **No existing
`data-test` attribute is renamed.**

| Hook | On |
|---|---|
| `derma-config-root` | the page shell |
| `config-rail-item-<tool>` | each rail item, plus `config-rail-item-annotation-templates` for the outbound link |
| `config-loading` / `config-error` / `config-partial` | load states, `config-partial` naming the degraded sections |
| `config-body-templates` / `config-body-templates-empty` | the panel and its empty state |
| `config-body-template-row` | one per template, carrying `data-template="<name>"` |
| `config-body-template-disabled` | the retired badge |
| `config-area-count` / `config-retired-area-count` | the two counts |
| `config-design-areas` / `config-new-body-template` | the row action and the header action |
| `config-placeholder` | a rail item whose panel has not shipped yet |

Phase 2 adds, on the same rule (nothing renamed):

| Hook | On |
|---|---|
| `config-procedure-templates` / `config-procedure-templates-empty` | the panel and its empty state |
| `config-procedure-template-row` | one per template, carrying `data-template="<name>"` |
| `config-procedure-template-disabled` | the retired badge |
| `config-required-field` | one chip per required field, carrying `data-source="<owner>"` and `data-enforced="0|1"` |
| `config-template-warning` | one badge per warning, carrying `data-warning="<code>"` |
| `config-template-warning-count` | the header roll-up |
| `config-variable-count` / `config-edit-procedure-template` | the count and the desk-form link |
| `config-categories` / `config-categories-empty` / `config-categories-note` | the panel, its empty state, the footnote |
| `config-category-row` | one per category, carrying `data-category="<name>"` |
| `config-category-disabled` / `config-category-template-count` | the retired badge and the usage count |
| `config-category-unread-field` | one badge per field nothing reads, carrying `data-field="<fieldname>"` |

Phase 3 adds these and **removes `config-placeholder`**, which named a state that no longer exists
once every rail item has a panel:

| Hook | On |
|---|---|
| `config-readiness` | the panel |
| `config-readiness-enforcement` | the mode, carrying `data-mode="Warn\|Block"` |
| `config-readiness-todo-downgrade` | the ToDo rule, carrying `data-enabled="0\|1"` |
| `config-readiness-warning` | one badge per warning, carrying `data-warning="<code>"` |
| `config-feature-toggle` / `config-feature-toggles-empty` | one row per toggle (`data-toggle`, `data-enabled`) and the degraded state |
| `config-edit-derma-settings` | the desk-form link |

### 5. Discoverability

`derma_sidebar.js` gains `do_derma.openConfig()` alongside the existing `openChart`, following the
same shape (no context resolution needed — it just routes). The file is already in
`app_include_js` (`hooks.py:14-17`), so nothing new is loaded globally. **This lands in Phase 4**,
with the sidebar item that calls it — a function nothing calls is dead code until then.

**What stays unchanged:** `DermaChart.vue`, `derma_chart.bundle.js`, every existing endpoint, the
`Page` rows for the two existing pages, and the whole permission model.

## Security

- `get_derma_config_overview` is a new whitelisted endpoint and **calls `_ensure_clinical_access()`
  first**, before any read. `TestClinicalAccessGate` gains a case proving a user without a clinical
  role gets `frappe.PermissionError`.
- The endpoint returns configuration, not patient data — no `Patient`, `Patient Encounter` or
  `Derma Chart Mark` row is read.
- The page row keeps `"roles": []`, consistent with the two existing pages; the API gate is the
  boundary, as `CLAUDE.md` states.
- All values render through Vue templates, which escape by default. Nothing on this page is
  rendered with `v-html`.

## Acceptance Criteria

1. `/app/derma-config` loads and shows the rail with four tools plus the outbound Annotation
   Templates link.
2. The body-template table lists every template including disabled ones, with area counts.
3. "Design areas →" opens the designer already loaded with that template — no manual URL.
4. A user without a clinical role calling `get_derma_config_overview` gets a `PermissionError`.
5. One failing sub-query (e.g. a site with no `Derma Procedure Category` doctype) leaves the other
   panels rendered.
6. The page survives a site missing any `custom_derma_*` field.
7. `ensure_derma_config_page` is re-runnable and does not move `modified` on an unchanged row.
8. **No regression:** the chart page and the designer page still load, and no existing `data-test`
   attribute changed.

## Phases

**Phase 1 — shell plus the body-template table.** ✅ Shipped 2026-08-16. Page row, patch, bundle,
rail, `get_derma_config_overview` returning body templates only, and the working "Design areas"
button. Also ships `ensure_derma_body_template_editor_page`.
*Exit:* an administrator reaches any body map's designer in two clicks, having typed no URL.

**Phase 2 — procedure templates and categories panels (read-only).** ✅ Shipped 2026-08-16. Lists
with the config each row actually carries, including a warning count for templates with no required
fields.
*Exit:* the four defects in the required-field story are visible on screen without opening a desk
form.

**Phase 3 — readiness panel mount point and settings surface.** ✅ Shipped 2026-08-16. The panel
spec 4 fills; here it shows the current enforcement mode read-only, plus the feature toggles.
*Exit:* every rail item leads somewhere real.

**Phase 4 — health counts on the rail.** Per-tool warning badges, plus the sidebar entry point.
*Exit:* the rail shows what needs attention before you click into it.

## Open Questions

- **Should the page be restricted to administrators?**
  *Default:* no. Keep `"roles": []` like the other two pages; the API gate is the boundary. Revisit
  if a clinic asks.
- **Does "+ New template" create inline or route to the desk form?**
  *Default:* route to the desk `new` form in Phase 1; inline creation is a later pass.
- **Does the config page need patient/appointment context?**
  *Default:* no. It never reads `frappe.route_options`, unlike `App.vue` in the chart.
- **Where does the Annotation Template link point?**
  *Default:* the do_health desk list view, opened in the same tab.

## Reconciliation — what changed vs the plan

### Phase 1 (2026-08-16)

- **"Design areas" navigates with `window.location.assign`, not `frappe.set_route`.** The plan's
  `frappe.set_route("derma-body-template-editor", { template: name })` cannot work: the router
  stores a plain-object argument in `frappe.route_options` and re-encodes it as
  `key=encodeURIComponent(JSON.stringify(value))` (`frappe/public/js/frappe/router.js:368-371`), so
  a string arrives as `?template=%22Face%20Map%22` — quoted. The designer reads it raw with
  `new URLSearchParams(window.location.search).get("template")`
  (`public/js/body-template-editor/body-template-editor.bundle.jsx:111`) and would look up a
  template whose name includes the quotes. An `<a href>` is no better: the router's own click
  handler (`router.js:26-70`) funnels it through the same encoder. A literal navigation to
  `/app/derma-body-template-editor?template=<encoded>` is the one form the designer already
  understands — it is how the page is opened by hand today. Cost: a full desk reload on that click.
- **The page-row patch logic moved into `do_derma/patches/helpers.py::ensure_standard_page`**, and
  `ensure_derma_chart_page` was refactored onto it. The plan said "`ensure_derma_chart_page.py` with
  the name changed", which would have meant three copies of the converge-field-by-field loop.
  Rewriting an already-applied patch is safe — patches run once and this one is idempotent either
  way.
- **Every Vue component in the bundle declares `const __ = window.__ || ((txt) => txt)`.** Without
  it the page mounted to a blank main section with `_ctx.__ is not a function`: Vue's template
  compiler emits `_ctx.__` for an identifier it does not recognise as a global. `DermaChart.vue:615`
  already does exactly this; the plan did not mention it because it reads as boilerplate. Found by
  the Playwright spec, not by review.
- **Three panels are a shared inline placeholder, not four `panels/*.vue` files.** Only
  `BodyTemplatesPanel.vue` exists; Procedure Templates, Categories and Readiness render "This tool
  arrives in a later pass" until their phase lands. Writing three empty components now is the
  speculative generality the repo's rules forbid.
- **`get_derma_config_overview` returns `errors` alongside `body_templates`.** `_safe_derma_context`
  takes an accumulator list, and the page needs it to show which section failed — otherwise a broken
  sub-query is indistinguishable from an empty one. `test_a_broken_sub_query_degrades_to_an_empty_list`
  proves the degraded section itself; with one section in the payload it cannot yet prove the *other*
  panels survive, so the second half of acceptance criterion 5 lands with Phase 2.
- **`get_config_body_templates` is a dedicated public read, not a reuse of `_get_body_templates`.**
  The plan asked it to reuse the chart's reader with an `include_disabled` flag. That reader is
  capped at `limit=100` templates and `_attach_body_template_parts` at `limit=1000` parts *across
  all templates*, so a large clinic would see silently wrong area counts — the one number this page
  exists to show. It now reads `Derma Body Template` unfiltered with `limit_page_length=0` and
  counts areas in `_count_template_areas`, which reads only `body_template` + `disabled`. Side
  benefit: no `regions_json`, `shape_json` or hydrated variables cross the wire for a table that
  renders none of them. `_get_body_templates` is left exactly as spec 1 left it.
- **`test_it_recreates_a_deleted_row` skips under `developer_mode`.** Deleting and re-inserting a
  source-backed `Page` writes the JSON back to the app folder on a developer-mode site, which
  rewrote `derma_config.json` with fresh timestamps mid-test. The patch only exists for sites
  without developer mode, so skipping there is honest rather than a workaround.
- **`+ New template` calls `frappe.new_doc("Derma Body Template")`** (Open Question 2's default,
  routed rather than inline), and the rail's outbound Annotation Templates link is a plain
  `/app/annotation-template` href.
- **The row action is "Design areas", not "Design regions"** (`data-test="config-design-areas"`).
  `CONTEXT.md` retires *region* in favour of *Area*, and the column two cells to its left already
  said "Areas". Caught in review before any spec depended on the old hook.
- **The gate case lives in `TestClinicalAccessGate`** (`tests/test_api.py`) as
  `test_config_overview_is_gated`, where `CLAUDE.md` says the gate's regression coverage belongs —
  not in a second access-control class inside `test_config_workspace.py`, which is where it was
  first written.
- **`do_derma.openConfig()` is not shipped.** It is Phase 4's, together with the sidebar item that
  calls it; adding it now would have been an exported function with no caller.

### Phase 2 (2026-08-16)

- **Required fields are returned per field with their owner, not as a flat set.** The plan asked
  only for "a warning count for templates with no required fields". A count says a template is
  under-configured but not *which of the four owners* put a field there, which is the thing spec 3
  is about to collapse into one owner. `_required_field_owners` is now the **single** definition of
  that order — `_get_template_variables` was refactored onto it (`required = [owner["fieldname"]
  for owner in _required_field_owners(row)]`), which deleted the now-unused `_merge_required_fields`
  and removed the risk of the panel and the chart drifting apart.
- **Each field also carries `enforced`, because owning a field is not the same as enforcing it.**
  `_get_template_variables:863-870` appends a required fieldname only when `_default_derma_variable`
  recognises it, and `_validate_marks_ready_for_procedure:3220` throws on that resolved list — so an
  invented fieldname in `custom_derma_required_fields` is required *nowhere*. Conversely
  `_parse_template_variable_schema` honours a row-level `"required": true`, which the chart does
  enforce though none of the four owners claims it; that field is reported with the source
  `variables_json`. `_required_fields_with_owners` reconciles the two lists and a new
  `unenforced_required_fields` warning names the first case. Both were silent before this panel.
- **`variable_count` is the chart's list, not the JSON's length.** A required field with no row of
  its own still reaches the clinician as a default variable, so counting the raw JSON would print a
  number nobody sees. The `unreadable_variables` check still reads the raw JSON, so an unreadable
  schema and a non-zero count can (correctly) appear on the same row.
- **Warnings are codes, not sentences.** `no_required_fields`, `category_name_defaults`,
  `unenforced_required_fields`, `unreadable_variables` cross the wire; the panel maps them
  through `__()`. Server-side English in
  a payload cannot be translated, and the Playwright specs select on `data-warning="<code>"`, which
  a copy edit would otherwise break.
- **`unreadable_variables` is inferred, not reported by the parser.** `_parse_template_variable_schema`
  swallows every malformed shape and returns `[]`, and changing that is spec 3's business (its
  Non-Goals keep the tolerated shapes). `_is_unreadable_variable_schema` therefore compares a
  non-empty raw value against a zero-length parse, excluding `[]`, `{}` and `null` as honest empties.
- **The derma-template predicate was extracted rather than duplicated.** `_get_derma_procedure_templates`
  and `get_config_procedure_templates` now share `_is_derma_template`, so the config list can never
  drift from the chart's definition of "a derma template". The predicate is unchanged: a category,
  a marker behaviour, or a required-fields value.
- **The two safety flags' field lists became `PRODUCT_TRACKING_REQUIRED_FIELDS` /
  `DEVICE_SETTINGS_REQUIRED_FIELDS`.** They were literals inside `_get_template_variables`; the
  owner walk needs the same lists, and two copies of `["device", "settings"]` is one owner too many.
- **Categories report `unread_fields`, a list, rather than a boolean.** `CATEGORY_UNREAD_FIELDS`
  names the five requirement fields nothing branches on, and the panel badges each one that carries
  a value plus a footnote saying so. `required_fields` is a JSON field, so it is tested through
  `_parse_required_fields` — a stored `"[]"` is an honest empty, not a value — while the four Check
  fields are tested with `cint`. Spec 3 deletes all five; `_select_existing_fields` means this list
  degrades to `[]` on the day it does, with no code change here.
- **`template_count` includes retired templates**, which still point at the category and still break
  if it is deleted. Said in the function's docstring rather than left to the reader.
- **`settings` is not in the payload.** The Design sketch listed `get_feature_toggles()`; the
  readiness panel that would render it is Phase 3, and shipping an unread key now would be a field
  with no reader.
- **The procedure row links to the desk form (`config-edit-procedure-template`).** Phase 2 is
  read-only, and until spec 3's builder lands the desk form is the only place to *fix* what this
  panel exposes — the same "navigate to the tool" shape as Phase 1's "Design areas".
- **Acceptance criterion 5 is now fully proven.** `test_one_broken_section_leaves_the_others_readable`
  breaks the procedure-template query and asserts both other sections still render, which Phase 1's
  single-section payload could not express.
- **The e2e fixture creates a `Clinical Procedure Template` and deletes its generated `Item`.**
  healthcare's `after_insert` builds an Item from `item_code`, so the spec cleans up both. The
  category-name defect is *not* covered in the browser: `Derma Procedure Category` autonames from
  its title, so proving it would mean creating a row literally named `Botox` on a production-clone
  dev site — and deleting it afterwards could remove a real one. `test_warns_when_requirements_come_from_the_category_name`
  covers it in the integration suite, where the transaction rolls back.

### Phase 3 (2026-08-16)

- **The panel names the gate, not just the mode.** The plan asked only for "the current enforcement
  mode read-only". On this site there *is* no enforcement: spec 4's `blocker_enforcement` field does
  not exist yet and `complete_derma_session` (`api.py:3028`) consults no readiness engine, so the
  only gate is `DermaChart.vue:2131`. Printing "Warn" alone would read as a server setting a clinic
  had chosen. `get_config_readiness` therefore carries `is_configurable` and a
  `completion_gate_is_client_side` warning, on Phase 2's warning-code convention — codes cross the
  wire, the panel maps them through `__()`.
- **`get_readiness_settings()` landed in `do_derma/settings.py` now, ahead of spec 4's Phase 2.**
  Spec 4 assigns that function to `settings.py` as the singleton's single owner. Reading the
  singleton from `api.py` instead would have created a second owner that spec 4 would then have to
  delete. It is field-existence-defensive via `doc.meta.has_field`, the same shape as
  `_has_field` — `settings.py` cannot import `api.py`, which imports it. Both defaults (`Warn`,
  downgrade on) are today's behaviour, so the day spec 4 adds the fields nothing gets stricter.
- **The feature toggles render here rather than in a fifth rail item.** Phase 2 deferred them
  ("shipping an unread key now would be a field with no reader"); they are the other thing
  `Derma Settings` holds, and a rail item for three checkboxes is a click for its own sake. They
  ride inside the `readiness` payload as `feature_toggles`, so the panel takes one prop and one
  `_safe_derma_context` wrapper covers the whole section.
- **`config-placeholder` is deleted, not left dangling.** With four panels shipped no rail item is
  unrouted, so the placeholder branch in `App.vue` is dead code. `config-workspace.spec.ts:73`
  moved to `config-readiness` in the same commit — the one `data-test` hook this spec has ever
  removed, and it named a state that can no longer occur.
- **No `Derma Settings` field, no patch, no migration.** Editing the mode is spec 4's Phase 2; this
  panel links to the desk form (`config-edit-derma-settings`), the same "navigate to the tool"
  shape as Phase 1's "Design areas" and Phase 2's "Edit".
- **`settings.py` pre-declares spec 4's fieldnames** (`blocker_enforcement`,
  `todo_downgrades_blockers`) and, since no site has them, only the fallback branch runs. Spec 4's
  Design §3 is the source of those names and now records the dependency; if it renames a field, this
  reader silently reports "not configurable" forever, so the rename has to travel with
  `settings.py`. `get_readiness_settings()` returns a **dict**, not the attribute-style object spec 4
  sketched.
- **Post-review changes.** `is_configurable` was dropped from the wire — the panel reads only
  `warnings`, and Phase 2's own rule forbids shipping a key with no reader; `warningLabel` /
  `sourceLabel` were collapsed into `config/labels.js::labelFor`, shared by both panels, at the
  second copy; and a **degraded readiness section now renders `—` for the ToDo rule** rather than
  "Still blocks", because `_safe_derma_context`'s `{}` fallback knows nothing and the old render
  asserted the stricter answer.

## Verification

### Phase 1

Integration (Frappe's runner, real site with `healthcare` + `do_health`):

```
bench --site dermaone.localhost run-tests --module do_derma.tests.test_config_workspace
→ Ran 6 tests, OK (skipped=1)
bench --site dermaone.localhost run-tests --module do_derma.tests.test_api
→ Ran 43 tests, OK
bench --site dermaone.localhost run-tests --app do_derma
→ Ran 130 tests in 24.8s, OK (skipped=1)
```

`test_config_workspace.py` covers: a disabled template appearing in the list, live vs retired area
counts, a template with no areas, the degraded sub-query path with its `errors` entry, and both page
patches being re-runnable without moving `modified`. The access gate is
`TestClinicalAccessGate.test_config_overview_is_gated` in `test_api.py`, which proves
`_ensure_clinical_access()` runs before any read.

Browser (Playwright, on fixtures the spec plants itself):

```
npx playwright test e2e/tests/config-workspace.spec.ts → 4 passed
npx playwright test                                    → 75 passed (9.5m)
```

`config-workspace.spec.ts` proves the disabled template is listed with its badge and a zero area
count, that "Design areas" lands on `[data-test="body-map-designer"]` with `?template=` set to the
exact name, and that each of the four rail items swaps the panel while the outbound Annotation
Templates link keeps its `/app/annotation-template` href (acceptance criterion 1).

Migrate and lint:

```
bench --site dermaone.localhost migrate    → clean; Page rows now derma-chart,
                                             derma-body-template-editor, derma-config
bench build --app do_derma                 → derma_config.bundle.js 258.86 Kb, .css 2.74 Kb
pipx run ruff check <changed files>        → All checks passed
pipx run ruff format --check               → 21 files already formatted
```

**Not yet run:** nothing for Phase 1.

### Phase 2

Integration:

```
bench --site dermaone.localhost run-tests --module do_derma.tests.test_config_workspace
→ Ran 22 tests, OK (skipped=1)
bench --site dermaone.localhost run-tests --app do_derma
→ Ran 146 tests in 41.7s, OK (skipped=1)
```

The 16 new cases cover: the owner of every required field across all four groups, first-owner-wins
on a field two owners claim, a required field the chart cannot enforce, a field the variables JSON
alone marks required, the category-name warning, the requires-nothing warning, the unreadable-JSON
warning and its readable counterpart, the variable count matching the chart's list, a disabled
template and a disabled category being listed, the per-category template count, the unread-field
flags with an empty `required_fields` excluded, and one broken section leaving the other two
readable.

Browser:

```
npx playwright test e2e/tests/config-workspace.spec.ts → 9 passed
npx playwright test                                    → 79 passed, 1 failed (10.3m)
```

The one failure is `annotation-anchoring.spec.ts:228` ("keeps a dragged treatment area at its drawn
size across resume"), which fails on `render_chart_marks` where it expects no console error. It is
**not** this phase's: re-running it with the whole change stashed reproduces it on `a72a0ae`. Phase
2 touches no chart code.

Build and lint:

```
bench build --app do_derma          → derma_config.bundle.css 3.32 Kb (JS unchanged in name)
pipx run ruff check do_derma/       → All checks passed
pipx run ruff format                → clean
```

**Not yet run:** `bench migrate` — Phase 2 ships no patch, no fixture and no schema change.
Phases 3-4 are unimplemented.

### Phase 3

Integration:

```
bench --site dermaone.localhost run-tests --module do_derma.tests.test_config_workspace
→ Ran 27 tests, OK (skipped=1)
bench --site dermaone.localhost run-tests --app do_derma
→ Ran 157 tests in 24.2s, OK (skipped=1)
```

The 11 new cases cover: the enforcement mode and its types, the client-side-gate warning, a
configured site reporting `Block` with no warning, every feature toggle reaching the payload, a
broken readiness read leaving the lists intact, and — in `test_settings.py` — the four fallbacks
(`get_readiness_settings` with the fields absent, with an unreadable singleton, with an unknown
mode, and with the downgrade field absent), the configured path, and this site answering all three
keys whatever its schema. Only that last one reads the real singleton; the rest fake it, so none
of them changes meaning the day spec 4 adds the fields.

Browser:

```
npx playwright test e2e/tests/config-workspace.spec.ts → 11 passed (19.6s)
```

The two new specs prove the readiness panel reports a mode, the ToDo rule and all three toggles,
and that it names the client-side gate. The rail spec now expects `config-readiness` where it
expected `config-placeholder`.

Build and lint:

```
bench build --app do_derma          → derma_config.bundle.js 279.28 Kb, .css 4.24 Kb
pipx run ruff check do_derma/       → All checks passed
pipx run ruff format --check        → 76 files already formatted
```

**Not yet run:** `bench migrate` — Phase 3 ships no patch, no fixture and no schema change. The
full Playwright suite was not re-run; Phase 3 touches only the config bundle, and the one known
failure (`annotation-anchoring.spec.ts:228`) predates it. The panel's own degraded render (the
`—` fallbacks when `readiness` comes back `{}`) is proven by reading the component, not by a
browser spec — forcing a server-side section failure from Chromium would need a fixture that
breaks the endpoint for every other spec in the run. Phase 4 is unimplemented.

## Files to touch (summary)

| File | Change |
|---|---|
| `do_derma/do_derma/page/derma_config/derma_config.json` | *(new)* |
| `do_derma/do_derma/page/derma_config/derma_config.js` | *(new)* |
| `public/js/config/derma_config.bundle.js` | *(new)* |
| `public/js/config/derma_config.bundle.css` | *(new)* |
| `public/js/config/App.vue` | *(new)* rail + panel switch |
| `public/js/config/panels/BodyTemplatesPanel.vue` | *(new)* |
| `public/js/config/panels/ReadinessPanel.vue` | *(new, Phase 3)* enforcement mode, ToDo rule, feature toggles |
| `public/js/config/panels/ProcedureTemplatesPanel.vue` | *(new, Phase 2)* required-field owners and warnings |
| `public/js/config/panels/CategoriesPanel.vue` | *(new, Phase 2)* usage counts and unread requirement fields |
| `do_derma/api.py` | `get_derma_config_overview` + `_config_body_templates`; Phase 2 adds `get_config_procedure_templates`, `get_config_categories`, `_required_field_owners`, `_is_derma_template` and the two safety-flag constants; Phase 3 adds `get_config_readiness` |
| `do_derma/settings.py` | *(Phase 3)* `get_readiness_settings` — the singleton's single owner, ahead of spec 4 |
| `do_derma/tests/test_settings.py` | *(Phase 3)* the readiness-settings fallbacks |
| `do_derma/patches/helpers.py` | *(new)* `ensure_standard_page`, shared by the three page patches |
| `do_derma/patches/ensure_derma_config_page.py` | *(new)* |
| `do_derma/patches/ensure_derma_body_template_editor_page.py` | *(new)* — never existed |
| `do_derma/patches/ensure_derma_chart_page.py` | refactored onto `ensure_standard_page` |
| `do_derma/patches.txt` | two entries |
| `public/js/derma_sidebar.js` | `do_derma.openConfig()` — Phase 4, not shipped yet |
| `do_derma/tests/test_config_workspace.py` | *(new)*; Phase 2 adds the procedure-template and category classes |
| `e2e/tests/config-workspace.spec.ts` | *(new)*; Phase 2 adds the configuration-lists describe block |
| `e2e/helpers/derma.ts` | Phase 2 adds `SEED.itemGroup`, so no spec hardcodes the seeded item group |
| `public/js/config/derma_config.bundle.css` | Phase 2 adds the chip and warning-badge styles |

`bench build --app do_derma` is **required** — a new bundle name,
`derma_config.bundle.js`, joins the `frappe.require` contract. No existing bundle filename changes.
