# Derma chart: Procedures tab restyle

Status: agreed 2026-10-03. Branch: `feat/derma-procedures-restyle`, cut from
`chore/derma-housekeeping-followups` (the redesign line).
Builds on `2026-10-01-derma-chart-panel-restyle.md` (phase 2b), which moved Procedures onto the
`--chart-*` tokens but kept its old layout.

## Goal

The Procedures tab reads like the other chart tabs (Photos, Prescription, Assessment): one
compact toolbar, `.chart-pill` / `.chart-label` vocabulary, flat inner card, quiet rows.
Behaviour, handlers and `data-test` hooks are unchanged, apart from two new filter values that
back the attention chips.

## Decisions

| Topic | Decision |
|---|---|
| Scope | Option B: restyle plus a lighter row layout. Drawing thumbnails on rows stay out (own spec) |
| Price editing | Click-to-edit: price shows as text; clicking opens today's override editor in a popover |
| Counter tiles | Removed. Counts move into status pills; attention chips replace Missing notes / Billing review / Lab follow-up |
| Notes + actions | Notes column removed. One borderless icon cluster: note, annotate, reopen, delete |
| Build | In place in `ProcedurePanel.vue` and its scoped styles. No new files (sanctioned large file) |

## Layout

### Toolbar (one line)

Search (flexible width) · Sort as a plain compact select, no stacked "Sort" label ·
`.ghost small` Filters button with its active count · Clear (only while filters are active).
The Read-only and Anesthesia-recorded pills stay at the end of the line. Section-level
buttons stay teleported into the card header. The advanced filters panel keeps its selects,
restyled with the shared input rules.

### Pills row

- Status pills as `.chart-pill`: `All 5 · Draft 5 · In Progress · Completed · Cancelled`. A
  pill shows its count only when above zero. The `statusPills` prop from `DermaChart.vue` stays
  a static list; the panel counts loaded rows per status (all loaded rows, ignoring filters,
  matching the tab badge).
- Attention chips on the right, each shown only when its `historyStats` count is above zero,
  `caution` tone: `N missing note(s)`, `N billing review`, `N lab follow-up` (lab only when
  `enableLabCases`). Clicking a chip sets one filter; clicking an active chip resets it to
  `"all"`. The active chip shows `aria-pressed="true"`.

  | Chip | Filter | Predicate |
  |---|---|---|
  | missing note | `noteFilter = "missing_note"` | existing |
  | billing review | `billingFilter = "review"` (new option "Needs review") | `hasAnyOverride(row) \|\| rowIsInsurance(row)`, as the count |
  | lab follow-up | `labFilter = "follow_up"` (new option "Follow-up") | `rowNeedsLabFollowUp(row)`, as the count |

  The two new values also appear in the Filters panel selects, so chip and select stay one
  state. `historyStats` uses the same predicates, so a chip's count equals the rows it shows.
- The "Matching" tile is dropped; the footer already states `displayed / total procedures`.

### Table

Inner flat card: `--chart-surface-muted` header row, `--chart-border`, no shadow. Header cells
use `.chart-label` styling. The date group row becomes a muted label-sized line (as Photos
shows its dates), not a bold grey band.

Six columns (`colspan` of the date and consumables rows becomes 6):

| Column | Content |
|---|---|
| Status | Status pill; consent pill under it (`ok` tone consented/waived, `danger` "Consent needed") |
| Procedure | Name as the open link; code and area muted on a second line |
| Details | Chips only, as `.chart-pill` variants with their icons (details, lab, insurance, materials, variables, artifacts) |
| Price | Amount, price list muted under it, `No charge` (neutral) or `Override` (caution) pill, saving spinner |
| Doctor | Practitioner name |
| Actions | Borderless icon buttons with hover tint |

The `No charge` and `Override` chips move from Details to Price. `Insurance` stays in Details.

### Actions cluster

- **Note**: pen icon; small `--chart-ok` dot when a note exists. Title "Add note" / "Edit note";
  "View note" on a non-editable row with a note; hidden on a non-editable row without one.
  Opens `openProcedureNoteDialog(row)` as today.
- **Annotate**: unchanged behaviour, keeps the `annotation_count` badge.
- **Reopen**: unchanged, submitted rows only.
- **Delete**: muted icon, red only on hover/focus. No red box per row.

### Footer

`displayed / total procedures` · Load more · the Load batch-size select (moved from the toolbar).

## Price cell and popover

Reuses `overrideListOpenRow`, `openOverrideList`, `closeOverrideList`, `updatePriceManual`,
`setOverrideFromPriceList`, `markNoCharge`, `clearPriceOverride` and `isRowSaving` unchanged.

- **Editable, non-insurance rows**: the amount is a `<button>` calling `openOverrideList(row)`.
  The button sits **inside** the `.override-picker` wrapper; the outside-click handler closes
  on any click outside `.override-picker`, so a trigger outside it would close the popover in
  the click that opened it.
- **Popover** (rendered only while `overrideListOpenRow === row.name`), anchored under the
  amount as an inner card with a shadow: override input pre-filled with the current override,
  the price-list options (today's `override-dropdown` buttons), and a footer with `No charge`
  and, when an override exists, `Reset`.
- Closes on Escape, outside click, price-list pick (already), input `@change` and Reset.
  `No charge` keeps its required-reason prompt; clicking into that dialog is an outside click,
  so the popover closes while the prompt continues.
- **Insurance, read-only and submitted rows**: amount and price list as plain text, no button.
- Errors stay as today (`frappe.show_alert` for "Could not fetch price" and insurance
  overrides). The save path does not change.

## Out of scope

- Drawing thumbnails on rows (the 2026-09-12 direction); needs its own spec.
- Any server or API change.
- Splitting `ProcedurePanel.vue`.

## Testing

Source tests in `do_derma/tests/test_chart_theme.py`, written first and failing:

- no `summary-tile` in the template; no Notes `<th>`; six `<col>` entries
- the override input and `no-charge-btn` render only inside the `overrideListOpenRow === row.name` branch
- status pills render a count; attention chips set `noteFilter`, `billingFilter`, `labFilter`
- `rowMatchesBillingFilter` handles `"review"` and `rowMatchesLabFilter` handles `"follow_up"`
  with the same predicates `historyStats` counts
- every one of today's 19 `data-test="procedure-*"` hooks still exists
- the note dot reads `var(--chart-ok)` (the existing `.note-presence-indicator` assertion moves to the new selector)
- the existing hex-colour allowlist and status-tone tests stay green

Browser, on HLC-ENC-2026-18379 (draft) and a submitted encounter:

- 1280 / 1600 / 1920, light and dark; no horizontal overflow at 1280 beyond the wrapper's own scroll
- live actions, each reverted: typed override, price-list pick, Reset, No charge with reason,
  note added, annotate opened, consumables toggled, delete on a throwaway procedure
- attention chip and status pill filters narrow the rows; Clear restores them
- read-only states on the submitted encounter: price as text, View note, no delete
- before/after screenshots

Suite: diff failures against the known set on `main`.
