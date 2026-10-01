# Derma chart: panel restyle (phase 2b)

Status: agreed 2026-10-01.
Branch: `feat/derma-chart-panel-restyle`, cut from `feat/derma-chart-overview-skin`.
Builds on `.planning/specs/2026-10-01-derma-chart-overview-skin.md` (phase 1, plus 2a fixes).

## Goal

Every panel inside the derma chart's section cards looks like the Patient Overview:
one accent taken from the clinic's settings, the same buttons, pills, labels and inner
cards, and section-level actions in the card header. Behaviour is unchanged.

Phase 2 runs 2a (phase 1 review leftovers, done in 1cd5e48), then 2b (this spec),
then 2c (dark mode, its own spec).

## Decisions

| Topic | Decision |
|---|---|
| Accent | Do Health Settings `sidebar_header_color`, read through `--do-health-header-accent` |
| Shades | Filled buttons use a darker mix of the accent; accents (tabs, pills, ticks) use it as is |
| OK green | Stays fixed `--chart-ok`, independent of the accent |
| Old palette | Every `--derma-*` variable becomes a `var(--chart-*)` alias |
| Toolbars | Section-level buttons teleport into the section card header |
| Buttons | One filled accent button per card header; the rest outlined. New Consent loses its blue |
| Shared pieces | Buttons, `.chart-pill`, `.chart-label`, inner cards, inputs defined once in the bundle CSS |
| Order | Photos → Prescription → Review → Assessment → Consent → Materials → Procedures |

## Colour system

### Accent

On `.dental-chart-page.derma-chart-page`:

```css
--chart-accent: var(--do-health-header-accent, #16a34a);
--chart-accent-strong: color-mix(in srgb, var(--chart-accent) 82%, black);
--chart-accent-soft: color-mix(in srgb, var(--chart-accent) 10%, white);
```

- `--do-health-header-accent` is set by do_health's sidebar on `document.documentElement`
  from `frappe.boot.do_health.sidebar_header_color`, defaulting to `--do-health-accent`
  (`#16a34a`). A settings change shows after a page reload, as it does for the sidebar.
- `--chart-accent-strong` (≈ `#13873d` on the default) carries filled buttons so white
  text reaches 4.5:1. `--chart-accent-soft` tints the active tab, selected pills and the
  avatar.
- Green that means "accent" moves to these tokens: active tab, assessment tick, avatar,
  primary buttons, selected filter pills. Green that means "OK" (Completed pill, "Ready to
  complete", ok chips) keeps `--chart-ok`.
- Known limit: a very light settings colour leaves white button text low-contrast. The
  sidebar header already has the same limit; no contrast computation in JavaScript.
- These three tokens sit outside the `--ov-*` parity test, because they come from settings.

### Old palette aliased

The 29 `--derma-*` variables move from `:root` onto `.dental-chart-page.derma-chart-page`
(a `var(--chart-*)` reference only resolves where `--chart-*` is defined) and each becomes
a reference:

| `--derma-*` | `--chart-*` |
|---|---|
| `white`, `bg-faint`, `bg-faint-alt` | `surface` |
| `bg-subtle`, `bg-muted` | `surface-muted` |
| `text-strong`, `text-strong-alt`, `text-deep`, `text-deepest`, `navy` | `text` |
| `text-secondary`, `text-secondary-alt` | `text-soft` |
| `text-muted` | `muted` |
| `border-subtle`, `border-faint` | `border` |
| `border`, `border-muted`, `border-light` | `border-strong` |
| `brand` | `accent-strong` |
| `brand-light` | `accent-soft` |
| `success-bg`, `success-bg-alt` | `ok-soft` |
| `warning-bg-subtle`, `warning-bg` | `caution-soft` |
| `danger` | `danger-text` |
| `danger-bg` | `danger-soft` |
| `info` | `blue` |
| `info-bg-subtle`, `info-bg` | `info-soft` |

Only `derma_chart.bundle.css` and `ProcedurePanel.vue` use `--derma-*`, both inside the page.

## Toolbars in the card header

- `SectionCard` renders an empty `<div id="chart-section-actions">` in its header, beside
  the existing `actions` slot (the Assessment format switch keeps using the slot).
- Panels wrap their section-level buttons in `<Teleport defer to="#chart-section-actions">`.
  The buttons stay in the panel's template, with the same state, handlers, disabled rules
  and `data-test` names. A panel unmounts on tab change, which removes its teleported
  buttons with it.
- Header buttons wrap under the label on narrow widths rather than squeezing.

| Panel | Into the card header | Stays in the panel |
|---|---|---|
| Procedures | New Procedure (filled); New Consent, Copy marks from last visit (outlined) | search, sort, Filters, Load, status pills, counters |
| Photos | Upload Photo (filled) | This visit / All photos scope, count |
| Prescription | Save (filled) | rows; the emptied `panel-header` row is deleted |
| Assessment | format switch (already there) | Dictate, Edit, Start Assessment |
| Review | nothing | everything |

## Shared building blocks

One block in `derma_chart.bundle.css`, directly after the token block and before the
early-closing `@media`, reading only `--chart-*` tokens:

- **Buttons**: the existing `.dental-chart-page .primary`, `.ghost`, `.small` rules are
  rewritten in place. `.primary` = filled `--chart-accent-strong`; `.ghost` = outlined
  secondary (surface, `--chart-border-strong`); `.small` = compact size.
- **Pills**: `.chart-pill` with `data-tone` neutral | accent | ok | caution | danger.
  Replaces status pills (Draft, In Progress, Completed, Cancelled), filter pills, photo
  scope chips, consent and note badges, Materials/Test chips.
- **Labels**: `.chart-label`, the small uppercase muted heading, for in-panel headings.
- **Inner cards**: blocks inside a section card (Drawings, Previous Visits, the procedures
  table, the readiness list) become flat `--chart-surface-muted` panels with
  `--chart-border` and no shadow.
- **Inputs and selects**: `--chart-border`, 8px radius, `--chart-focus` ring.

## Per-panel work

For each panel, in order: replace hardcoded hex colours in its `.vue` with tokens, apply
the shared classes, delete its now-dead rules from `derma_chart.bundle.css` and its scoped
style, and check it in the browser. One commit per panel.

1. Photos (`photos/PhotosPanel.vue`, `PhotoViewer.vue`)
2. Prescription (`PrescriptionPanel.vue`)
3. Review (`DermaChart.vue` review template, `review/AiDocumentsCard.vue`)
4. Assessment (`assessment/*`, the Drawings strip in `DermaChart.vue`)
5. Consent dialog (`ConsentPanel.vue`, `AnesthesiaPanel.vue`)
6. Materials (`consumables/ConsumablesEditor.vue`)
7. Procedures (`ProcedurePanel.vue`)

## Done when

- No hardcoded hex colour in any chart `.vue` file outside the annotation studio.
- Every `--derma-*` variable is a `var(--chart-*)` reference.
- `derma_chart.bundle.css` is shorter than at the start of 2b.
- Every panel's section-level buttons render in the card header.

## Out of scope

- Dark mode (2c)
- The annotation studio (`annotation/**`, React)
- Print templates
- The early-closing `@media` bug in `derma_chart.bundle.css`
- Any do_health change

## Testing

Python, reading sources (extends `test_chart_theme.py`):
- `--chart-accent` reads `--do-health-header-accent` with `#16a34a` fallback; strong and
  soft shades derive from `--chart-accent`
- every `--derma-*` declaration is a `var(--chart-*)` reference
- a list of chart `.vue` files allowed to keep hex colours, seeded with today's offenders;
  each panel commit removes its entry, and the list ends empty
- every `Teleport` in the chart targets `#chart-section-actions` with `defer`, and
  `SectionCard.vue` renders that id

Browser, per panel at 1280 / 1600 / 1920:
- actions in the card header, one filled button, gone after switching tabs
- no horizontal overflow
- disabled and read-only states on a submitted encounter
- one live action: upload a photo, save a prescription, create a consent, add and delete
  a procedure, on a test encounter, cleaned up afterwards

Accent: set `sidebar_header_color` to `#7c3aed`, reload, confirm the chart follows and OK
greens stay green, then restore the empty value.

Suite: diff failures against `main` after each panel; whole-branch review at the end.
