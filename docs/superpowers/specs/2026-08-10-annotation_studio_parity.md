# Annotation Studio Parity — Uncage The Canvas, Semantic Strokes, Lean Storage, Form Entry

Date: 2026-08-10
Status: **Implemented & verified** (2026-08-10) — all six phases shipped. Implementation
deviated from the plan in five places; see [Reconciliation](#reconciliation--what-changed-vs-the-plan)
and [Verification](#verification).

## Goal

A practitioner opens the drawing surface and it behaves like a drawing tool: pinch to zoom, drag
to pan, undo, right-click, insert a photo, open the shape library. Picking a procedure colours
the pen, and the stroke they draw over the affected skin becomes a real clinical mark. Numbered
badges appear as they work rather than only in the saved image. And from a Patient Encounter or
Clinical Procedure they can see, at a glance, that drawings exist at all.

The request, verbatim:

> "I really liked the annotation in annotation app, can you compare the current one with
> annotation app."

Why it was hard: **nothing was wrong with the engine.** do_derma and the `annotation` app
(`~/Developer/develop/apps/annotation`) both run Excalidraw 0.17.6. The difference was that the
annotation app disables exactly one thing (`saveToActiveFile`) while do_derma caged the canvas
from two directions at once — in JSX *and* in CSS — and the CSS half is invisible to anyone
reading the component.

## Decisions

- **A semantic freehand stroke creates a `Derma Chart Mark`** at its centroid, through the same
  `save_chart_mark` path stamps use → `Derma Chart Mark` is the sole input to
  `_build_inventory_readiness`, `get_followup_intelligence`, `create_procedure_from_mark`,
  `build_mark_narrative`, `carry_forward_marks` and the Procedures-tab counts. A stroke carrying
  clinical variables only in `customData` would be a second, invisible representation of "a
  treatment applied at a location". Trade-off accepted: a region is reduced to a point, which is
  the compromise dragged areas already make — `x_percent`/`y_percent` are `reqd`. The full
  geometry stays in the scene. Rejected: drawing-only metadata, because it would have required
  reviving the dead element-tagged branch of `_sync_chart_marks_for_annotation`.

- **Badges live in the scene, not in the export call** → one computation feeds the canvas, the
  PNG and the `annotation_data` legend, which previously came from three separate snapshots and
  could disagree. Locked, `kind: "derma_badge"`, `commitToHistory: false`, stripped from what is
  persisted. Rejected: keeping `extraElements`, which would double-draw every badge once they
  were also on canvas.

- **The viewport lock is replaced by a `Fit` button, not by a smarter lock** → verified, not
  assumed: mark geometry is scene-space throughout (`getTemplateBounds` reads the template
  element's own `x/y/width/height`), so zoom and pan cannot move a stored percentage. The lock
  was pure UX. Trade-off accepted: a practitioner can now pan the template out of view, so there
  is an explicit way back.

- **The storage strip keys on `customData.kind === "derma_template"`, never on "is an image"** →
  the annotation app strips `dataURL` from every image element, which permanently destroys any
  photo the practitioner inserted. That is a live concern here because the image tool is now
  enabled. Trade-off accepted: an inserted photo is still stored base64 and unbounded.

- **No backfill of the 5,437 existing annotations** → the user's call. They keep working through
  the legacy read branch, which uses the `files` map when one is present.

## Current State (verified 2026-08-09/10, before the work)

### The cage was in two places, and only one is visible from the component

`EmbeddedExcalidraw.jsx`: `enforceLockedViewport` snapped `scrollX`/`scrollY`/`zoom` back on any
drift beyond 2px or 0.01 and clamped zoom to 0.18–1.8, called from three sites including an
`onScrollChange` prop; capture-phase listeners swallowed `wheel`, `contextmenu`, middle-click and
the keys `space + - = 0` and all four arrows; `UIOptions` disabled the image tool, the library,
export, theme, background colour and clear-canvas; `cleanupExcalidrawControls` hid further
controls through a `MutationObserver`.

`derma_chart.bundle.css`: `touch-action: none` killed trackpad pinch and two-finger pan at the
browser level — deleting the JSX alone would have changed nothing on a laptop — plus a
28-selector `display: none !important` block hiding the hand tool, the frame tool, help, both
footer rails, the top-left menu, every Library affordance, **every zoom button**,
scroll-back-to-content and the lock button; and `.layer-ui__wrapper__footer { pointer-events:
none }` with undo/redo re-enabled by exception.

### Storage

Measured on `dermaone.localhost`: **5,437 `Health Annotation` rows, 193 MB of JSON, 35.6 KB
average, 481 KB worst case, 5,431 containing a `dataURL`.** `exportScene` persisted
`{elements, files, derma_template}` with `files` carrying the base64 body template.

**The read path for stripped scenes already existed**: `hydrateTemplateImageFiles` re-fetches
from `element.customData.template.image` or `scene.derma_template.image`. Only the write path
needed changing.

### Badges

`collectBadgeItems` / `badgeElements` / `generateAnnotationDataHTML` were near-identical ports of
the annotation app's. They ran only at save time, and `badgeElements` output was passed as
`extraElements` to `exportScene`, so badges existed solely inside the exported PNG.

### What do_derma was already ahead on

Clickable anatomy zones with per-zone variables (`Derma Body Template Part` is a superset of
`Annotation Template Part` — it adds `disabled` and Float/Int/Date/Check variable types), an
admin zone-authoring page, history thumbnails with a preview dialog, correct in-place resume (the
annotation app never rebinds `annotation_name`, so every save there forks a new record),
`_ensure_clinical_access()` on every endpoint where the annotation app has **no permission checks
at all**, and a test suite where it has none.

## Non-Goals

- No backfill of existing annotations, and no port of the annotation app's migration patch.
- `2026-08-09-derma_chart_revamp.md` Phases 4 (orphan triage) and 5 (feature toggles) stay open.
- The dead element-tagged branch of `_sync_chart_marks_for_annotation` stays dead.
- No change to `_ensure_clinical_access` as the authorization boundary or to the DocPerm matrix.
- Not fixing the `Patient Encounter` refresh handler that throws (owned by another app).
- Not bounding the size of practitioner-inserted photos.

## Design

### 1. Mark rendering owns only what it drew — `EmbeddedExcalidraw.jsx`

`renderChartMarks` claimed every element tagged `kind: "derma_mark"` with a `mark_name`, dropped
it and rebuilt it from the mark's centroid. Now it stamps `generated_by: "render_chart_marks"` on
its own output and reclaims only that, and skips marks already represented on canvas:

```js
const existing = api.getSceneElements().filter((el) => el.customData?.generated_by !== GENERATED_BY_MARKS)
const alreadyDrawn = new Set(existing.map((el) => el.customData?.mark_name).filter(Boolean))
```

### 2. Uncaging — `EmbeddedExcalidraw.jsx` + `derma_chart.bundle.css`

Both halves of the cage deleted. `UIOptions` reduced to `{ canvasActions: { saveToActiveFile:
false } }`. `handleKeyboardGlobally={false}` **stays** — it stops Excalidraw binding
document-level keydown and stealing keys from the desk form behind the overlay.
`resetChartView(api, ref)` becomes `fitToTemplate(api)`: same fit, no captured viewport, no 80 ms
timeout that could fire after a scene import. It runs on template insert, on scene import and on
the `Fit` button — **not** on resize, which would make it a viewport thief.

### 3. Lean storage — `exportScene`

```js
function stripTemplateImagePayload(elements, files) {
  const templateFileIds = new Set(
    elements.filter((el) => el.customData?.kind === "derma_template" && el.fileId).map((el) => el.fileId)
  )
  return {
    elements: elements
      .filter((el) => el.customData?.kind !== BADGE_KIND)
      .map((el) => (templateFileIds.has(el.fileId) ? { ...el, dataURL: undefined } : el)),
    files: Object.fromEntries(Object.entries(files).filter(([id]) => !templateFileIds.has(id))),
  }
}
```

**The riskiest line in the feature: strip the template's payload, never the template element.**
`_sync_chart_marks_for_annotation` (`api.py:1806`) returns early when no element carries
`kind in ("derma_template", "derma_template_image")`, so dropping the element — which is what the
annotation app's migration patch does — would silently stop every mark in the session being
linked to its annotation, with no error anywhere. Covered by
`test_marks_still_backlink_when_the_scene_carries_no_image_payload`, named for the failure rather
than the happy path.

### 4. Live badges

The studio owns badge policy (it has `partValues`, `selectedParts`, `procedures`); the canvas
owns the scene. `collectBadgeItems` is recomputed in a `useMemo` keyed on a `sceneRevision`
counter and pushed down via `setBadgeElements`. Two guards, because a scene update re-fires
`onChange`:

- `markLayerSignature(elements)` — badges derive from the mark layer alone, so only a change to
  mark ids, positions or variables signals the studio. Without this the studio deadlocks with
  *Maximum update depth exceeded*: Excalidraw fires `onChange` on every appState tick.
- `syncBadgeLayer`'s own signature over badge ids and positions, with deterministic badge ids
  (`derma-badge-<n>`) so an unchanged layer produces an unchanged signature.

### 5. Semantic freehand

`placementToolFor(template)` routes `area`/`hatch`/`five_lines` → drag rectangle,
`freehand`/`stroke`/`paint` → pen, everything else → point stamp. `setDermaTool` already mapped
`draw → freedraw` and already coloured the pen from `custom_derma_marker_color`, so this is one
branch, not a feature. Area and freehand share `findCommittedElement` / `tagDrawnElement` /
`buildDrawnPlacementPayload`; only the centroid differs. A stroke under 6 px in both dimensions is
a flick of the pen and is ignored.

Clicking a mark reopens its variables. **The mark is the owner and the element is the cache** —
every edit writes `save_chart_mark` first, then `updateMarkVariables`. Selection is read from
Excalidraw's own `appState.selectedElementIds`, and only while no placement tool is armed, so the
selection made on a freshly placed stamp is not read as "edit this one".

### 6. Form entry point

`get_derma_annotation_summary(doctype, docname)` calls `_ensure_clinical_access()` first, rejects
any doctype outside `("Patient Encounter", "Clinical Procedure")`, and reuses
`_load_annotations_for_parents(..., include_scene=False)`.

### What stays unchanged

The React-overlay mounting model, both `*.bundle.js` filenames (so the `frappe.require` contract
is untouched), `DermaChart.vue`'s tab spine, every doctype except the two Select option lists,
and every existing endpoint's signature.

## Security

- **Authorization.** `get_derma_annotation_summary` calls `_ensure_clinical_access()` as its
  first statement. It reads patient drawings and is reachable from any desk form, which makes it
  the easiest endpoint here to call unnoticed. Proven by
  `TestClinicalAccessGate.test_annotation_summary_is_gated`.
- **Input validation.** The endpoint rejects any parent doctype outside the two that can hold
  annotations, rather than trusting the caller's `doctype` string.
- **XSS.** `annotations_button.js` escapes every interpolated value through
  `frappe.utils.escape_html` and binds handlers on the rendered wrapper. The annotation app
  interpolates the template label and image URL directly into an `onclick` attribute; that was
  not copied. `annotation_data` is rendered as HTML because this app generates it itself.
- **No new write path.** The summary endpoint is read-only.

## Acceptance Criteria

1. Pinch-zoom, two-finger pan, right-click, `0`/`+`/`-` all work; the zoom control, hand tool,
   image tool and library are present. ✅
2. Zoom does not move a stored mark percentage: a centre click lands on the template centre at
   fit and while zoomed in. ✅
3. `Fit` returns the template to view after panning away. ✅
4. A newly saved annotation contains no `dataURL`, still contains its template element, and
   reopens showing the body template. ✅
5. Marks still backlink to their annotation when the scene carries no image payload. ✅
6. A badge appears as soon as a mark carries a filled variable, renumbers as marks are added,
   cannot be selected, and never reaches the persisted JSON. ✅
7. Unticking `Badges` removes them from canvas and export together. ✅
8. The badge layer settles instead of looping. ✅
9. A freehand procedure colours the pen and one stroke becomes exactly one `Derma Chart Mark`
   carrying `annotation_json.shape = "freehand"`. ✅
10. The stroke keeps its own geometry across save and resume. ✅
11. Clicking a mark reopens its variables, bound to that mark. ✅
12. Re-saving a drawing neither duplicates nor deletes its marks. ✅
13. A mark promoted to a Clinical Procedure still survives a re-save. ✅
14. Both doctypes show `Annotations (N)`, listing drawings with a preview and a route into the
    chart. ✅
15. A user without a clinical role cannot call the summary endpoint. ✅
16. A dragged treatment area keeps its drawn size across resume. ✅
17. A new visit opens as a new drawing even when the patient has earlier ones. ✅

## Phases

**Phase 1 — Mark-rendering regression.** ✅ `renderChartMarks` owns only its own output.
*Exit: a dragged area keeps its size across resume.* Met; the spec fails on the previous build
with `Received: 80` — the `createAreaMark` box.

**Phase 2 — Uncage.** ✅ JSX and CSS cages deleted, `Fit` button added, `hydrateTemplateImageFiles`
guarded.
*Exit: zoom/pan/library/image tool available, percentages unaffected.* Met.

**Phase 3 — Lean storage.** ✅ New saves strip the template payload.
*Exit: no `dataURL` persisted, template element retained, scene reopens.* Met — a real save
measured **3,684 bytes** against the 35,652-byte legacy average.

**Phase 4 — Live badges.** ✅ Badges in the scene, one generator.
*Exit: badges visible and numbered while working, absent from the saved JSON.* Met.

**Phase 5 — Semantic freehand.** ✅ Strokes become marks; marks are re-editable.
*Exit: one stroke, one mark, geometry preserved, variables re-editable.* Met.

**Phase 6 — Form entry point.** ✅ `Annotations (N)` on both doctypes.
*Exit: drawings reachable from the document that holds them.* Met.

## Reconciliation — what changed vs the plan

- **The badge generator did not move into `EmbeddedExcalidraw.jsx`.** The plan had it move so
  there would be "one place badges exist". Moving it would have dragged `getContrastText` and the
  colour helpers across too, and `collectBadgeItems` genuinely needs the studio's `partValues`
  and `procedures`. As built, the studio owns badge *policy and geometry* and the canvas owns
  *hosting* — still one generator, with a smaller diff and no duplicated helpers.

- **The loop guard is on the mark layer, not a 250 ms debounce.** The plan proposed debouncing
  `onSceneChanged`. That is not sufficient: Excalidraw fires `onChange` on every appState tick,
  so any `setState` there re-renders the host, re-renders Excalidraw and fires again — debouncing
  only slows the loop down. The first build deadlocked with *Maximum update depth exceeded*.
  Watching `markLayerSignature` kills it at the source, because badges derive from the mark layer
  and badge elements are not marks.

- **`collectBadgeItems` needed deduplication that the plan did not anticipate.** A numbered-dot
  stamp is several elements sharing a group, and every one of them was being counted, so one mark
  drew two badges. Pre-existing, invisible while badges only lived inside the export. They are
  now keyed by mark identity.

- **`Health Annotation Table.annotation_data` did not exist on this site**, so the badge legend
  could never round-trip. Its patch is recorded as applied in `Patch Log` — precisely the drift
  the `after_migrate` schema spine was built for — so it was added to `DERMA_CUSTOM_FIELDS`
  rather than as a fourteenth patch.

- **Two schema fixes the plan did not foresee.** `Derma Chart Mark` and `Derma Procedure
  Category` offered eight marker behaviours where `Clinical Procedure Template` offers eleven, so
  a mark from a template configured as `three_dots`, `triangle_cluster` or `five_lines` was
  rejected on save. Both lists now match, plus `freehand`. The template's Select gains the option
  through a patch, because the schema spine creates missing fields but never rewrites an existing
  one.

- **The fan-out's deletion loop had to change, and this was the sharpest moment in the work.**
  Giving drawn marks an `annotation_json.element_id` — the idempotency key the plan asked for —
  exposed them to a loop that spares only `tagged` elements, and `tagged` is always empty in
  practice. Saving the same drawing twice deleted the mark. A mark is now orphaned only once its
  element has actually left the scene. Caught by `test_resave_does_not_duplicate_a_drawn_mark`,
  written before the change.

- **The `Annotations (N)` button needed a router fallback.** Frappe runs every app's `refresh`
  handlers as one sequence, and on this site a `Patient Encounter` handler throws *Cannot read
  properties of undefined (reading 'fieldname')* partway through, silently skipping every handler
  registered after it — eight other apps' buttons land before the throw, ours did not. The defect
  belongs to another app. The button is registered on `refresh` and `onload_post_render`, with a
  bounded router-driven retry behind them.

Not deviations, worth recording: a **cross-visit resume bug shipped in `79276fa`** was found while
testing Phase 2 and fixed there — `encounter_annotations` falls back to the patient's earlier
encounters when the current one has none, so a new visit opened *"Editing the saved drawing"* and
its first save would have overwritten the previous visit's. Resume now matches on `source_name`.
Badge placement sits just below its mark rather than above; cosmetic, geometry unchanged from the
original port.

## Verification

### Run 2026-08-10, all green

| Command | Result |
|---|---|
| `run-tests --module do_derma.tests.test_api` | **19 passed** (12 pre-existing + 7 new) |
| `run-tests --module do_derma.tests.test_schema` | **4 passed** — no regression |
| `run-tests --module do_derma.tests.test_assessment` | **14 passed** — no regression |
| `bench --site dermaone.localhost migrate` | Clean, run repeatedly; `after_migrate` idempotent |
| `bench --site dermaone.localhost execute do_derma.e2e_seed.setup_e2e_data` | Clean, `skipped: []` |
| `bench build --app do_derma` | Clean |
| `npx playwright test` | **38 passed** (18 pre-existing + 20 new) |
| `ruff check apps/do_derma` | 5 findings, **all pre-existing** — see note |

Ruff note, unchanged from the revamp spec: `pipx run ruff` is newer than the project pins and
reports one `RUF005` in `api.py` plus four import-sort findings in patches this work does not
touch. Every file changed here is clean.

New backend tests:

| Test | Asserts |
|---|---|
| `test_marks_still_backlink_when_the_scene_carries_no_image_payload` | The strip cannot silently break the mark backlink |
| `test_stored_scene_keeps_the_template_element` | Payload stripped, element retained, no `dataURL` |
| `test_resave_does_not_duplicate_a_drawn_mark` | The fan-out neither duplicates nor deletes a drawn mark |
| `test_annotation_summary_is_gated` | The new endpoint refuses a user without a clinical role |
| `test_lists_an_encounter_annotation_without_the_scene` | Summary omits `json` |
| `test_returns_empty_for_an_unknown_document` | Missing document degrades to `[]` |
| `test_rejects_a_doctype_that_cannot_hold_annotations` | Parent doctype is validated, not trusted |

New e2e specs: `annotation-canvas.spec.ts` (8), `annotation-badges.spec.ts` (6),
`annotation-freehand.spec.ts` (5), `annotation-toolbar-button.spec.ts` (4), plus the dragged-area
assertion added to `annotation-anchoring.spec.ts`.

Manual, against seeded data on `dermaone.localhost`: the studio was driven through draw → save →
reopen → re-save in Chromium for both anchors and for the freehand procedure. Screenshots confirm
the full stock toolbar with zoom controls and Library, the teal pen matching the procedure colour,
and badges 1–3 numbered top-to-bottom on canvas with the header reading `Badges (3)`.

**Not yet run:** no backfill of the 5,437 legacy annotations, by decision. Print formats still do
not render SOAP notes (carried over from the revamp spec's Open Questions).

## Open Questions

- **Practitioner-inserted photos are unbounded.** Now that the image tool is enabled, a 2 MB
  photo is stored base64 in the scene and survives the strip. *Default:* accept it — the template
  strip removes ~90% of the average row, and downscaling clinical photos is a decision for the
  clinic, not the app.

- **The `Patient Encounter` refresh chain throws on this site.** Any app registering a handler
  after the broken one is silently skipped. *Default:* work around it here; report it separately.
  It is worth finding, because it will be breaking other apps' buttons too.

- **Badges render below their mark, not above.** *Default:* leave it; the geometry is unchanged
  from the original port and the numbering is correct.

## Phase 2 (future, not in this spec)

- Backfill the 5,437 legacy annotations, if the storage saving is wanted retroactively.
- Reviving the dead element-tagged branch of `_sync_chart_marks_for_annotation`.
- Revamp Phases 4 (orphan triage) and 5 (feature toggles).
- ~~Print formats keyed off the stamped assessment mode.~~ ✅ *Shipped 2026-08-10* — see
  `2026-08-10-assessment_print_formats.md`.

## Files to touch (summary)

| File | Change |
|---|---|
| `chart/excalidraw/EmbeddedExcalidraw.jsx` | Mark-ownership fix, uncage, `fitToTemplate`, storage strip, badge layer, freehand routing, selection reporting |
| `chart/derma_chart.bundle.css` | Delete `touch-action`, the 28-selector hide block, the footer `pointer-events` block |
| `chart/annotation/DermaAnnotationStudio.jsx` | `Fit`, live badge memo, badge dedupe, freehand hints, mark re-edit |
| `chart/DermaChart.vue` | Resume matches on `source_name` |
| `do_derma/api.py` | `get_derma_annotation_summary`; `include_scene`; deletion loop spares live elements |
| `do_derma/schema.py` | `Health Annotation Table.annotation_data` |
| `do_derma/hooks.py` | Second `app_include_js`, first `app_include_css`, first `doctype_js` |
| `do_derma/patches/add_derma_freehand_marker_behavior.py` | *(new)* |
| `doctype/derma_chart_mark`, `doctype/derma_procedure_category` | Marker behaviour options aligned + `freehand` |
| `public/js/annotations_button.js` | *(new)* Toolbar button, dialogs, router fallback |
| `public/js/doctype/{patient_encounter,clinical_procedure}.js` | *(new)* Form shims |
| `public/css/annotations_button.css` | *(new)* Dialog styles |
| `do_derma/e2e_seed.py` | Freehand procedure template fixture |
| `do_derma/tests/test_api.py` | 7 new tests |
| `e2e/tests/annotation-{canvas,badges,freehand,toolbar-button}.spec.ts` | *(new)* |
