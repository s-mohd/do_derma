# Derma chart: Assessment tab restyle

Status: agreed 2026-10-03. Branch: `feat/derma-assessment-restyle`, cut from
`feat/derma-procedures-restyle`.
Builds on `2026-10-01-derma-chart-panel-restyle.md` (phase 2b), which moved Assessment onto the
`--chart-*` tokens but kept its layout, and follows `2026-10-03-derma-procedures-restyle.md`.

## Goal

The Assessment tab reads like the restyled Procedures tab: actions in the card header, one
filled button, `.chart-pill` / `.chart-label` vocabulary, flat sections instead of nested
cards. It also shows more useful content: real table rows and the format and procedures of
previous visits, actionable other-format pills, a quieter status line, and a compact
dictation result. Handlers, saves and `data-test` hooks are unchanged.

## Decisions

| Topic | Decision |
|---|---|
| Scope | Option C: restyle plus layout plus the five content changes below |
| Build | In place in `assessment/*`, the Assessment block of `DermaChart.vue`, and their scoped styles. No shared section-shell component |
| Filled buttons | One per tab: Edit / Save in the card header. Dictate and Annotate Consultation become `.ghost small` |
| Other formats | Caution pills that call `requestAssessmentModeChange`, so the existing confirm prompt guards the switch |
| Previous-visit server change | Additive keys on `get_previous_visits`; visit eligibility unchanged |

## Layout

### Card header

`SectionCard` header actions, left to right (teleported content lands after the `actions`
slot, so `SectionCard` itself is not changed):

- The format switch (unchanged, existing `actions` slot).
- Status pill, teleported, only while editing: `Unsaved changes` (caution) or `Saving...`
  (neutral). Nothing when reading.
- `Print` (`.ghost small`), teleported to `#chart-section-actions`, shown under today's
  `canPrint` rule.
- `Edit` or `Save` (`.primary small`), teleported to `#chart-section-actions`, with today's
  `canEdit` / `editMode` / `isDirty` / `saving` rules. `Start Assessment` stays in the empty
  state body.

The footer row (`.assessment-footer`) is deleted; everything in it moves to the header or to
the Patient advice section.

### Body

One surface. Sections sit flat on the card, separated by a `1px solid var(--chart-border)`
rule, each with a `.chart-label` heading where it has one. No bordered inner card around the
dictation block, the note, Drawings or Previous visits.

1. **Dictation** (`VoiceScribe.vue`). Dictate is `.ghost small` with the mic icon; the hint
   follows on the same line. The Adjust form stays as the next line when a note exists, with
   the shared input style. Result line, see "Dictation result".
2. **Other formats** (`AssessmentPanel.vue`), only in read mode when another format has
   content. See "Other-format pills".
3. **Note fields** (`SoapNoteFields.vue`, `StructuredAssessmentFields.vue`):
   - Field and section headings use `.chart-label` styling (small uppercase, muted), not bold
     15px.
   - Read mode: values as plain text on the surface, no grey control box.
   - Edit mode: textareas and the Structured desk controls take the shared chart input look
     (`--chart-surface` fill, `--chart-border`, accent focus ring) instead of desk's grey fill.
     Overrides are scoped to `.assessment-panel` so desk forms elsewhere are untouched.
4. **Patient advice**, only when advice text exists: `.chart-label` heading, the advice text
   (collapsible as today), and the `Include in print` checkbox plus the language select moved
   here from the footer. `data-test="assessment-advice"`, `assessment-advice-toggle` and
   `assessment-advice-language` stay.
5. **Drawings** (`DermaChart.vue`). `Annotate Consultation` becomes `.ghost small` with an
   icon instead of the `✎` glyph; the drawing cards stay.
6. **Previous visits**, see below.

Error text (`assessment-error`) and the submitted / cancelled note stay at the top of the
body; the submitted note becomes a neutral pill-toned line instead of orange text.

## Content changes

### 1. Previous visits show table rows

`assessment._preview_text` stops returning `"{0} row(s)"`. For table fields it uses
`get_table_rows(row, value)`: values inside a row join with a space, rows join with `"; "`.
Example: `L29.8 Other pruritus; L21.0 Seborrhoea capitis`. A table whose rows are all empty
adds no preview field. `value` stays a string, so the client `<dl>` and its three-field
preview cap keep working.

### 2. Previous visits show format and procedures

`previous_visits._build_visit` adds two keys to each visit:

- `mode_label`: `_(assessment.MODE_LABELS[assessment.get_assessment_mode(doc)])`, the same
  source as `get_visit_summary`. `_build_visit` already loads the encounter doc; load it once
  and pass it to both `get_preview` and the mode lookup.
- `procedures`: list of titles of the visit's non-cancelled procedures. `get_page` takes a
  `load_procedures` callable next to `load_drawings`; `api.get_previous_visits` passes a
  function returning `[row["title"] for row in _get_visit_summary_procedures(doc)]`, so the
  title rule matches the summary dialog.

Eligibility is unchanged: a visit with neither drawings nor assessment content is still
skipped, even if it has procedures. A failure loading procedures fails the request (as
drawings do); no silent empty list.

Client (`PreviousVisitsPanel.vue`):

- Visit header line: date · doctor · neutral `.chart-pill` with `mode_label`, then up to
  three neutral procedure pills and a `+N` pill for the rest. View Summary stays
  `.ghost small` at the end.
- The panel drops `chart-inner-card` and becomes a flat section (rule above, `.chart-label`
  heading). Visits are separated by thin rules. `dt` uses `.chart-label` styling.
- Load more, Collapse, Show all, View Summary unchanged.

### 3. Other-format pills

Replaces the orange `assessment-other-format` sentence. One `caution` `.chart-pill` per other
format with content, labelled `{format} has content` using the short labels (`Structured`,
`SOAP`, `H&P`). The row keeps `data-test="assessment-other-format"`; each pill carries
`data-test="assessment-other-format-<mode lowercase>"`.

- Unlocked encounter: each pill is a `<button>`; `AssessmentPanel` emits
  `switch-mode(mode)`, and `DermaChart.vue` handles it with `requestAssessmentModeChange`.
  That keeps today's confirm prompt ("Switch this visit to {0}? Nothing you have written is
  deleted.") and today's behaviour after switching (the format is restamped and edit mode
  opens).
- Locked encounter (`docstatus !== 0`): plain `<span>` pills, not clickable.

### 4. Quieter status

- Removed: "Read-only. Choose Edit to continue documenting." and "No changes".
- Kept, as the header status pill while editing: "Unsaved changes", "Saving...".

### 5. Dictation result

`VoiceScribe.vue` result block:

- Diagnosis as a neutral `.chart-pill`; the ICD-10 code as a second pill (replaces the
  purple `<code>`). "No diagnosis suggested" stays as muted text when there is none.
- `WhatsApp follow-up` and `Arabic note` become `.ghost small` toggle buttons on the same
  line, with `aria-expanded`. One open at a time; the open one's content renders under the
  line (follow-up texts with their Copy buttons, the RTL Arabic note). No `<details>`.

## Out of scope

- A shared section-shell component for every tab.
- Changes to `VisitSummaryDialog.vue` beyond what its reused helpers return.
- Showing procedure-only visits in Previous visits.
- Desk controls outside the chart.

## Testing

Written first and failing.

Server (`test_previous_visits.py`, `test_assessment.py`):

- a previous visit whose Diagnosis table has two filled rows previews it as
  `"<code> <name>; <code> <name>"`; no `row(s)` in any preview value
- a table with only empty rows adds no preview field
- each visit carries `mode_label` matching its stamped format (a SOAP and a Structured visit)
- each visit carries `procedures` with its non-cancelled procedure titles; a cancelled one is
  absent
- a procedures-only visit is still not listed

Source (`test_chart_theme.py`):

- `VoiceScribe.vue` result has no `<details>` and no `<code>`; the ICD code renders as
  `.chart-pill`
- Edit and Save sit inside `<Teleport defer to="#chart-section-actions">`; across the
  Assessment components and the Assessment block of `DermaChart.vue` there is exactly one
  `primary` button class besides Start Assessment
- "Read-only. Choose Edit to continue documenting." and "No changes" are gone
- other-format pills emit `switch-mode`, are buttons only when unlocked, and `DermaChart.vue`
  routes `@switch-mode` to `requestAssessmentModeChange`
- field headings in `SoapNoteFields.vue` and `StructuredAssessmentFields.vue` use the
  `.chart-label` look
- every `data-test` hook named `assessment-*`, `voice-*`, `previous-visit*` and
  `annotate-consultation` that exists today still exists
- the existing hex-colour allowlist and token tests stay green

Browser, on HLC-ENC-2026-18379 (draft; has SOAP, Structured and H&P content) and a submitted
encounter:

- 1280 / 1600 / 1920, light and dark
- read and edit mode in all three formats; a real edit saved, then reverted
- other-format pill: confirm prompt appears; Cancel keeps the format, OK switches
- dictation result toggles on the saved summary
- Include in print and the language select, each reverted
- Previous visits shows real diagnoses, the format pill and procedure pills; Load more and
  Collapse work
- submitted encounter: no Edit unless an Allow-on-Submit field exists; other-format pills
  inert
- before/after screenshots

Suite: diff failures against the known set on `main`.
