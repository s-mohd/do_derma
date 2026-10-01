# Derma chart: Patient Overview design concept

Status: agreed 2026-10-01, phase 1 ready to plan.
Branch: `feat/derma-chart-overview-skin`.

## Goal

The derma chart page reads as the same product as do_health's Patient Overview drawer:
the same tokens, card language, hero identity card and clinical strip. Clinicians keep
every capability the chart has today.

## Decisions

| Topic | Decision |
|---|---|
| Concept | Overview skin **and** layout: hero card, clinical strip, then the sections |
| Sections | Stay as tabs: Assessment, Procedures, Photos, Prescription, Review (five; Consent lives inside Procedures since PR #21) |
| Right column | None. The main column runs full width |
| Readiness | One line in the hero's "This visit" box, plus red dots on tabs. Review keeps the full list |
| Clinical strip | Mirrors the Overview: Allergies, Medical history, Medications, Surgical/Habits footer |
| Approach | do_derma owns its own token scope; new shell components; scoped styles |
| Phasing | Phase 1 = shell. Phase 2 = panel internals onto the tokens |

This replaces the 2026-09-12 readiness *rail*: there is no side column, so readiness
lives in the hero instead. The tab-state rule from that direction (red dot when
blocking, count badge otherwise, undecorated when nothing to say) still holds.

## Layout

Grey canvas (`--chart-bg`), top to bottom:

1. Previous-visit banner (only when viewing an older encounter)
2. Hero card: `ChartHero.vue`
3. Clinical strip: `ClinicalStrip.vue`
4. Tab row
5. Active section card

## Phase 1

### Previous-visit banner

Today's strip ("Previous visit · date · encounter · practitioner · Open latest visit →")
as a thin caution-toned bar above the hero. Same `open-latest` event.

### Hero card (`components/ChartHero.vue`, replaces `DermaEncounterHeader.vue`)

Left:
- Patient photo, or a large soft-green initials avatar (`useBrokenImages` fallback kept)
- Name in the Overview's heavy weight
- Meta line: age · sex · File · CPR (fields `_patient_fields()` already loads)
- Phone chip from `mobile`
- Encounter alert chips (`alerts` prop, `alert-action` event), restyled as Overview pills

Right, the "This visit" box:
- `THIS VISIT` label and appointment status pill (amber for in-progress statuses, green
  for Completed/submitted encounter)
- Date · time in bold (existing `visitWhen` formatting)
- Visit type · practitioner, muted
- Insurance label, muted
- Readiness line:
  - blockers present: "{n} blockers · {m} warnings" in danger tone
  - warnings only: "{m} warnings" in caution tone
  - nothing: "Ready to complete" in ok tone
  - click jumps to the tab holding the first blocker, or to Review when there are only
    warnings
- Complete / Reopen Encounter button and the completed note, with today's disabled,
  pending and permission rules unchanged

Not shown: "Patient since", visit count, "last seen", second phone. The chart does not
load them and the sidebar and Overview already show them.

### Clinical strip (`components/ClinicalStrip.vue`, read-only)

- One card, three columns, each an icon plus uppercase label over pill chips:
  ALLERGIES · MEDICAL HISTORY · MEDICATIONS
- Allergy chips use the danger tone when allergies exist. "Not recorded" and "None
  known" are neutral, following the profile's `allergy_status`
- Footer row: Surgical and Habits inline, then "Reviewed {date}" or "History not yet
  reviewed" (`reviewed_on`)
- "Update history →" renders only when `window.do_health.openMedicalHistoryPanel` exists
- If the profile failed to load, show `DegradedSectionNotice` instead of empty pills

### Tabs

- Segmented row on a white card; label only. The `hint` lines are removed from
  `SECTION_TABS`
- Red dot:
  - Procedures, when any readiness blocker exists (both engines, inventory and
    follow-up, are driven by procedure marks today)
  - Review, when any blocker exists
- Count badges for procedures, photos, prescriptions; the Assessment tick stays
- The assessment mode toggle moves out of the tab into the Assessment card header

### Section card frame

Each active section renders inside one card (surface, 14px radius, `--chart-shadow`).
The header has the uppercase section label on the left and the section's existing
actions on the right. Panel internals are unchanged in phase 1.

### Tokens and CSS

- New `do_derma/public/js/chart/theme/chart_tokens.css`: the do_health `--ov-*` values,
  renamed `--chart-*`, declared on `.derma-chart-page`, with a
  `[data-theme="dark"] .derma-chart-page` twin. Imported once from the chart bundle
- New components use `<style scoped>` reading only `--chart-*` tokens
- `derma_chart.bundle.css`: delete only rules the shell makes dead (old encounter header,
  `.encounter-chip`, tab hint styles). Check brace depth before each deletion (early-closing
  `@media` trap). Add no new rules there. Do not fix the brace bug here

### Backend

- The chart context in `api.py` gains `clinical_profile`, built by do_health's
  `do_health.api.clinical_profile.get_clinical_profile(patient_doc)` inside
  `_safe_derma_context(_("Clinical profile"), None, …, errors)`
- No new endpoint; the existing chart gate runs first

### do_health (separate change, approval required)

Expose `openMedicalHistoryPanel` on `window.do_health`, taking the patient. Own branch
and PR in do_health. The chart feature-detects it, so phase 1 ships without it.

## Phase 2 (separate plan)

Move panel internals (Assessment, Procedures, Photos, Prescription, Review, consent
dialogs, consumables editor) onto `--chart-*` tokens and Overview pills/labels, panel by
panel, deleting the bundle CSS each panel stops using.

## Out of scope

- Right column cards (previous visit, account)
- Patient picker anywhere on the chart (the sidebar owns selection)
- Body map on the chart page
- Dead body-map state in `DermaChart.vue` (`selectedBodyTemplate`, `visibleMarks`,
  `loadBodyTemplate`, `chartOverlayMode`)
- Fixing the `@media` brace bug in `derma_chart.bundle.css`
- Any change to `health_sidebar.css`

## Testing

Python:
- Chart context includes `clinical_profile` for a patient
- A raising profile builder yields `clinical_profile = None` and records
  "Clinical profile" in the payload's errors

Browser (`dermaone.localhost`, 1280 / 1600 / 1920 px, light and dark):
- Hero, strip and tabs render; strip with and without allergies
- Previous-visit banner on an older encounter, Open latest works
- A blocker shows dots on Procedures and Review; the readiness line jumps to Procedures
- Complete is disabled while blocked under Block enforcement
- "Update history" hidden when do_health does not export the opener

Diff the suite against the known failures on `main`; do not expect it to be fully green.
