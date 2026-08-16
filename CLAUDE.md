# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`do_derma` is a **Frappe app** providing dermatology charting and encounter workflows. It is not standalone — it must be run from inside a Frappe bench, and it reads/writes doctypes owned by `healthcare` (ERPNext Healthcare) and `do_health`.

This checkout lives at `apps/do_derma` inside the bench at `/Users/hameed/Developer/bench-v16` (webserver port 8002, sites `dermaone.localhost` and `dermaone2.localhost`, `developer_mode: 1`).

[`CONTEXT.md`](CONTEXT.md) fixes the domain vocabulary — Body Template, Mark, Annotation, Assessment Mode, encounter- vs procedure-anchored — with an *Avoid* list per term. Use those words in code, UI copy, and specs; check it before naming anything new.

## Commands

All commands run from the **bench root** (`/Users/hameed/Developer/bench-v16`), not from this app directory.

```bash
# Apply schema changes + run patches.txt
bench --site dermaone.localhost migrate

# Build JS/CSS bundles (esbuild). Required after touching anything in public/js/
bench build --app do_derma
bench watch                       # rebuild on change during development

# Tests (Frappe's unittest runner — do NOT introduce pytest)
bench --site dermaone.localhost run-tests --app do_derma
bench --site dermaone.localhost run-tests --module do_derma.tests.test_api
bench --site dermaone.localhost run-tests --module do_derma.tests.test_api \
  --test TestSaveChartMark.test_round_trips_position_and_patient

# Interactive debugging against live data
bench --site dermaone.localhost console

# Lint / format (ruff config in pyproject.toml — tabs, double quotes, line-length 110)
ruff check apps/do_derma && ruff format apps/do_derma
```

Python tests are `IntegrationTestCase` subclasses — they need a real site with `healthcare` and `do_health` installed, and they create real Patients/Encounters. There is no unit-test-only path.

The browser suite is a second stack and runs from **this app directory**, not the bench root:

```bash
# once per machine
yarn install && npx playwright install chromium

yarn test:e2e          # headless
yarn test:e2e:headed   # watch it drive the browser
yarn test:e2e:ui       # Playwright UI mode
yarn test:e2e:debug    # step through
```

Its fixtures are planted once per site by a bench command (idempotent, safe to re-run), and the bundles must be current or the specs select on stale `data-test` hooks:

```bash
bench --site dermaone.localhost execute do_derma.e2e_seed.setup_e2e_data
bench build --app do_derma
```

### Demo data for clicking around

`e2e_seed.py` is deliberately minimal — 40 specs assert exact counts against it, so anything added there to make manual testing nicer breaks them. Manual/demo data is a **separate** seeder, prefixed `DEMO ` so the two sets can never be confused:

```bash
bench --site dermaone.localhost execute do_derma.demo_seed.setup_demo_data
bench --site dermaone.localhost execute do_derma.demo_seed.teardown_demo_data
```

It builds one patient (`DEMO Amina Haddad`) part-way through a course of treatment: three visits (one SOAP-documented, one Structured, today's unstamped), seven marks across all three placement behaviours, five procedure templates, two Clinical Procedures, a Before/After photo set, two findings, and a drawing on each anchor. Both commands are idempotent and print a JSON summary. Clinical rows are written through the real endpoints, so a broken endpoint fails the seed instead of producing data the chart cannot read.

## Dependency model (important)

`hooks.py` deliberately does **not** declare `required_apps`. `healthcare` and `do_health` are hard runtime dependencies but this bench's installer misreads local app names as remote tags, so the dependency is documented rather than enforced. `do_derma` also talks to `Health Annotation` / `Health Annotation Table` (do_health) **directly** — it does not depend on the separate `annotation` app.

The only hard Python import across apps is `do_health.api.appointment_methods.create_encounter_for_appointment`. Everything else is reached via `frappe.get_doc` / `frappe.get_all` on doctype names, guarded by existence checks.

## Backend architecture (`do_derma/api.py`)

One ~3.5k-line module holds every whitelisted endpoint. Two conventions govern it:

**1. Every `@frappe.whitelist()` function calls `_ensure_clinical_access()` first.** Many writes below use `ignore_permissions=True` because DocPerms are inconsistent across the three apps (e.g. `Health Annotation` grants only System Manager). That role check against `CLINICAL_ACCESS_ROLES` *is* the authorization boundary for this module. Adding an endpoint without it silently opens patient data to any authenticated user — the regression test `TestClinicalAccessGate` exists for this.

**2. Schema-defensive reads.** The same code runs against sites where a given custom field or doctype may or may not exist. Never assume a field is present:

- `_has_doctype(dt)` / `_has_field(dt, fieldname)` before touching optional schema
- `_select_existing_fields(dt, FIELDS)` to build `frappe.get_all` field lists from the `DERMA_*_FIELDS` constants
- `_safe_derma_context(label, fallback, getter)` to wrap a chart-context section so one broken sub-query logs and degrades instead of blanking the whole chart

Context resolution funnels through `_get_visit_context(patient|appointment|encounter)`, which back-fills the other two identifiers and creates a draft `Patient Encounter` when needed via `_ensure_encounter`. Endpoints accept any of the three and normalize.

## Data model

Own doctypes (`do_derma/do_derma/doctype/`) all key off `patient` + `appointment` + `encounter`:

- **Derma Chart Mark** — the hub. One mark on a body template; links to `clinical_procedure`, `finding`, `treatment_entry`, `annotation`, `photo_set`, plus product/dose/device detail fields. Most workflows converge here.
- **Derma Finding** / **Derma Treatment Entry** — clinical detail rows
- **Derma Photo Set** (parent of child **Derma Photo**) — before/after evidence
- **Derma Body Template** (+ child **Derma Body Template Part**, **Derma Template Part Variable**) — the body maps drawn on
- **Derma Procedure Category**, **Derma Template Set**, **Derma Chart Template** — configuration

Procedure behaviour is configured on **`Clinical Procedure Template` custom fields** (`custom_derma_category`, `custom_derma_variables_json`, `custom_derma_marker_behavior`, `custom_derma_required_fields`, …) — see `DERMA_TEMPLATE_FIELDS`. Those custom fields are shipped as `fixtures` filtered on `module = "Do Derma"`, and some are created/repaired by patches.

Annotations are do_health `Health Annotation` docs, attached via a `custom_annotations` child table (`Health Annotation Table`) on `Patient Encounter` and `Clinical Procedure`.

### Annotation → mark fan-out

`_sync_chart_marks_for_annotation` is the trickiest contract in the codebase. On each annotation save it walks the Excalidraw scene, finds elements tagged with a `customData.procedure` template, converts their centroids to percentages relative to the body-template element, and upserts one `Derma Chart Mark` per element. Idempotency comes from storing the Excalidraw `element_id` in the mark's `annotation_json` — re-saving updates in place. Marks already promoted to a real `Clinical Procedure` are never auto-deleted. Marks stamped in real time (`onMarkPlaced`) already exist and are only re-linked. Preserve all four of those properties when editing.

## Printing (`do_derma/printing/`)

`Patient Encounter` print formats are hand-written Jinja owned by other parties — `Encounter Print` is standard and belongs to `healthcare`; `Encounter print (Dr Sadiq)` is a site-only row. do_derma ships **no print format of its own**. Instead:

- `printing/render.py` registers the Jinja global `derma_assessment_html(doc)` via the `jinja` hook. It renders the assessment through `assessment.get_layout()`, so the clinic-configurable Structured field list has one owner. **Every value is escaped here** — Frappe's print Jinja environment does not autoescape.
- `printing/inject.py` writes a marker-delimited (`<!-- do_derma:assessment:start/end -->`) call to that global into every enabled, non-builder `Patient Encounter` format, from `after_migrate`. Idempotent: an unchanged format is not written at all, so `modified` does not move. A format with a foreign HTML comment after the marker is skipped and logged rather than rewritten.

Because `Encounter Print` is standard, a `healthcare` release that edits its JSON reverts the injected block; `after_migrate` re-injects on the next migrate. That is why this is not a patch.

## Frontend architecture

Two Frappe desk pages under `do_derma/do_derma/page/`, each a thin `on_page_show` bootstrap that `frappe.require`s a bundle:

| Page | Route | Stack | Entry |
|---|---|---|---|
| Derma Chart | `/app/derma-chart` | Vue 3 | `public/js/chart/derma_chart.bundle.js` → `App.vue` → `DermaChart.vue` |
| Derma Body Map Designer | `/app/derma-body-template-editor` | React + Excalidraw | `public/js/body-template-editor/body-template-editor.bundle.jsx` |
| Derma Configuration | `/app/derma-config` | Vue 3 | `public/js/config/derma_config.bundle.js` → `App.vue` → `panels/*.vue` |

Frappe's esbuild treats any `*.bundle.{js,jsx,css}` under `public/js/` as an entrypoint and emits to `public/dist/` (gitignored). Bundle filenames are the contract with `frappe.require` — renaming one breaks the page.

`DermaChart.vue` (~2.8k lines) is the shell: `SECTION_TABS` (Clinical Notes / Photos / Prescription / Consent / Review) plus a lazily-loaded workspace tab set (`procedure_history`, `assessment`, `prescriptions`, `anesthesia`, `consents`) — see `ensureSectionData` / `ensureWorkspaceTab`. Sub-panels live in `public/js/chart/components/*.vue`.

**Vue hosts React**: the drawing surface is React. `DermaChart.vue` calls `openDermaAnnotationStudio()` from `annotation/DermaAnnotationStudio.jsx`, which mounts its own `createRoot` overlay wrapping `excalidraw/EmbeddedExcalidraw.jsx`. Excalidraw itself is dynamically `import()`ed after shimming `process.env.NODE_ENV`.

Patient context flows in from the host app, not from props: `App.vue` reads `frappe.route_options` and subscribes to `window.do_health.patientWatcher` / `window.doHealthSidebar`. `public/js/derma_sidebar.js` (loaded globally via `app_include_js`) exposes `do_derma.openChart()`, which calls `ensure_chart_context` then routes to `derma-chart`.

## End-to-end tests

`playwright.config.ts` sits at the app root, specs live under `e2e/{tests,helpers,pages}`, and fixtures are planted by `do_derma/e2e_seed.py` through `bench execute`. An `auth.setup.ts` project logs in once and writes `e2e/.auth/{user,csrf}.json` — gitignored, never commit it. `fullyParallel: false` / `workers: 1` because every spec shares the one seeded fixture set. `e2e/README.md` carries the long form.

Four contracts to preserve:

- **`data-test` attributes are the selector contract** — 59 of them across the Vue components (`derma-chart-root`, `section-tab-*`, `consent-panel`, …). Renaming or dropping one breaks specs silently, and an un-rebuilt bundle still serves the old ones.
- **Two base URLs, deliberately.** Node cannot resolve `.localhost` TLDs, so API calls go to `127.0.0.1` with an explicit `Host` header while the browser uses Chromium's `--host-resolver-rules`. That is also why `helpers/frappe.ts` attaches session cookies and the CSRF token by hand instead of trusting the `request` fixture's cookie jar.
- **Never wait on `networkidle`.** The Vue bundle is lazily `frappe.require`d inside `on_page_show` and the desk holds long-poll sockets open forever. Wait on a `data-test` element — `ChartPage.open()` does.
- **The chart does not reliably open on Clinical Notes.** The active section is persisted under `do_derma_chart_last_section` (`DermaChart.vue:653`) plus Frappe user settings, so specs set it explicitly via `ChartPage.setSection()`.

Seed fixtures are all prefixed `E2E ` and resolved by that prefix from `helpers/derma.ts`; nothing reads rows that merely happen to exist, because the dev site is a production clone. `Patient` and `Healthcare Practitioner` use naming series, so they are looked up by `first_name`, not by `name`.

## Patches

`patches.txt` is all `post_model_sync` and patches are written idempotently (check-then-act), because they repair live sites: seeding sidebar items and default templates, creating custom fields the other apps may not have added, and `ensure_derma_chart_page` which recreates the `Page` row on sites without developer mode. Follow that pattern — a patch here should be safe to re-run and safe on a site missing the target doctype.

## Writing specs

Feature work starts with a spec in `docs/superpowers/specs/<YYYY-MM-DD>-<snake_case_feature>.md`
before code. One file per feature. Write it as a **living document**: after
implementation, update it in place rather than leaving a stale plan behind.

Three directories look like they hold specs. Only the first is one:

| Path | What it is |
|---|---|
| `docs/superpowers/specs/` | The spec. Committed, the durable artifact, the only one to add to. |
| `docs/superpowers/plans/` | One committed pre-convention plan (`2026-08-01-derma-chart-first-visit`). Kept for history; do not add more — fold planning into the spec's Phases. |
| `.superpowers/sdd/<date>-<slug>/` | Tool scratch — review diffs, `progress.md`, findings. Gitignored, never a source of truth, safe to delete. |

`2026-08-01-derma-chart-first-visit-design.md` predates the naming rule and is
kebab-case with a `-design` suffix. Leave it; new files follow the convention above.

### Required frontmatter (plain lines under the H1, not YAML)

    # Feature Name In Plain English

    Date: 2026-08-09
    Status: **Draft** | **Implemented & verified** (date) — link to [Verification](#verification)

Update `Status` when the work lands. If implementation deviated from the plan,
say so in the Status line and link to the Reconciliation section.

### Section order

1. **Goal** — what the user can do afterwards, and why it's hard today. Quote the
   constraints from the request verbatim ("frontend-only", "no new doctype").
2. **Decisions** — settled product/technical calls, one bullet each, in the form
   *decision → rationale → trade-off accepted → what was rejected and why*.
   Only include if real choices were made.
3. **Library choice** (only when adding a dependency) — comparison table
   (option | size | why/why not), the winner in bold, the exact install command,
   and links to the sources consulted. Never add a dep without this table.
4. **Current State (verified)** — the single most important section. Cite exact
   file paths **and line numbers**, real data shapes, and the existing patterns
   this feature must mirror. State negatives explicitly ("no search UI exists
   anywhere", "`permission_query_conditions` is commented out"). Everything here
   must be checked against the code, not remembered — this is the section a
   future reader trusts without re-reading the source.
5. **Non-Goals** — exhaustive. Each one is a boundary someone would otherwise
   assume is in scope. Note explicitly which existing machinery is untouched.
6. **Design** — the core idea in two or three sentences, then one numbered
   subsection per file/component (`### 1. <what> — <path>`). Show **code
   sketches**, not prose descriptions of code. Call out precedence/ordering
   concerns and idempotency contracts. End with a "what stays unchanged" line.
7. **Security** — required whenever the feature touches patient data, permissions,
   user-authored content rendered to others, or a new whitelisted endpoint.
   State the control and the regression test that proves it.
8. **Acceptance Criteria** — observable behaviors, including the *no-regression*
   ones and the degraded/empty/error paths.
9. **Phases** — tracer bullets: vertical slices through every layer, each
   independently shippable and each producing real feedback. Phase 1 is the
   thinnest end-to-end path that a user could actually use. Give each an
   `Exit:` line. Do not phase by layer (schema → backend → frontend).
10. **Open Questions** — each with a `Default:` answer so an unanswered question
    never blocks implementation.
11. **Reconciliation — what changed vs the plan** / **Implementation Notes
    (as-built)** — written *after* shipping. Every deviation, with why the
    as-built choice was better or forced. Never silently rewrite the plan to match.
12. **Verification** — the real commands run and their real results, split by
    kind (unit / integration / migrate / manual). Name the test modules and pass
    counts. List what was **not** run under a "Not yet run" heading.
13. **Phase 2 (future, not in this spec)** — deferred ideas, so they stop
    haunting the current scope.
14. **Files to touch (summary)** — a two-column table (`File | Change`) with
    `*(new)*` markers. It doubles as the implementation checklist.

Sections 2, 3, 7, and 11 are conditional; the rest are expected.

### Tone

Decisive. Prefer "we do X because Y; Z was rejected because W" over "we could
either X or Z". Bold the load-bearing claim in a paragraph. If something is the
single riskiest part of the feature, say so in those words and link to where
it's handled.

### do_derma specifics for the Current State / Verification sections

- Cite bench-relative paths (`do_derma/api.py:1420`, `public/js/chart/DermaChart.vue:812`).
- Say which of the three apps owns each doctype touched (`do_derma` / `healthcare` /
  `do_health`) — cross-app reads must be named as such.
- Any new whitelisted endpoint states in Design that it calls `_ensure_clinical_access()`
  first, and Verification names the test that proves it.
- Schema-defensive reads (`_has_doctype` / `_has_field` / `_select_existing_fields`)
  are a Design concern, not an implementation detail — say which optional fields
  the feature must survive the absence of.
- Frontend changes state whether `bench build --app do_derma` is required and
  whether any `*.bundle.js` filename (the `frappe.require` contract) changes.
- Verification runs the real runner:
  `bench --site dermaone.localhost run-tests --module do_derma.tests.test_<x>`,
  plus `bench --site dermaone.localhost migrate` when patches or fixtures change,
  and `ruff check apps/do_derma`. Report actual pass counts.

## Main Rules

- Whitelisted endpoints gate first, then reuse the `api.py` helpers instead of re-deriving context or schema checks.
- Group related files in folders instead of adding many same-prefix modules.
- Avoid lazy re-exports in package `__init__.py` when autocomplete matters.
- Keep comments short. Remove comments that restate the code.
- Do not put comments at the top of a file. Use a short, terse class or method docstring instead.

## Code Taste

These rules are mandatory for agents changing this repo:

- Choose clean code over clever code.
- Prefer explicit config over implicit behavior.
- Prefer object-oriented code where it maps to the domain.
- Keep functions small. Around 25 lines is a useful target, not a reason to split readable code blindly.
- Keep cyclomatic complexity <= 8
- Keep files 800 lines max when practical. `api.py` (3.5k), `DermaChart.vue` (2.8k), `ProcedurePanel.vue` (2.5k) and `EmbeddedExcalidraw.jsx` (1.3k) are sanctioned exceptions: the limit binds new files, so do not split those four opportunistically.
- Avoid crowded modules. If a folder grows too large, group related files into a subfolder instead of adding more same-prefix files.
- Avoid abbreviations.
- Use standard APIs and existing repo helpers before adding custom logic.
- Reuse existing patterns. Write as little new code as the change needs.
- Delete before adding when existing code can be simplified.
- Always add or update tests for behavior changes, and make sure they pass.
- Build the minimum working change, then iterate.
- Keep comments and docstrings terse. Explain only what the code does not already make obvious.
- Put detailed change explanation in commit messages or docs, not inline comments.
- Keep one owner for state that can drift out of sync.
- Keep state scoped. Do not let temporary state leak across object or module boundaries.
- Fail loudly near the bug. Do not hide corrupt or partial state behind broad fallbacks.
- Retry only operations that are safe to repeat.
- For a no-argument method that computes and returns one noun-like value, use `@property`.
- For methods with arguments or multi-step work, prefer `get_<what_it_returns>()`, such as `get_chart_context()`.
- Default to public methods. Use a leading underscore only for raw parsing, security-sensitive validation, OS plumbing, or genuinely internal details callers should not reach for.
- Do not make a method private just because it currently has one caller.
- Do not split code into more helpers than necessary. A single-use one-liner usually reads better inline.
- Name boolean-returning properties and methods with `is_` or `has_`, such as `_has_doctype` or `_has_field`.

## Implementation Guidelines
* Create a new branch before working on a new feature/spec (branch name patterns: feat/, fix/, just like conventional commit pre-fixes)
* Reconcile the spec and log the progress after each phase of development
