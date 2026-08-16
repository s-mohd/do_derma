# A Place To Configure Derma

Date: 2026-08-16
Status: **Phase 1 implemented & verified** (2026-08-16); Phases 2-4 remain **Draft**. Phase 1
deviated from the plan on how the designer is opened and on where the page-row patch logic lives —
see [Reconciliation](#reconciliation--what-changed-vs-the-plan) and [Verification](#verification).

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
		"procedure_templates": _config_procedure_templates(),
		"categories": _get_categories(),
		"settings": get_feature_toggles(),
	}
```

`get_config_body_templates()` queries `Derma Body Template` unfiltered and unlimited and carries an
`area_count` plus a `retired_area_count` per template (see
[Reconciliation](#reconciliation--what-changed-vs-the-plan) — it does *not* reuse
`_get_body_templates`, whose `limit=100` / `limit=1000` would silently under-count).
`_config_procedure_templates()` reuses `_select_existing_fields` over `DERMA_TEMPLATE_FIELDS` so a
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

**Phase 2 — procedure templates and categories panels (read-only).** Lists with the config each
row actually carries, including a warning count for templates with no required fields.
*Exit:* the four defects in the required-field story are visible on screen without opening a desk
form.

**Phase 3 — readiness panel mount point and settings surface.** The panel spec 4 fills; here it
shows the current enforcement mode read-only.
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

**Not yet run:** nothing for Phase 1. Phases 2-4 are unimplemented.

## Files to touch (summary)

| File | Change |
|---|---|
| `do_derma/do_derma/page/derma_config/derma_config.json` | *(new)* |
| `do_derma/do_derma/page/derma_config/derma_config.js` | *(new)* |
| `public/js/config/derma_config.bundle.js` | *(new)* |
| `public/js/config/derma_config.bundle.css` | *(new)* |
| `public/js/config/App.vue` | *(new)* rail + panel switch |
| `public/js/config/panels/BodyTemplatesPanel.vue` | *(new)*; the other three panels land with their phases |
| `do_derma/api.py` | `get_derma_config_overview` + `_config_body_templates`; `_get_body_templates(include_disabled)` |
| `do_derma/patches/helpers.py` | *(new)* `ensure_standard_page`, shared by the three page patches |
| `do_derma/patches/ensure_derma_config_page.py` | *(new)* |
| `do_derma/patches/ensure_derma_body_template_editor_page.py` | *(new)* — never existed |
| `do_derma/patches/ensure_derma_chart_page.py` | refactored onto `ensure_standard_page` |
| `do_derma/patches.txt` | two entries |
| `public/js/derma_sidebar.js` | `do_derma.openConfig()` — Phase 4, not shipped yet |
| `do_derma/tests/test_config_workspace.py` | *(new)* |
| `e2e/tests/config-workspace.spec.ts` | *(new)*, on `demo_seed` fixtures |

`bench build --app do_derma` is **required** — a new bundle name,
`derma_config.bundle.js`, joins the `frappe.require` contract. No existing bundle filename changes.
