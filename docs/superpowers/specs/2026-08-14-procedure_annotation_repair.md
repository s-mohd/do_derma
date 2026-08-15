# Procedure Annotation Popup — Repair

Date: 2026-08-14
Status: **Implemented & verified** (2026-08-15) — all four phases; see
[Verification](#verification). Phases 2 and 3 both deviated from the plan (phase 2 needed a new
endpoint; phase 3's race turned out to be a template element that could not be painted at all) —
see [Reconciliation](#reconciliation--what-changed-vs-the-plan).

The findings this spec repairs were recorded by a browser pass in
[`2026-08-14-procedure_annotation_qa.md`](2026-08-14-procedure_annotation_qa.md); each phase below
names the finding it closes. The earlier fixes on this anchor are in
[`2026-08-14-annotation_studio_safety.md`](2026-08-14-annotation_studio_safety.md) and
[`2026-08-14-annotation_output_fidelity.md`](2026-08-14-annotation_output_fidelity.md).

## Goal

The procedure-anchored annotation studio produces a record the practitioner cannot trust:

1. **A mark placed without filling any procedure variable is dropped from the legend and from the
   numbering** — the stamp prints with no number and no row, so the saved sheet shows a mark
   nobody can identify (finding 2).
2. Discarding a drawing keeps the `Derma Chart Mark` rows it created, against what the confirm
   dialog promises (finding 1).
3. A resumed procedure drawing opens unfitted and draws no area outlines (finding 3).
4. The procedures drawer is unfiltered and unsearchable; the header repeats the patient name
   (findings 4 and 5).

Phase 1 closes the first, which is the one that corrupts the clinical record rather than merely
annoying the user.

## Decisions

- **Discarding deletes the marks the session placed, rather than confessing they survive** →
  the practitioner's mental model is that Cancel throws the work away, and a truthful-but-keeping
  dialog would leave them deleting rows by hand from the procedures tab → trade-off: the studio
  now owns a destructive action, so the rule for what may be destroyed lives on the server, not in
  the popup → rejected: rewording the confirm to name the survivors, which is honest but leaves
  the chart holding a record nobody wanted.
- **A new `discard_chart_marks` endpoint rather than reusing `delete_chart_mark`** →
  `delete_chart_mark` refuses any mark linked to a non-cancelled `Clinical Procedure`, and every
  procedure-anchored mark is linked to its anchor by construction, so it refuses all of them
  (verified: HTTP 417, *"This mark is linked to an active Clinical Procedure and cannot be
  deleted"*) → trade-off: two deletion rules to keep straight, so the new one is named for the
  session it undoes and documents why it is separate → rejected: loosening
  `delete_chart_mark`'s guard, which would also loosen the desk-facing delete it was written for.
- **A tagged mark earns a badge and a legend row whether or not its variables are filled** →
  the mark's identity is its procedure template, not its parameters; a stamp on the cheek tagged
  *DEMO Filler Cheek* is a complete clinical statement even with Units blank → trade-off: legends
  grow a row for marks that carry nothing but a name, and every drawing with one tagged mark is
  now saved as `Predefined Annotations` rather than `Free Drawing` → rejected: numbering the mark
  on the canvas but leaving it out of the table, which would print a number pointing at no row.
- **Areas keep their `hasValues` gate** → an area outline with no variables filled is scene
  furniture, not a placed mark; the practitioner never "placed" it, it came from the template →
  trade-off: the two branches of `collectBadgeItems` now read differently, so the asymmetry is
  commented → rejected: dropping both gates, which would number every part of the body map.
- **The empty parameter cell renders an em dash** → an empty `<td>` reads as a rendering fault in
  a printout → trade-off: none.

## Current State (verified)

Phase 1 is `do_derma`-owned frontend only. Phase 2 adds one whitelisted endpoint to `api.py`; no
doctype, patch or fixture changes anywhere in this spec.

- `collectBadgeItems` — `public/js/chart/annotation/DermaAnnotationStudio.jsx:109-148`. The mark
  branch skips an element whose `customData.procedure_variables` are all empty
  (`:117-118`, `if (!hasParams) continue`). The area branch has the parallel `hasValues` gate at
  `:132-134`. Items are sorted top-to-bottom and numbered `index + 1` at `:147`, so a skipped mark
  does not merely lose its row — it shifts every number below it.
- One computation feeds three surfaces: the canvas badge layer
  (`badgeElements(badgeItems)`, `:222`, pushed at `:401-403`), the header count
  (`Badges (n)`, `:694-696`, exposed to the specs as `data-badge-count`), and the persisted legend
  table (`generateAnnotationDataHTML(badgeItems)`, `:179-198`, saved as `annotation_data` at
  `:635`). Fixing the gate therefore fixes screen, PNG and table together — that coupling was the
  point of `2026-08-14-annotation_output_fidelity.md` phase 2.
- `markCount` (`:406-412`) counts `derma_mark` elements on the canvas with no variable gate at
  all. **That is the disagreement the QA pass photographed**: `Marks Placed 2` beside
  `Badges (1)`.
- `generateAnnotationDataHTML` (`:179-198`) filters empty values out of the parameter string, so
  an unparameterised mark already renders an empty cell once it reaches the table.
- `annotation_type` is chosen by `badgeItems.length` (`:631`).
- `e2e/tests/annotation-badges.spec.ts:78-91` asserts today's behaviour in the words
  *"A mark with no variable values is not badge-worthy"*, expecting `data-badge-count` `0` after
  the first stamp. **It is the RED test for this phase** — it must be rewritten to the new
  contract and watched to fail.
- Marks are written to the server at placement time (`onMarkPlaced` → `save_chart_mark`), which
  phase 2 has to reckon with; phase 1 does not touch persistence.

Phase 2:

- `requestClose` — `DermaAnnotationStudio.jsx:467-473` (pre-fix). It compares `userSignature()`
  against `savedSignature` and, when they differ, confirms and calls `onClose()`. Nothing there
  knows a mark was ever written, so *Yes* discards the scene and leaves the rows.
- `handleMarkPlaced` (`:539-576` pre-fix) is the only place a mark is created from the studio, and
  it already holds the saved doc (`response.message`) — the session's own list of marks is one
  line away from existing.
- **`delete_chart_mark` cannot be reused** (`api.py:2727-2739`, `do_derma`): it throws
  *"This mark is linked to an active Clinical Procedure and cannot be deleted"* whenever
  `mark.clinical_procedure` points at a procedure that is submitted **or** whose status is not
  `Cancelled`. A procedure-anchored mark always carries its anchor, and a live anchor is a
  `Draft`, so the guard rejects every mark this phase must remove. Confirmed against the running
  site: `frappe.client` call returned **417 ValidationError** with that message.
- `openDermaAnnotationStudio` (`:891-910` pre-fix) hard-wires `onClose` to unmount, and
  `DermaChart.vue:1691-1712` passes only `onSaved`, so the host chart has no way to learn that a
  close changed the server. `onSaved` is what refreshes the chart today (`refresh()` at
  `DermaChart.vue:1709`).
- `Derma Chart Mark` (`do_derma`) carries `annotation`, `finding`, `treatment_entry` and
  `photo_set` links (`DERMA_MARK_FIELDS`, `api.py:78-100`) — the four ways a mark can already be
  part of the record.

## Non-Goals

- Not changing when marks are saved, nor `_sync_chart_marks_for_annotation` or any of its four
  properties.
- Not touching the badge geometry, the toggle, the scene-signature loop guard, or the review
  dialog — only which items reach them.
- Not touching the area branch's gate or part rendering (phase 3 owns the rendering race).
- No schema change: no doctype, patch or fixture is touched, so **no migrate is required**. Phase
  2 adds one endpoint to `api.py`; phase 1 changed no Python at all.
- Not changing `delete_chart_mark` or the desk-facing delete it guards.
- Not deleting marks a *previous* session placed, nor marks the practitioner drew and then erased
  from the canvas without discarding — the studio only undoes what it wrote this session.
- Not making Save Annotation delete anything: saving keeps every mark, as it always has.
- Existing legends stored on saved annotations are not regenerated; `annotation_data` is a
  snapshot taken at save time and stays as it was.

## Design

Delete the `hasParams` gate from the mark branch of `collectBadgeItems` so that every
non-deleted, non-duplicate `derma_mark` element carrying a `procedure_template` becomes an item.
Everything downstream — numbering, badge layer, header count, legend table — already follows the
item list, so no other call site changes.

### 1. Mark branch keeps every tagged mark — `DermaAnnotationStudio.jsx`

```jsx
    const procedureTemplateName = element.customData?.procedure_template
    if (!procedureTemplateName) continue
    // A tagged mark is legend-worthy on its template alone: unfilled variables must not drop it
    // from the numbering, or the sheet prints a mark with no row. Areas below are different -
    // an untouched area outline was never placed by the practitioner.
    const params = element.customData?.procedure_variables || element.customData?.variables || {}
```

### 2. Empty parameter cell reads as empty — `generateAnnotationDataHTML`

```jsx
    const params = Object.entries(item.params || {})
      .filter(([, value]) => value !== "" && value !== null && value !== undefined)
      .map(([key, value]) => `<b>${escapeHtml(key)}</b>: ${escapeHtml(value)}`)
      .join(", ")
    ...
      <td style="padding:6px 10px;">${params || "\u2014"}</td>
```

Unchanged: `markIdentity` de-duplication (a stamp is several elements, one badge), the sort, the
area branch, `badgeElements`, the toggle, and the save payload's shape.

### 3. The session remembers what it wrote — `DermaAnnotationStudio.jsx`

A ref, not state: nothing renders from it, and a re-render must not reset it.

```jsx
  const sessionMarks = useRef(new Set())
  ...
      const mark = response.message
      if (mark?.name) sessionMarks.current = new Set(sessionMarks.current).add(mark.name)
  ...
      savedSignature.current = userSignature()
      // Saved marks belong to the annotation now; a later discard must not reach for them.
      sessionMarks.current = new Set()
```

Closing then guards on both halves of what is at stake, and the confirm names the marks:

```jsx
  function requestClose() {
    const placedMarks = [...sessionMarks.current]
    const isDrawingDirty = savedSignature.current !== null && userSignature() !== savedSignature.current
    if (!isDrawingDirty && !placedMarks.length) return onClose?.()
    window.frappe.confirm(discardPrompt(placedMarks.length), () => discardDrawing(placedMarks))
  }
```

`discardPrompt(0)` is the old wording verbatim, so a consultation sketch prompts exactly as before.
`discardDrawing` calls the endpoint once with every name, keeps whatever the server refused, and
tells the practitioner about it rather than closing on a half-kept promise. **If the call itself
fails the studio stays open** — closing then would lose the drawing *and* keep the marks, which is
the defect this phase exists to remove.

### 4. `discard_chart_marks` — `api.py`

The rule for what a discarded session may destroy is the server's, not the popup's.

```python
@frappe.whitelist()
def discard_chart_marks(names: str | list[str]):
	_ensure_clinical_access()
	requested = json.loads(names) if isinstance(names, str) else list(names or [])
	for name in requested:
		if not name or not frappe.db.exists("Derma Chart Mark", name):
			continue
		mark_doc = frappe.get_doc("Derma Chart Mark", name)
		if _is_mark_documented(mark_doc):
			kept.append(name)
			continue
		mark_doc.delete(ignore_permissions=True)
```

`_is_mark_documented` is the whole rule: any of `annotation`, `finding`, `treatment_entry`,
`photo_set`, or a `clinical_procedure` with `docstatus == 1`. Being linked to a *draft* procedure
is not documentation — that is the anchor the mark was drawn on, and it is precisely what
`delete_chart_mark` refuses. A name that no longer exists is skipped, not thrown on, so a
double-click on *Yes* is safe.

### 5. The host chart hears about it — `DermaAnnotationStudio.jsx` / `DermaChart.vue`

```jsx
  const close = (result) => {
    root.unmount()
    mount.remove()
    options.onClose?.(result || {})
  }
```

```js
    onClose: async (result) => {
      if (result?.marksChanged) await refresh()
    },
```

Only a discard that had marks to remove sets `marksChanged`, so an ordinary close still costs no
round trip, and a save still refreshes exactly once through `onSaved`.

Unchanged: when marks are written (`onMarkPlaced` is untouched), `_sync_chart_marks_for_annotation`
and all four of its properties, `delete_chart_mark`, and the scene payload.

### 6. Nothing is measured against an unmeasured template — `EmbeddedExcalidraw.jsx`

`getTemplateBounds` stops inventing a template. Its `|| 1` fallback is what produced the 1px
outlines the QA pass photographed, and every caller already handles `null`
(`buildPlacementPayload` and `buildDrawnPlacementPayload` fall back to 50%, `renderChartMarks`
returns, `renderTemplateParts` clears the layer).

```jsx
function getTemplateBounds(api) {
  const template = getTemplateElement(api)
  if (!template || template.isDeleted) return null
  if (!isPositiveSize(template.width) || !isPositiveSize(template.height)) return null
  return { x: template.x || 0, y: template.y || 0, width: template.width, height: template.height }
}
```

The wait is one bounded rAF loop, in the same shape as the canvas retry it sits below:

```jsx
function whenTemplateMeasured(api, expectsTemplate = true) {
  if (!api || !expectsTemplate || getTemplateBounds(api)) return Promise.resolve()
  return new Promise((resolve) => { /* rAF until measured, TEMPLATE_MEASURE_RETRY_LIMIT frames */ })
}
```

`loadSceneIntoApi` awaits it before fitting (`expectsTemplate` read off the hydrated elements, so
the consultation sketchpad never waits), `insertTemplateImage` awaits it before fitting, and the
marks effect and the `renderTemplateParts` bridge method await it before drawing. `fitToTemplate`
ignores a template element it cannot measure rather than parking the view on an invisible box, and
`getRenderedPartCount` counts only outlines with real bounds — so `Hide Areas` is offered when
areas are visible, not when they merely exist.

### 7. A template that cannot be painted is rebuilt in place — `EmbeddedExcalidraw.jsx`

**This is the actual defect behind finding 3.** A scene can carry a template element with no
`fileId` and a `customData.template` stub with no `image` — `demo_seed._demo_scene` writes exactly
that. `hydrateTemplateImageFiles` cannot rebuild it (no `fileId`, no URL), so the element is a
phantom: fit lands on it, areas trace it, and nothing is drawn.

```jsx
  async function rebuildUnrenderableTemplate() {
    if (!api || isTemplateRenderable(api)) return
    const template = chartTemplateRef.current
    const sceneTemplateName = getTemplateElement(api)?.customData?.template?.name
    if (!template?.image) return
    if (sceneTemplateName && sceneTemplateName !== template.name) return
    await loadTemplateIntoCanvas(api, template, latestTemplateImage, loadingTemplateImage, templateLoadGeneration)
  }
```

Two properties make that safe:

- **The rebuild keeps the box.** `templateGeometry` reuses the previous element's `x/y/width/height`
  when the same template is being replaced, and fits to the canvas only for a first insert or a
  switch to another silhouette. Moving the box would slide every stroke and mark off the anatomy.
- **The rebuild keeps the drawing.** `insertTemplateImage` used to hand `updateScene` the image
  alone (`const existing = []`), so the resize watcher's repair replaced the whole scene. It now
  keeps every non-template element. That wipe — not the fit — is why the QA pass saw `Hide Areas`
  offered over a canvas with no outlines on it: the count was taken before the scene was replaced.
  A side effect worth naming: switching to another body template mid-drawing no longer erases what
  is on the canvas either. Silently discarding a drawing was never the intended behaviour of a
  picker click, and no spec asserted it.

The name guard is the boundary: a drawing made on another silhouette is left as it is rather than
silently re-backed with the chart's current body template.

### 8. The procedures drawer filters to the anchor's category and takes a search — `DermaAnnotationStudio.jsx`

The drawer listed every derma-flagged `Clinical Procedure Template` on the site. It now narrows to
the category of the template the anchor procedure was booked with, using **the same rule the body
template picker already uses for patient sex** — filter to what this anchor is for, and fall back
to everything rather than to an empty picker:

```jsx
const anchorProcedureCategory = useMemo(
  () => procedures.find((row) => row.name === context.procedureTemplate)?.custom_derma_category || "",
  [procedures, context.procedureTemplate],
)
const categoryMatchedProcedures = useMemo(() => {
  if (!anchorProcedureCategory) return procedures
  const matched = procedures.filter((row) => row.custom_derma_category === anchorProcedureCategory)
  return matched.length ? matched : procedures
}, [procedures, anchorProcedureCategory])
```

`visibleProcedures` then applies the search string over the label, the category and the
description. The escape hatch is the templates drawer's checkbox, worded for categories
(`data-test="annotation-show-all-procedures"`), and it appears only when the filter is actually
holding rows back. An empty result says so (`data-test="annotation-procedure-empty"`) instead of
rendering a blank panel.

`custom_derma_category` is already on every row `get_derma_chart_context` returns
(`DERMA_TEMPLATE_FIELDS`, `api.py:129`), so **no endpoint and no schema check changes**; a site
whose templates carry no category falls through to the unfiltered list by the same guard.

### 9. The anchor is named once — `DermaAnnotationStudio.jsx` / `DermaChart.vue`

`annotateProcedure` now passes `procedureTemplate` (the `Clinical Procedure Template` docname)
beside the existing `procedureLabel`, through the picker and into `context`. The header prefers it,
because a Clinical Procedure's own name embeds the patient:

```jsx
function anchorDescription(context = {}) {
  const patientName = context.patientName || context.patient || ""
  const anchor = context.clinicalProcedure
    ? `${__("Procedure")}: ${procedureAnchorLabel(context)}`
    : __("Consultation")
  return [patientName, anchor].filter(Boolean).join(" — ")
}
```

`procedureAnchorLabel` strips a `"<patient> - "` prefix when it has to fall back to the display
name, so an anchor opened from a surface that never learned the template still reads once. Both
branches now lead with the patient, so the consultation and procedure headers are one shape.

## Security

`discard_chart_marks` is a new whitelisted endpoint that **deletes patient data**, so it calls
`_ensure_clinical_access()` before reading its arguments — the same authorization boundary every
other endpoint in `api.py` uses, and the reason `ignore_permissions=True` on the delete is
acceptable. `TestDiscardChartMarks.test_is_gated` proves a user without a `CLINICAL_ACCESS_ROLES`
role gets `frappe.PermissionError`, and `TestClinicalAccessGate` continues to cover the module.

The blast radius is bounded server-side rather than by the caller: `_is_mark_documented` refuses
any mark that another record depends on, so a hostile or buggy caller handing over a list of
arbitrary mark names still cannot remove one that is part of an annotation, a finding, a treatment
entry, a photo set, or a submitted procedure. `TestDiscardChartMarks` asserts each refusal.

## Acceptance Criteria

- A stamp placed with every procedure variable blank raises `Badges` to 1 and is numbered on the
  canvas.
- `Badges (n)` equals `Marks Placed` for any drawing whose marks are all tagged.
- The saved `annotation_data` table carries one row per mark, in canvas order, with an em dash in
  the parameter cell of an unparameterised mark.
- Regression: a mark **with** variables still produces exactly one badge, not one per stamp
  element, and its parameters still print.
- Regression: badges still never persist into the scene JSON, and the badge sync still settles
  instead of looping.
- Regression: areas with no values filled are still not numbered.
- Discarding a drawing after placing two marks leaves zero marks on the procedure, and the
  procedures tab behind the studio says so without a manual reload.
- The confirm names the count it is about to remove; with nothing placed it reads exactly as it
  did before.
- A mark the session did not place — one from a previous visit or planted by another surface —
  survives the discard.
- A mark the server refuses (annotation, finding, treatment entry, photo set, or a submitted
  procedure) survives, and the practitioner is told how many stayed.
- Regression: Save Annotation still keeps every mark, and closing an untouched studio still costs
  no round trip and no prompt.
- A resumed procedure drawing opens at the same zoom its first open had, not at an untouched 100%.
- A resumed drawing shows its area outlines, and `Hide Areas` is offered only when outlines are
  actually on the canvas.
- A drawing whose template image was never persisted — no `fileId`, no image URL on the stub —
  gets its picture rebuilt, in the box the scene already had, and keeps every mark and stroke.
- A drawing made on a different body template than the one the chart currently shows is left with
  its own background rather than re-backed.
- The procedures drawer opens showing the anchor procedure's own category, and typing in the
  search box narrows it to the matching templates.
- A search that matches nothing says so rather than showing an empty panel, and clearing it
  restores the list.
- A site whose templates carry no category, or whose anchor's category matches nothing, still
  gets the full list rather than an empty drawer.
- The header names the patient once and names the procedure by its template.

## Phases

1. **Finding 2 — every tagged mark is legend-worthy.** *Exit:* an unparameterised stamp is
   numbered on canvas and printed in the legend; `annotation-badges.spec.ts` green on the new
   contract. **Done.**
2. **Finding 1 — truthful discard.** Delete the marks this session created and left unlinked, and
   name them in the confirm. *Exit:* after a discard, the procedures tab's mark count matches what
   the dialog said would happen. **Done.**
3. **Finding 3 — resume race.** Fit and part geometry both wait on the template *element* having
   non-zero bounds, not just the canvas. *Exit:* a resumed procedure drawing opens fitted with its
   area outlines drawn. **Done.**
4. **Findings 4 and 5 — drawer filter/search, header wording.** *Exit:* the drawer filters to the
   procedure's own category with a search box; the header names the patient once. **Done.**

## Open Questions

- Should an untagged freehand stroke (a `derma_mark` with no `procedure_template`) also be
  numbered? *Default:* no — it carries no clinical identity at all, and the consultation anchor is
  a plain sketchpad by design.
- Should `annotation_type` still switch on `badgeItems.length` now that the count is easier to
  reach? *Default:* yes; a drawing with a tagged mark genuinely is a predefined annotation.
- Should a mark the practitioner erases from the canvas mid-session be deleted too, rather than
  waiting for a discard? *Default:* no — that is a separate defect (an erased mark survives a
  *save* as well), and undoing it belongs with the fan-out, not with the close button.

## Reconciliation — what changed vs the plan

- **Phase 2 needed a backend endpoint; the plan said the spec had none.** `delete_chart_mark` was
  the obvious tool and it cannot be used: it refuses every mark linked to a non-cancelled
  `Clinical Procedure`, which is every procedure-anchored mark. Discovered by watching the
  browser spec fail with the marks still present, then reproduced directly against the endpoint
  (**417**, *"This mark is linked to an active Clinical Procedure and cannot be deleted"*). The
  spec now carries a `discard_chart_marks` endpoint, a Security section, and Python coverage —
  none of which phase 1 needed.
- **`onClose` grew a result argument.** The plan did not mention refreshing the chart, but
  deleting rows behind a modal and leaving the tab showing them is the same class of lie the phase
  set out to fix. `openDermaAnnotationStudio` now forwards a `{ marksChanged }` result and
  `DermaChart.vue` refreshes on it.
- **Phase 3 was not a frame race.** The plan read the QA note literally — wait a frame for the
  template element to be measured — and a spec written to that contract passed on the shipped
  bundle, twice, even with the settle window cut to 1.5s. The real cause is a template element the
  canvas cannot paint: `demo_seed._demo_scene` (and any drawing saved the same way) stores one with
  no `fileId` and a `{"name": …}` template stub, so `hydrateTemplateImageFiles` has nothing to
  rebuild from. The fit and the outlines were landing on a phantom, and the resize watcher's late
  repair then replaced the entire scene — `insertTemplateImage` passed `updateScene` the image
  alone. A spec seeded with that scene shape failed red (`data-mark-count` `0`, *"rebuilding the
  template image threw the drawing away"*). The measured-bounds guard the plan asked for is still
  here and still correct; it is the smaller half of the phase.
- **`insertTemplateImage` no longer replaces the scene, and a rebuild keeps the previous box.**
  Neither was in the plan. Both are forced by the above: repairing a template must not cost the
  drawing, and must not move the anatomy under marks that were placed against it.
- **The bench's job queue blocked the browser verification, not the code.** Every HTTP delete
  returned **503 QueueOverloaded** — the `default` RQ queue held its 600-job cap of
  `delete_dynamic_links` jobs left by earlier e2e runs with no worker consuming them (oldest
  2026-08-11). Drained with `bench worker --queue default --burst`; nothing in the app changed.
  Worth knowing before debugging a "delete does nothing" report on this bench.

## Verification

### Phase 1

Frontend only, so `bench build --app do_derma` is required; no bundle filename changed, so the
`frappe.require` contract holds. No migrate, no Python change — `ruff` and the Frappe test runner
have nothing to say about this phase, and neither was run.

**Browser (Playwright, headless Chromium 1600×1000, demo `PAT-2026-1448` /
`HLC-CPR-2026-02869` DEMO Laser Resurfacing).** Armed the procedure, left Product / Units / Plane
blank, drew one freehand stroke: the stroke was numbered **1** on the canvas, the header read
`Badges (3)` and the sidebar `3 tagged mark(s) on this drawing` — the two counts agree, where the
QA pass photographed `Badges (1)` beside 2 marks.

**End-to-end, `npx playwright test annotation-` — 31 passed** (7.1m), covering
`annotation-badges`, `-canvas`, `-consultation`, `-freehand`, `-anchoring` and `-toolbar-button`.
Within that, `annotation-badges.spec.ts` was **watched red first**: on the pre-fix bundle the three
rewritten assertions failed (`Expected "1", Received "0"` on the blank stamp, the same on the count
parity, `Expected "2", Received "1"` on the saved table), and all seven passed after the gate came
out and the bundle was rebuilt.

The legend assertion moved during the run: `generateAnnotationDataHTML` first emitted `&mdash;`,
and the saved `annotation_data` came back holding the decoded character, so the source now writes
`—` directly rather than the entity.

The rest of the browser suite — `tab-spine`, `assessment-modes`, `chart-context`,
`feature-toggles`, `orphan-triage` — **21 passed** (30.8s).

**Not yet run:** `bench --site dermaone.localhost run-tests --app do_derma`, because no Python,
patch or fixture was touched.

### Phase 2

**Integration (Frappe runner).** `bench --site dermaone.localhost run-tests --module
do_derma.tests.test_api` — **41 passed**, of which the five new
`TestDiscardChartMarks` cases were **watched red first** (`AttributeError: module 'do_derma.api'
has no attribute 'discard_chart_marks'`) before the endpoint existed. The whole app suite,
`run-tests --app do_derma`, is **89 passed**.

**Lint.** `pipx run ruff check` and `ruff format --diff` over `api.py` report only the
pre-existing `RUF005` finding and pre-existing formatting drift, neither inside the new code.

**Browser (Playwright).** New `e2e/tests/annotation-discard.spec.ts`, three specs, also watched
red first on the shipped bundle (the confirm carried no count; both mark assertions failed with
the rows still on the chart). Green after the endpoint, the studio change and
`bench build --app do_derma`. The full suite is **54 passed** (8.2m), so the consultation close
guard, the badge specs and the tab spine are all unaffected.

No migrate: no doctype, patch or fixture changed. No bundle filename changed.

**Not yet run:** nothing outstanding for this phase.

### Phase 3

Frontend only: `bench build --app do_derma` required, no bundle filename changed, no Python, patch
or fixture touched, so no migrate and nothing for `ruff` or the Frappe runner to say.

**Browser (Playwright).** New `e2e/tests/annotation-resume.spec.ts`, two specs. The second —
*"rebuilds a template that cannot render without losing the drawing"* — was **watched red first**
on the shipped bundle: `expect(locator).toHaveAttribute` failed with `Expected "1", Received "0"`
on `data-mark-count`, the drawing gone after the rebuild. Green after the change and a rebuild.

The first spec, *"opens a saved drawing fitted to its template, with the areas drawn"*, **passed on
the pre-fix bundle** and is kept as a regression guard rather than claimed as a red test — see the
Reconciliation note above. It asserts the resumed zoom equals the first open's zoom (Excalidraw
renders it as the reset-zoom label) and that `Hide Areas` is offered.

`npx playwright test annotation-` — **36 passed** (8.4m), so badges, canvas, consultation, discard,
freehand, anchoring and the toolbar button are unaffected by the strict bounds and the
scene-preserving insert. The rest of the suite — `tab-spine`, `assessment-modes`, `chart-context`,
`feature-toggles`, `orphan-triage` — **21 passed** (30.1s).

**Not yet run:** the demo-data reproduction from the QA pass (`HLC-CPR-2026-02868`) in a real
browser; the seeded spec above reproduces that scene shape exactly and is what the fix is measured
against.

### Phase 4

Frontend only again: `bench build --app do_derma` required, no bundle filename changed, no Python,
patch or fixture touched, so no migrate and nothing for `ruff` or the Frappe runner.

**Browser (Playwright).** New `e2e/tests/annotation-procedure-drawer.spec.ts`, two specs — the
category filter keeps every sibling template in the anchor's own category, the search narrows to
one and then to none with the empty message, clearing restores the count, and the header names the
seeded patient exactly once while reading `Procedure: E2E Filler`. **2 passed** (12.7s). The
first run failed on a strict-mode violation (four `.derma-annotation-empty` nodes in the studio),
which is why the drawer's empty state carries its own `data-test` hook.

The show-all-categories branch is asserted conditionally: the dev site is a production clone, so
whether any other-category template exists is site data. When the checkbox is offered, the spec
requires it to widen the list.

**Regression:** `annotation-anchoring`, `-consultation`, `-badges`, `-discard` — **20 passed**
(5.3m); `annotation-canvas`, `-freehand`, `-resume` — **14 passed** (3.2m). Between them they
cover both header branches and every drawer selection in the suite.

### Left behind

The browser check placed a real mark on demo procedure `HLC-CPR-2026-02869`, on top of the
leftovers the QA pass recorded. `bench --site dermaone.localhost execute
do_derma.demo_seed.teardown_demo_data` then `setup_demo_data` resets them.

## Files to touch (summary)

| File | Change |
|---|---|
| `public/js/chart/annotation/DermaAnnotationStudio.jsx` | Phase 1: drop the `hasParams` gate; em dash for an empty parameter cell. Phase 2: `sessionMarks`, the counted confirm, `discardDrawing`, and the close result. Phase 4: `anchorProcedureCategory` / `visibleProcedures` / search box / show-all checkbox / empty state, and `anchorDescription` naming the patient once |
| `do_derma/api.py` | Phase 2: `discard_chart_marks` + `_is_mark_documented` |
| `public/js/chart/DermaChart.vue` | Phase 2: refresh the chart when a discard removed marks. Phase 4: pass `procedureTemplate` through the annotate entry points and the picker |
| `public/js/chart/derma_chart.bundle.css` | Phase 4: `.derma-annotation-search` |
| `e2e/tests/annotation-procedure-drawer.spec.ts` | Phase 4 *(new)*: category filter, search, empty state, header names the patient once |
| `do_derma/tests/test_api.py` | Phase 2: `TestDiscardChartMarks` *(5 cases)* |
| `e2e/tests/annotation-discard.spec.ts` | Phase 2 *(new)*: discard deletes what it placed, keeps what it did not |
| `public/js/chart/excalidraw/EmbeddedExcalidraw.jsx` | Phase 3: strict `getTemplateBounds`, `whenTemplateMeasured`, `isTemplateRenderable`, `rebuildUnrenderableTemplate`, `templateGeometry`, scene-preserving `insertTemplateImage`, visible-only `getRenderedPartCount` |
| `e2e/tests/annotation-resume.spec.ts` | Phase 3 *(new)*: a resumed drawing opens fitted with its areas; an unpaintable template is rebuilt without losing the drawing |
| `e2e/tests/annotation-badges.spec.ts` | Rewrite the "not badge-worthy" assertion to the new contract |
| `docs/superpowers/specs/2026-08-14-procedure_annotation_qa.md` | Point findings 1, 2, 4 and 5 at this spec |
