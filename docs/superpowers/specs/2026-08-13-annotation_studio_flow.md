# Annotation Studio Flow

Date: 2026-08-13
Status: **Implemented & verified** (2026-08-13) — see [Verification](#verification); deviations in [Reconciliation](#reconciliation--what-changed-vs-the-plan)

## Goal

The consultation popup becomes a plain sketchpad ("remove badges checkbox and
procedures button, and remove right sidebar"); the procedure popup gets a
calmer tagging flow ("tagging should be activated once click on procedure from
procedures sidebar and not the procedure annotation", "dont hide procedures
sidebar when click on drawing area"), body templates "show up based on patient
sex", and "when annotation saved user should view output image with
annotations details". Treatment-area styling is borrowed from
`~/Developer/develop/apps/annotation`.

## Decisions (user-confirmed in review)

- **Consultation = pure sketchpad**: no Procedures drawer, no badges checkbox,
  no right sidebar. Consultation-time procedure tagging (and with it the
  consultation-mark → procedure promotion path in this popup) is retired.
- **Badges checkbox stays in the procedure popup** (badges are already
  export-only — persisted JSON never contained them; only UI changes here).
- **Mark click ≠ tagging**: clicking an existing mark binds the variable editor
  to it but no longer re-arms placement mode; the drawer click is the only
  tagging trigger, and popup open never auto-arms.
- **Sex filter with "Show all" escape hatch**; missing/other sex or zero
  matches → show all. Client-side only.
- **Post-save side-by-side review dialog** (image ≈58% / legend, Print +
  Close); the same dialog replaces the thumbnail msgprint.
- **Port three-state area styling + Hide/Show areas toggle**; the floating
  variable card was rejected (sidebar layout stays for procedure popups).

## Current State (verified)

- One component serves both anchors (`DermaAnnotationStudio.jsx`, 744 lines);
  differences are anchor doctype/name, header text, resumed annotation, mark
  filter only.
- Drawer close-on-canvas-click is a transparent scrim
  (`DermaAnnotationStudio.jsx:580`, `derma_chart.bundle.css:4264-4269`) that
  swallows the first canvas click; `annotation-badges.spec.ts:38` double-clicks
  "Procedures" to work around it. `handleMarkSelected` also closes the drawer
  (`:469`) and **re-arms tagging** (`setActiveProcedure`, `:466`).
- Badges: computed in `collectBadgeItems`, injected as locked scene elements,
  stripped on persist (`EmbeddedExcalidraw.jsx:1210,1222`) — already
  export-only.
- Sex filtering does not exist; `patient.sex` is loaded (`api.py:224`) but
  unused; `Derma Body Template.gender` is reqd Female/Male.
- `save_derma_annotation` (`api.py:1950-2023`) returns the anchor's **newest**
  annotation row — wrong when an older annotation was resumed via the spec-B
  picker (the studio would then overwrite the wrong drawing on its next save,
  and the review dialog would show the wrong image).
- Template parts render as locked dashed `line` polygons with ray-cast
  hit-testing (`EmbeddedExcalidraw.jsx:611-706`); no state-dependent styling,
  no hide toggle.
- "Marks Placed" panel counts only marks placed this session
  (`placedMarkCount`, `:305,445`).
- Post-save: toast → refresh → close. No review screen. Thumbnail preview is a
  `frappe.msgprint` (`DermaChart.vue:1593-1605`).
- E2E: `annotation-badges.spec.ts`, `annotation-freehand.spec.ts`, and
  `annotation-canvas.spec.ts` all drive tagging through the **consultation**
  entry point + Procedures drawer — a flow this spec removes. They must move to
  a procedure anchor; a fresh Clinical Procedure helper is needed because the
  seeded one is shared.

## Non-Goals

- `_sync_chart_marks_for_annotation` and its four properties are untouched.
- No change to mark placement mechanics, stamp shapes, or `save_chart_mark`.
- No server-side template filtering; no `Derma Template Set` integration.
- The desk-form `annotations_button.js` viewer stays as-is.

## Design

### 1. Anchor-aware shell — `DermaAnnotationStudio.jsx`
`isProcedureAnchor = Boolean(context.clinicalProcedure)`. Consultation hides
the Procedures toggle, badges label, and right sidebar (`no-right` shell grid
variant); `handleMarkSelected` returns early. Procedure popup keeps everything.

### 2. Drawer + tagging — same file
Scrim deleted (element + CSS); drawers toggle only from the header.
`handleMarkSelected` sets `editingMark` + seeds values but no longer touches
`activeProcedure`/`selectedProcedures`/drawer. The variable editor binds to
`editingMark?.procedure || activeProcedure`; the banner and `tagging` shell
class show for either.

### 3. Sex filter — same file
`context.patientSex` (from `data.patient.sex`); default list = templates whose
`gender` matches (fallback to all when none match or sex unknown); "Show all"
toggle in the Templates drawer. Resumed selection is looked up in the full
list so an off-sex resume never silently swaps templates.

### 4. Area styling — `EmbeddedExcalidraw.jsx`
Part elements carry `base_color`/`base_opacity` in customData; new imperative
handles `setPartStates({selected, filled})` and `setPartsHidden(hidden)`
restyle the part layer: selected = solid stroke 3 / α0.4, filled = solid 2 /
α0.3, empty = dashed 1 / base α (three-state, per reference app
`App.jsx:372-384`); hidden flips opacity to 0. State lives in a ref and is
re-applied after every `renderTemplateParts`. A "Hide areas" header toggle
drives it. "Marks Placed" derives from the scene (distinct `markIdentity` of
`derma_mark` elements) instead of the session counter.

### 5. Saved-row response — `do_derma/api.py`
`save_derma_annotation` returns (and links to treatment entries) the row whose
name is the annotation actually saved, falling back to newest. This is the
single riskiest interaction with spec B's picker: without it, resuming an older
drawing hands the studio the newest annotation's name back.

### 6. Review dialog — `DermaChart.vue`
`openAnnotationReviewDialog(annotation)`: extra-large dialog, flex layout —
image ~58% / `annotation_data` legend right (70vh caps, per reference
`annotation_button.js:95-109`), Print (print window with escaped title, image,
stored legend) + Close, `on_hide` removes the wrapper. Called from `onSaved`
(after refresh) and from the annotations strip (replacing the msgprint).

What stays unchanged: `save_chart_mark`, mark fan-out, badge computation and
stripping, `EmbeddedExcalidraw` placement/export paths.

## Security

No new endpoint. `save_derma_annotation` keeps `_ensure_clinical_access`; its
return-shape change is covered by a new integration test. The review dialog
renders only server-stored `annotation_data` (escaped at generation) and
escaped titles/URLs.

## Acceptance Criteria

- Consultation popup: Templates/Fit/Cancel/Save only; drawing + template choice
  work; no tagging affordances anywhere.
- Procedure popup: drawer stays open across canvas clicks; clicking a mark
  edits its variables without entering placement mode; badges checkbox works
  as before.
- Templates drawer defaults to the patient's sex; Show all reveals the rest;
  empty-filter and unknown-sex cases fall back to all.
- Saving an older (picker-resumed) drawing updates that drawing, and the
  review dialog shows *it* — not the newest one.
- Review dialog appears after every save and from thumbnail clicks; Print
  produces image + legend.
- Areas: three-state styling reflects selection/values; Hide areas clears the
  overlay; marks counter reflects the canvas.

## Phases

1. Backend return fix + test. Exit: run-tests green.
2. Studio/Embedded/Chart UI. Exit: manual pass both anchors.
3. E2E migration (badges/freehand/canvas to procedure anchor, fresh-procedure
   helper, review-dialog handling in saveAndClose) + new consultation
   assertions. Exit: full suite green.

## Open Questions

- Should legacy consultation annotations containing tagged marks still render
  badges in consultation exports? Default: yes — badge layer stays computed;
  only the checkbox is hidden there.

## Reconciliation — what changed vs the plan

- **Mark click also disarms placement.** Clicking a mark while a procedure was
  armed would have left the stamp tool live under an "Editing" banner; editing
  now replaces placing (`setActiveProcedure("")` in `handleMarkSelected`).
- **The review dialog needed an explicit Close secondary action** — Frappe
  dialogs ignored a synthetic Escape in the e2e runs, and specs (plus users)
  want a visible way out next to Print.
- **E2E drawer clicks had to be scoped to `.derma-annotation-modal`**: the
  studio now opens over the procedures tab, whose own row button ("PAT-… -
  E2E Filler") shadows `getByRole("E2E Filler")` — 8 of the first run's 10
  failures were this one ambiguity.
- Sex-filter behaviour is covered by the client logic + manual pass only; the
  e2e seed has a single body template, so a filtered-vs-all assertion cannot
  distinguish outcomes there.

## Verification

- **Integration**: `bench --site dermaone.localhost run-tests --app do_derma` —
  **82 tests OK** (new: `test_resaving_an_older_annotation_returns_that_annotation`,
  RED-first against the newest-row response bug).
- **E2E**: annotation suites (`annotation-consultation`, `-badges`, `-freehand`,
  `-canvas`, `-anchoring`) — **23 passed (5.7m)** after the reconciliation
  fixes; full suite run recorded below.
- **Build**: `bench build --app do_derma` clean; no bundle renames; no migrate.
- **Lint**: changed Python (`api.py` edit region, `test_api.py` additions)
  clean under `pipx run ruff check`; whole-file format drift in both files is
  pre-existing and untouched.
- **Full e2e suite**: `npx playwright test` — **46 passed (6.3m)**.
- **Manual (browser, 2026-08-14)**, demo patient across both anchors:
  the consultation popup shows only Templates / Fit / Hide Areas / Cancel /
  Save with no right sidebar; the procedure popup keeps the Procedures drawer,
  badges checkbox and sidebar, and its "Marks Placed" panel reported the 8
  marks already on the canvas rather than a session count; the Procedures
  drawer **stayed open across a canvas click** (scrim removed); saving opened
  the review dialog with the badge-stamped output image beside the details
  table and Print/Close.

## Files to touch (summary)

| File | Change |
|---|---|
| `do_derma/api.py` | return saved row, link saved annotation |
| `do_derma/tests/test_api.py` | saved-row response test |
| `do_derma/public/js/chart/annotation/DermaAnnotationStudio.jsx` | anchor-aware shell, tagging, sex filter, counters |
| `do_derma/public/js/chart/excalidraw/EmbeddedExcalidraw.jsx` | part-state styling, hide toggle |
| `do_derma/public/js/chart/DermaChart.vue` | patientSex, review dialog |
| `do_derma/public/js/chart/derma_chart.bundle.css` | scrim removal, no-right grid, review layout |
| `e2e/helpers/derma.ts` | freshClinicalProcedure/cleanup helpers |
| `e2e/tests/annotation-badges.spec.ts` | procedure-anchor rewrite |
| `e2e/tests/annotation-freehand.spec.ts` | procedure-anchor rewrite |
| `e2e/tests/annotation-canvas.spec.ts` | procedure-anchor tagging parts |
| `e2e/tests/annotation-anchoring.spec.ts` | saveAndClose dismisses review dialog |
| `e2e/tests/annotation-consultation.spec.ts` | *(new)* sketchpad + sex-filter assertions |
