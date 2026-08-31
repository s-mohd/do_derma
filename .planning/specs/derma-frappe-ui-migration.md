# Derma chart on frappe-ui: one design system for the chart and config pages

## Problem Statement

The derma chart page looks and behaves like nothing else on a Frappe site. Every
element on it is hand-made:

1. **A private design system nobody maintains.** `derma_chart.bundle.css` is 4,916
   lines of bespoke global CSS, with another ~2,100 lines spread across eight
   `<style scoped>` blocks. Its tokens (`--derma-brand`, `--derma-text-*`,
   `--derma-border-*`) are hard-coded hexes that drift from Frappe's own palette,
   and two places override desk's `--color-primary` to force a teal brand.

2. **Hand-rolled primitives.** Buttons are `<button class="ghost small">`, selects
   and inputs are raw elements, tabs are a custom bar, badges and chips are bespoke
   spans, the spinner is CSS-drawn, and icons are text glyphs like `✓`. None of it
   matches the Button/Select/Tabs/Badge language a Frappe user knows from CRM,
   Helpdesk, or desk itself.

3. **No dark mode.** The stylesheet has no `[data-theme]` or `prefers-color-scheme`
   handling, so a practitioner running desk in dark mode gets a blinding white chart.

4. **Data flow with 47 owners.** Every component calls `frappe.call` inline and
   manages its own `loading` / `error` refs; there is no shared request layer, no
   caching, and loading affordances are inconsistent because each site reinvents them.

5. **Desk-global dialogs.** 40× `frappe.show_alert`, 22× `frappe.msgprint`,
   9× `frappe.ui.Dialog`, 9× `frappe.confirm` and 1× `frappe.prompt`, papered over
   by helper shims (`dialog_a11y.js`, `dialog_progress.js`) that exist only because
   the desk dialogs are not accessible or progress-aware out of the box.

The derma config page (8 Vue panels) shares all five problems with its own 545-line
stylesheet. The result: the two Vue surfaces of this app cost real effort to keep
consistent and still do not look like a Frappe product.

## Solution

Adopt **frappe-ui** — the component library and semantic token system behind Frappe
CRM, Helpdesk, Gameplan and Drive — inside the existing desk pages. The pages stay
where they are (`/app/derma-chart`, `/app/derma-config`), keep their mount contract
with the do_health sidebar, and keep every behaviour they have today. What changes:

- A **Vite build** under `frontend/` compiles the chart and config apps and emits
  fixed-name bundles into `do_derma/public/frontend/`; the desk page JS loads those
  instead of the Frappe-bundler output.
- Every hand-rolled element is replaced by its **frappe-ui component** (Button,
  FormControl, Select, Combobox, Tabs, List, Dialog, Badge, Alert, Avatar,
  Spinner/LoadingText, FileUploader), styled exclusively with **semantic tokens**
  (`bg-surface-*`, `text-ink-*`, `border-outline-*`). Dark mode comes free: desk
  toggles `data-theme="dark"` on `<html>`, which is exactly the switch the tokens
  listen to.
- In-page **navigation** (section tabs on the chart, panel switcher on config)
  moves to frappe-ui `Tabs` / `TabButtons`, keeping the existing per-encounter
  section persistence.
- **Data flow** consolidates on `useCall` from frappe-ui: reads auto-fetch with
  shared loading/error surfaces, writes use `immediate: false` + `submit()` bound
  to `<Button :loading>`. The whitelisted endpoints in `api.py` are untouched.
- Desk-global dialogs and alerts become frappe-ui's imperative `dialog.confirm` /
  `dialog.alert` / `dialog.prompt` and `toast.*`, retiring the a11y/progress shims.
- At the end, the 4,916-line global stylesheet, the scoped style blocks, and the
  old bundle entries are **deleted**.

Delivery is **phased**: a build-swap phase that changes no pixels, then one phase
per chart section, then the config page, then teardown. Every phase is shippable
and browser-verifiable on its own.

## User Stories

1. As a practitioner, I want the chart to use the same buttons, fields, tabs and
   badges as the rest of my Frappe apps, so that nothing on it needs relearning.
2. As a practitioner running desk in dark mode, I want the chart and config pages
   to follow, so that opening a patient chart at night is not a white flash.
3. As a practitioner, I want every action button to show its own busy state while
   its request runs, so that I never double-submit a procedure or consent.
4. As a practitioner, I want the first chart load to show the page skeleton with
   placeholder text instead of a blank pane, so that I can see the page is coming.
5. As a practitioner, I want save confirmations as quiet toasts and destructive
   actions behind a proper confirm dialog, so that feedback matches its weight.
6. As a practitioner, I want the procedure history as a real sortable table with
   aligned columns, so that scanning fifty procedures does not mean reading ragged
   rows.
7. As a practitioner, I want the item and drug pickers to be searchable dropdowns
   that work like every other frappe-ui picker, so that picking a consumable does
   not depend on an embedded desk form control.
8. As a practitioner, I want empty sections to say what is missing and offer the
   one action that fills them, so that a new patient's chart is not a wall of
   nothing.
9. As a clinic admin, I want the config page to share the chart's design system,
   so that setting up templates feels like part of the same product.
10. As a practitioner, I want everything the chart does today — marks, photos,
    consents, prescriptions, consumables, assessments, completion — to keep working
    exactly as it does, so that the retheme costs me nothing.
11. As a developer, I want one request layer with shared loading and error
    handling, so that a new section does not reinvent `loading` refs.
12. As a developer, I want the bespoke stylesheets gone, so that a visual change
    is a token or prop change, not archaeology in 6,000 lines of CSS.

## Implementation Decisions

### Build: a Vite workspace beside the Frappe bundler

- New `frontend/` directory at the app root: Vite + Vue 3 project owning
  `chart/` and `config/` entries. Version pins are mandatory and non-negotiable
  (frappe-ui 0.1.x constraints): `vite@^5`, `@vitejs/plugin-vue@^5`,
  `tailwindcss@^3.4` + `postcss` + `autoprefixer`, `vue-router@^4`,
  `frappe-ui@beta`, `unplugin-icons` + `@iconify/json` + `lucide-static`.
  Tailwind v4 and Vite 6+ silently break the frappe-ui preset and vite plugin.
- `vite.config.js` uses the `frappeui()` plugin with `optimizeDeps.exclude:
  ['frappe-ui']` and the documented CJS includes. Two library-mode entries
  (`chart`, `config`) build to `do_derma/public/frontend/` with **fixed file
  names** (no content hashes) so the desk pages can `frappe.require`
  `/assets/do_derma/frontend/chart.js` + `chart.css` (and `config.*`). Frappe's
  cache-busting query on `frappe.require` covers staleness.
- `tailwind.config.js` uses `presets: [frappeUIPreset]` (import from
  `'frappe-ui/tailwind'`, not a deep path) with `content` covering
  `frontend/src/**` and `node_modules/frappe-ui/src/**`.
- **Preflight stays off** (`corePlugins: { preflight: false }`). The chart CSS
  loads into the whole desk document; a global reset would restyle the desk
  navbar, awesomebar and sidebar. The app root carries a `derma-frappe-ui` class,
  and the few base rules the components genuinely need (border-color inheritance,
  font smoothing) are declared scoped under that class in the CSS entry. The CSS
  entry imports `'frappe-ui/style.css'` then the three `@tailwind` layers.
- The existing sources move: `public/js/chart/**` and `public/js/config/**`
  (Vue only — the React annotation/excalidraw files stay put and keep being
  imported by path from the chart entry, exactly as today). The old
  `*.bundle.js` entries and `derma_chart.bundle.css` / `derma_config.bundle.css`
  survive until the teardown phase so a mid-migration site never loses a page.
- Build command: `cd frontend && npm run build`, added as a `build` script in the
  app's root `package.json` and documented in the README. `bench build` does not
  run Vite; that is accepted — CI/deploy calls the script.

### Mounting, routing and the desk contract

- `page/derma_chart/derma_chart.js` keeps its `on_page_load` / `on_page_show`
  shape; only the `frappe.require` list changes to the new asset paths. The
  `frappe.ui.DermaChart` wrapper class, `single_column: true`, and the
  `.layout-main-section` mount point are unchanged. Same for `derma_config.js`.
- Patient context keeps arriving from `window.frappe.route_options` and
  `window.do_health.patientWatcher` (`App.vue` is untouched in behaviour). No
  patient picker appears on the chart — the health sidebar owns selection.
- frappe-ui's `Button` injects the router symbol, so each entry installs a
  **`createMemoryHistory` router with a single catch-all route**. Memory history
  never touches the URL, so desk routing (`/app/...`) is never hijacked. No
  `route` props are used; navigation stays desk-side.
- Each entry's root wraps content in `FrappeUIProvider` (imperative dialog/toast
  portals, theme) and installs the `FrappeUI` plugin. Dark mode needs no code:
  desk already sets `data-theme` on `<html>` and the tokens follow it.

### Design language

Follow the frappe-ui app design language (gray-first, hierarchy through ink):

- **Drop the teal brand.** Primary actions are `variant="solid" theme="gray"`;
  destructive ones `theme="red"`. The two `--color-primary` overrides in the old
  CSS die with it. Color appears only where it encodes state: status badges via
  one `statusTheme` lookup (`Badge variant="subtle"`), allergy chips red,
  degraded-section notices amber `Alert`s, completion green.
- **Ink ladder, not boxes.** Section headings `text-lg-semibold text-ink-gray-8`,
  labels `text-sm text-ink-gray-6`, meta `text-sm text-ink-gray-5`, body
  `text-base text-ink-gray-9` on `bg-surface-base`. Cards that must stay cards
  compose `bg-surface-base rounded-5 border border-outline-gray-1` (there is no
  Card component by design).
- **Icons** are lucide CSS classes (`<span class="lucide-plus size-4"
  aria-hidden="true" />`) or `icon`/`iconLeft` string props. The `✓` glyphs,
  CSS-drawn spinner and inline SVGs in Vue files go; the React studio keeps its
  own SVGs.
- Sentence case everywhere; no uppercase headers. One primary action per screen
  (the header's complete-session button); everything else `subtle` or `ghost`.

### Component mapping (the pattern, applied per section)

| Today | Becomes |
| --- | --- |
| `<button class="primary/ghost small">` | `Button` (`variant`/`theme`/`size`, `:loading`) |
| raw `<select>` / `<input>` / `<textarea>` | `FormControl` (or bare `Select` / `TextInput` in dense toolbars) |
| custom section tab bar (`SECTION_TABS`) | `Tabs` with `v-model:tab`, keeping `persistDermaSection` / `hydrateDermaSectionPreference` |
| config panel switcher | `TabButtons` |
| ProcedurePanel table + sort + "load more" | `List` in table mode (`:columns`, `ListHeaderCellSort`, `:row-height="48"`); sort comparators stay app code |
| filter toolbar selects | `Select` / `Combobox` row + `TextInput` with `lucide-search` prefix |
| bespoke badges/chips (`MarkResponseChips`, allergy, insurance) | `Badge` with theme lookup |
| `DegradedSectionNotice` | `Alert theme="amber"` with retry as `primary-action` |
| refresh banner | `Alert theme="blue"` |
| skeleton loader / `chart-spinner` | `LoadingText` skeletons on first load, `Spinner` inline, `Button :loading` on actions |
| photo upload | `FileUploader`; viewer/lightbox → `Dialog size="4xl"` (or `bare`) |
| patient header | composed from `Avatar`, `Badge`, `Button`, ink-ladder text |
| empty sections | the DESIGN.md empty-state pattern (icon disc, one-line title, one action) |

`frappe.ui.form.make_control` embeds (item Link in `ConsumablesEditor`, drug
fields in `PrescriptionPanel`) are replaced by **`Combobox`** (`v-model` +
`v-model:query`) backed by a `useCall` to the existing search paths — the
`api.py` helpers where they exist, `frappe.client.get_list` /
`search_link` otherwise. This removes the last dependency on desk form
internals inside the Vue tree.

### Data flow

- All 47 `frappe.call` sites convert to **`useCall`** against
  `/api/v2/method/do_derma.api.<fn>` (v2 returns the `data` envelope `useCall`
  expects; the site is Frappe v16). Desk provides the session cookie and
  `window.csrf_token`, which frappe-ui's request layer already reads.
- Reads (`get_patient_derma_chart`, per-section `ensureSectionData` loaders)
  are `useCall` with reactive `params` + `refetch`, their `loading`/`error`
  driving `LoadingText` / `Alert`. Section degradation tracking
  (`isSectionDegraded`) keeps its semantics, fed by `useCall.error` instead of
  hand-rolled flags.
- Writes are `immediate: false` + `submit(params)`, `onSuccess` →
  `toast.success`, `onError` → `toast.error(serverErrorText(...))`. The
  `error_text.js` helper survives (it maps server messages to human text); the
  dialog shims do not.
- The scattered `frappe.db.get_list/get_value/get_doc` calls convert to
  `useList` / `useCall` on the document API. The four `fetch()` calls for
  image/photo blobs stay `fetch` — they fetch binaries, not JSON envelopes.
- One toast per user action; multi-field saves in the same form reuse a stable
  toast `id` rather than stacking.

### Dialog and alert mapping

- `frappe.confirm` → `dialog.confirm({ theme: 'red', ... })` for destructive
  flows; `frappe.prompt` → `dialog.prompt`.
- `frappe.msgprint` → `dialog.alert` when it blocks, `toast.error/info` when it
  informs. `frappe.show_alert` → `toast.*`.
- The 9 `frappe.ui.Dialog` instances become declarative `<Dialog
  v-model:open>` components (multi-field forms) or imperative calls (single
  question). `dialog_a11y.js` and `dialog_progress.js` are deleted once their
  last caller converts — frappe-ui dialogs are accessible and buttons carry
  their own `:loading`.

### Phases

Each phase is one branch/PR, browser-verified, and leaves both pages working.

- **Phase 0 — build swap, zero visual change.** Stand up `frontend/` (pins,
  configs, provider, memory router, token CSS entry), move the Vue sources,
  emit fixed-name bundles, point both desk pages at them, delete nothing.
  Exit test: chart and config render pixel-equivalent; desk chrome unaffected
  with the new CSS loaded; no console errors (subpath/exports, `~icons`,
  router-injection warnings all clean).
- **Phase 1 — shell.** `DermaChart.vue` frame: tabs → `Tabs`, encounter header
  (`DermaEncounterHeader`) → frappe-ui composition, skeleton/error/empty/refresh
  states → `LoadingText`/`Alert`/empty-state pattern, chart-level `frappe.call`s
  → `useCall`, chart-level alerts → toasts. Global CSS for the shell dies here.
- **Phase 2 — procedures.** `ProcedurePanel.vue`: `List` table, toolbar,
  pagination, row actions, its dialogs and confirms, its ~1,000-line scoped
  style deleted. Largest single phase.
- **Phase 3 — assessment.** `AssessmentPanel`, `SoapNoteFields`,
  `StructuredAssessmentFields` → `FormControl` forms, autosave toasts.
- **Phase 4 — photos.** `PhotosPanel` + `PhotoViewer`: `FileUploader`, grid,
  `Dialog` viewer, stage retag via `Select`.
- **Phase 5 — consent + anesthesia.** `ConsentPanel`, `AnesthesiaPanel`.
- **Phase 6 — prescriptions + consumables.** `PrescriptionPanel`,
  `ConsumablesEditor`: `Combobox` replaces both `make_control` embeds; keep the
  UOM lock-out fixes (pending-item loading states, non-convertible unit
  flagging) behaviour-identical.
- **Phase 7 — config page.** All 8 config panels + its `App.vue`;
  `derma_config.bundle.*` retired.
- **Phase 8 — teardown.** Delete `derma_chart.bundle.css`, remaining scoped
  styles, old bundle entry files, the stray `public/css/derma_chart.css`, the
  dialog shims; full dark-mode pass; grep gates (below) turn red-line.

### File-size and repo rules that bind the executor

- `DermaChart.vue` and `ProcedurePanel.vue` are sanctioned size exceptions —
  do not split them opportunistically, but natural extractions during a phase
  (e.g. the procedures filter toolbar) are welcome if they shrink, not shuffle.
- New files go in the existing feature folders (`components/assessment/`,
  `components/photos/`, …); no new same-prefix module sprawl.
- Whitelisted endpoints gate first; reuse `api.py` helpers rather than
  re-deriving context. No backend changes are expected in any phase.

## Testing Decisions

The retheme must not change server behaviour, so the Python suite is the
regression net, and the browser is where the theme itself is judged.

### Machine-tested

- The full existing Python test suite passes untouched after every phase — any
  red test means a behaviour change leaked in, which this spec forbids.
- No JS test framework is introduced (consistent with prior specs).
- **Grep gates**, enforced from Phase 1 onward on migrated files and repo-wide
  at Phase 8: zero `frappe.call(` in `frontend/src`, zero `frappe.show_alert` /
  `frappe.msgprint` / `frappe.confirm` / `frappe.ui.Dialog` /
  `frappe.ui.form.make_control` in Vue files, zero raw-palette Tailwind classes
  (`bg-gray-`, `text-slate-`, `bg-white`, `border-gray-`), zero `--derma-*`
  custom properties.

### Browser-verified, per phase

Drive the running site (bench browse gives a port-8002 sid; seeded body
template images 404 — known, ignore):

- The phase's section renders with frappe-ui components: buttons show
  `:loading` during writes, toasts replace alert popups, confirms are frappe-ui
  dialogs.
- Full workflow pass for the migrated section (e.g. Phase 2: filter, sort,
  paginate, open a procedure, edit consumables, complete) — behaviour matches
  the pre-phase page.
- Dark-mode toggle (`data-theme="dark"` on `<html>`): the migrated section
  flips cleanly, no white islands.
- **Desk regression check every phase:** with the chart assets loaded, open an
  unrelated doctype form and the desk home — navbar, awesomebar and forms must
  be visually unaffected (this is the preflight-off contract).
- Phase 0 only: side-by-side screenshot comparison old vs new build,
  pixel-equivalent within font-rendering noise.

## Out of Scope

- The React surfaces: `DermaAnnotationStudio.jsx`, `EmbeddedExcalidraw.jsx`,
  `MarkerSizeControl.jsx`, and the body-template editor bundle. frappe-ui is
  Vue-only; these keep their current look and their Frappe-bundler build (the
  chart entry imports the studio by path as today).
- Any behaviour change: no new features, no changed endpoints, no changed
  payloads, no changed section semantics. Pending specs (annotation area
  selection, camera capture) land independently of this migration.
- `api.py` and all Python code.
- The globally injected `derma_sidebar.js` / `annotations_button.js` desk
  scripts — they are desk chrome, not part of the two pages.
- A standalone SPA, vue-router URL routing, `DesktopShell`/`MobileShell`, or a
  mobile layout — the pages remain desk pages inside desk's shell.
- Realtime/socket features; refresh stays manual.
- Introducing a JS test runner.
- i18n changes: `__()` keeps working as today (desk provides it globally).

## Further Notes

- **Why embed rather than a standalone SPA:** patient context is owned by the
  do_health sidebar (`patientWatcher`), and the standing rule is that the chart
  never grows its own patient picker. A `/derma` SPA would need a new context
  bridge and a second navigation model for zero user benefit; embedding keeps
  the contract and still delivers the full component/token system.
- **Why preflight must stay off:** the desk page injects its CSS into the same
  document as the rest of desk. Tailwind's global reset would restyle desk
  chrome app-wide. This is the one place the stock frappe-ui setup guide is
  deliberately deviated from, and the per-phase desk regression check is its
  insurance.
- **Why fixed asset names instead of hashed:** `frappe.require` takes literal
  paths from page JS; a manifest indirection is more moving parts than the
  cache-busting query already solves.
- **Why the memory-history router:** frappe-ui `Button` injects the router
  symbol and warns on every render without one; memory history satisfies the
  injection without ever competing with desk's `/app` routing.
- **Why phased with a zero-change Phase 0:** the build swap is the riskiest
  step (icons, exports subpaths, CJS deps, preflight). Landing it with no
  visual delta isolates build failures from design review; every later phase
  then reviews as pure UI diff.
- The old CSS is deleted **per phase**, not at the end only — dead selectors
  left lying around would mask specificity clashes between the bespoke rules
  and Tailwind utilities during review.
