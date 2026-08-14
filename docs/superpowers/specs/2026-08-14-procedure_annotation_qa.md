# Procedure Annotation Popup — QA Findings

Date: 2026-08-14
Status: **Findings only — not implemented.** A browser pass over the procedure-anchored
annotation studio, the counterpart to the consultation pass recorded in
[`2026-08-14-annotation_studio_safety.md`](2026-08-14-annotation_studio_safety.md) and
[`2026-08-14-annotation_output_fidelity.md`](2026-08-14-annotation_output_fidelity.md).

## Goal

Drive every control of the procedure popup as a clinician would and record what is wrong, so the
fixes can be specced deliberately rather than patched ad hoc. Nothing here is fixed yet.

**Environment**: demo patient `PAT-2026-1448`, encounter `HLC-ENC-2026-03308`, procedures
`HLC-CPR-2026-02868` (DEMO Filler Cheek, one saved drawing) and `HLC-CPR-2026-02869`
(DEMO Laser Resurfacing, none). Chromium 1600×1000, bundles built from `fix/annotation-studio-qa`.

## What already works

Verified good, and worth not breaking:

- Header is complete and anchor-correct: Templates / Procedures / Fit / Hide Areas / Badges /
  Cancel / Save, with the right sidebar (Procedure Variables, Selected Area, Marks Placed).
- The **picker** works: a procedure with saved drawings offers *New Annotation* alongside *Edit*
  per drawing — the two paths the consultation anchor was missing.
- Tagging reads well: arming from the drawer shows "Tagging as: … — draw over the affected skin"
  with *Stop Tagging*, and the tool switches to match the template's marker behaviour (freehand
  for Laser Resurfacing, stamp for Filler Cheek).
- The **Procedures drawer stays open across canvas clicks** (the scrim removal held).
- **Area hit-testing works**: drawing inside an outline resolves *Selected Area → DEMO Left Cheek*
  and binds that area's own variables; the area switches to its selected styling.
- `Marks Placed` tracks the canvas, not the session.
- Carried over from the fixes landed today and confirmed on this anchor: area outlines render,
  no Library button, one number per mark, close guard prompts only when dirty, review dialog
  titled `DEMO Face Map · 14-08-2026 20:31` rather than a docname hash.

## Findings

### 1. Discarding a drawing keeps the marks — the promise is only half kept (worst)

Marks are written to the server the instant they are drawn (`onMarkPlaced` → `save_chart_mark`,
toast "Mark saved"), before *Save Annotation*. `Cancel` → "Discard this drawing? Unsaved changes
will be lost." → *Yes* removes the drawing but **not the marks**.

Reproduced: drew one tagged freehand mark, discarded, and `DCM-2590072` remained with
`annotation=None`. It is not invisible bookkeeping — the procedures tab then showed
`1 mark(s) · DEMO Aesthetics · DEMO Face Map` on that row, so the patient's chart carries a
clinical record the practitioner believes they threw away.

Real-time saving is deliberate (`_sync_chart_marks_for_annotation` re-links stamps rather than
recreating them), so the fix is not "stop saving early". The dialog has to either tell the truth
("the drawing is discarded; N marks stay on the chart") or the discard has to delete the marks
this session created and left unlinked. **This defect predates today's work** — `Cancel` always
discarded instantly — but the new confirm makes a promise that was previously only implied.

### 2. A mark with no variables filled in vanishes from the legend and the printout

`collectBadgeItems` skips any mark whose procedure variables are all empty
(`DermaAnnotationStudio.jsx:116-118`, `if (!hasParams) continue`).

Reproduced: placed a *DEMO Filler Cheek* stamp without touching Product / Units / Plane. The
header read **`Badges (1)`** while **`Marks Placed` read 2**, and the saved output shows the stamp
on the image with **no number** and **no row in the legend table** — the record shows a mark
nobody can identify. The other mark appeared only because its template supplied defaults
(`dose: 0, passes: 0, severity: Mild, status: Active`).

This is the same class as the duplicate-numbering defect fixed today, in the opposite direction,
and it is worse: that one printed a number twice, this one omits the mark entirely.

### 3. Resuming a procedure drawing opens unfitted, and its areas never draw

Opening the saved drawing on `HLC-CPR-2026-02868` gave a blank canvas at **100%** zoom. The
content is there — pressing *Fit* revealed the template at 88% — so the initial `fitToTemplate`
ran before the template image finished rehydrating. The consultation resume path does not show
this because its scene carries the image; here `derma_template` is `{"name": "DEMO Face Map"}`
with **no `image` key**, so the picture can only be rebuilt later, from the template row.

With the template finally visible, **no area outlines are drawn at all**, yet `Hide Areas` is
offered — so `getRenderedPartCount()` counted elements that are not visible. Excalidraw's
zoom-to-fit-all (`Shift+1`) does not move the view, which means those part elements have
degenerate bounds: they were built by `createTemplatePartElements` against
`getTemplateBounds(api)` while the template image was still unmeasured.

The `fitToTemplate` retry added today guards the *canvas* not being measured; it does not guard
the *template element* not being measured. Same race, one level down.

### 4. The procedures drawer lists every template on the site, unfiltered and unsearchable

Eleven entries for this patient, including the `E2E ` test fixtures and unrelated site templates
(Facial, Laser), with no search box and no filter by the procedure's own category — while the
Templates drawer beside it does filter, by patient sex. A clinic with a real template list will
scroll. Seed fixtures leaking in is dev-clone noise, but the absent filter is not.

### 5. Cosmetic: the header repeats the patient name

`Procedure — DEMO Amina Haddad - DEMO Laser Resurfacing`: the Clinical Procedure's own name
already embeds the patient, so the name appears twice in one line.

## Non-Goals for the eventual fix

- Do not change when marks are saved. Real-time persistence is what makes stamp re-linking
  idempotent; finding 1 is about honesty and cleanup, not about deferring the write.
- Do not touch `_sync_chart_marks_for_annotation` or its four properties.
- The `/private/files/…` template images stay broken; that is site data.

## Suggested phases

1. **Finding 2** — the record is wrong today and it is the smallest change: decide whether an
   unparameterised mark is legend-worthy (it should be: it is still a mark) and drop the
   `hasParams` gate, or number it with an empty parameter cell.
2. **Finding 1** — make discard truthful. Either name the surviving marks in the dialog or delete
   the unlinked ones this session created.
3. **Finding 3** — fit and part geometry both wait on the template element having non-zero
   bounds, not just the canvas.
4. **Findings 4 and 5** — drawer filter/search, header wording.

## Verification

Manual browser pass only; no code changed, so no test run. Reproduction steps for each finding
are inline above, with the exact doc names and counts observed.

### Left behind

`DCM-2590072` (the orphan from finding 1) and the marks/drawing from the finding-2 reproduction
are still on the demo patient. `bench --site dermaone.localhost execute
do_derma.demo_seed.teardown_demo_data` then `setup_demo_data` resets them.
