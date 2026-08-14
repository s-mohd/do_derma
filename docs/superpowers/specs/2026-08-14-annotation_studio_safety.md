# Annotation Studio Safety

Date: 2026-08-14
Status: **Implemented & verified** (2026-08-14) — see [Verification](#verification). Two findings
surfaced during implementation that the plan did not have; see
[Reconciliation](#reconciliation--what-changed-vs-the-plan).

## Goal

A browser QA pass over the consultation annotation flow (2026-08-14, demo
patient `PAT-2026-1446`, encounter `HLC-ENC-2026-03308`) found that **the studio
throws a drawing away on a stray click**, tells the practitioner nothing when a
body template fails to load, and ships Excalidraw's stock chrome — including
*Open*, which loads an arbitrary `.excalidraw` file straight over a patient's
chart. This spec closes the paths by which patient work is lost or leaves the
app. It is **frontend-only**: no endpoint, no schema, no migrate.

Its sibling, [`2026-08-14-annotation_output_fidelity.md`](2026-08-14-annotation_output_fidelity.md),
covers the findings about what gets *saved and printed*. The two share three
files and are sequenced safety-first.

## Decisions

- **The backdrop stops being a close button; one guarded exit replaces three
  unguarded ones** → a stray click outside the shell is the cheapest way to lose
  a drawing and there is no undo after the modal unmounts. Trade-off accepted:
  practitioners who close by clicking outside must now use Cancel or Escape.
  Rejected: confirming on all three paths (a dialog on every stray click trains
  people to dismiss it), and autosaving on close (writes a record nobody asked
  for and makes Cancel meaningless).
- **Dirty is measured over user-authored elements only** → `sceneRevision` is
  bumped by our own `renderChartMarks` / badge / part renders, so using it
  directly would prompt on drawings nobody touched. Trade-off: a signature has to
  be recaptured after each save.
- **Excalidraw's chrome is trimmed to the clinical set, not just the Library
  button** → *Open* can silently replace the patient's drawing and *Save to
  disk* / *Export image* write patient images outside any audit path. Trade-off:
  no ad-hoc export; do_derma's Save and the review dialog's Print become the only
  ways a drawing leaves the app. Rejected: removing only the Library button, the
  one the QA pass happened to photograph.
- **The template-load failure is reported and the selection refused, not
  repaired** → 24 of 26 `Derma Body Template.image` values on this site point at
  `/private/files/…` that 403/404. That is site data on a production clone; the
  app's job is to say so.

## Current State (verified)

- `DermaAnnotationStudio.jsx:570` — `<div className="derma-annotation-backdrop"
  onClick={onClose} />`. Verified in the browser: draw a stroke, click at (6,6),
  the modal unmounts and the stroke is gone. No confirmation anywhere.
- `DermaAnnotationStudio.jsx:614` — `Cancel` is `onClick={onClose}`, the same
  bare call. **Nothing in the file tracks dirty state**: no `dirty`, no
  `unsaved`, no `beforeunload`.
- No Escape handling exists. Verified: pressing Escape with the studio open
  leaves `.derma-annotation-modal` in the DOM. So the key users expect to be safe
  does nothing, and the click users expect to be safe destroys work.
- `DermaAnnotationStudio.jsx:308` — `sceneRevision` is a counter bumped from
  `onSceneChanged`; `:375-384` shows it is also bumped by our own badge sync, so
  it is **not** a usable dirty signal on its own.
- `EmbeddedExcalidraw.jsx:120-126` — `loadTemplateImage` ends
  `const loaded = await loadTemplateIntoCanvas(...); if (!loaded) return`. The
  failure never reaches the studio. Verified: clicking "Head - 3 Sides" highlights
  the card, leaves the previous template on canvas, and raises no message.
- `fetch('/private/files/Head.jpeg')` → **404**;
  `fetch('/private/files/Face 1.jpeg')` → **403**. All 26 rows have a non-empty
  `image`, so `groupedTemplates` (`:46-48`) and `allTemplates` (`:317`), which
  filter on `template.image`, list every one of them.
- `DermaAnnotationStudio.jsx:753-763` — `TemplateThumbnail` already has a broken
  state driven by the `<img onError>`; 13 cards were in it during the QA pass.
  Nothing connects that state to whether the card can be selected.
- `EmbeddedExcalidraw.jsx:259` — `UIOptions={{ canvasActions: { saveToActiveFile:
  false } }}`, the only chrome restriction. Excalidraw **0.17.6**
  (`node_modules/@excalidraw/excalidraw/types/types.d.ts:340-366`) also gates
  `changeViewBackgroundColor`, `clearCanvas`, `export`, `loadScene`,
  `toggleTheme`, `saveAsImage`; the Library button is displaced by
  `renderTopRightUI` (`types.d.ts:304`).
- `EmbeddedExcalidraw.jsx:1283-1291` — `fitToTemplate` calls
  `api.scrollToContent(..., { fitToViewport: true, viewportZoomFactor: 0.72 })`
  with no check that the canvas has been measured. On the first studio open after
  a cold page load the zoom pill read **NaN%** and the canvas sat off content
  behind Excalidraw's "Scroll back to content" button; `Fit` recovered it at 88%.
  It did not reproduce on four warm reopens — by then the template image was in
  the browser cache — so this is a cold-path race, which is exactly the path a
  clinic hits on the first chart of the day.
- Console during the whole pass carried **no do_derma errors**: only
  `Error connecting to socket.io: xhr poll error` (bench dev noise) and one React
  `controlled input to be uncontrolled` warning traced to Excalidraw's own
  `LockButton`.
- E2E: `annotation-consultation.spec.ts` asserts the consultation header's button
  set, and `annotation-{badges,freehand,canvas,anchoring}.spec.ts` drive the
  procedure anchor. None of them close the studio by clicking the backdrop, and
  none assert on Excalidraw's own chrome — verified before trimming it.

## Non-Goals

- **The 403/404 template images are not repaired.** No patch, no re-upload, no
  change to `File` permissions. The templates stay listed and stay unselectable
  until the clinic fixes its own data.
- No change to what gets saved, exported or printed — that is the sibling spec.
- No change to `save_derma_annotation`, `_sync_chart_marks_for_annotation`, mark
  placement, or the badge computation.
- Excalidraw is not upgraded off 0.17.6.
- Annotating after **Complete Encounter** is untested and unaddressed; the QA
  pass deliberately did not mutate encounter state.
- The male / unknown-sex template fallback is likewise untested here.

## Design

One guarded exit, one honest failure path, and a canvas that only exposes the
tools a clinician should have. All three live in the two frontend files the
studio is built from; nothing server-side moves.

### 1. One guarded exit — `annotation/DermaAnnotationStudio.jsx`

```jsx
const savedSignature = useRef("")

// Only the practitioner's own elements count. Marks, badges and area outlines are
// re-derived on every load, so including them would prompt on an untouched drawing.
function userSignature() {
  return (embeddedRef.current?.getSceneElements?.() || [])
    .filter((element) => !element.isDeleted && !element.customData?.generated_by)
    .map((element) => `${element.id}:${element.version}`)
    .join("|")
}

function requestClose() {
  if (userSignature() === savedSignature.current) return onClose?.()
  window.frappe.confirm(
    __("Discard this drawing? Unsaved changes will be lost."),
    () => onClose?.(),
  )
}
```

`savedSignature` is captured once the initial import settles and again after each
successful save (next to the existing `setAnnotationName(response.message.name)`,
`:558`). The backdrop keeps its scrim role and loses `onClick`; `Cancel` calls
`requestClose`; a `keydown` listener on the modal maps Escape to the same
function. **One function owns closing** — the state that can drift is the
signature, and it has a single writer.

`getSceneElements` is added to the `useImperativeHandle` block
(`EmbeddedExcalidraw.jsx:118-152`) beside the existing `resetView` /
`setPartsHidden` handles.

### 2. Honest template-load failure — both files

`loadTemplateImage` returns the outcome instead of swallowing it:

```jsx
loadTemplateImage: async (nextTemplate) => {
  const target = nextTemplate || chartTemplate
  if (!api || !target?.image) return false
  const loaded = await loadTemplateIntoCanvas(...)
  if (loaded) setChartTemplate(target)
  return Boolean(loaded)
},
```

The studio awaits it, and on `false` keeps the previous selection, alerts, and
remembers the failure:

```jsx
const [unavailableTemplates, setUnavailableTemplates] = useState(() => new Set())
```

A card in that set renders the existing `derma-template-thumb-missing` treatment,
gets `disabled` + `aria-disabled`, and is skipped by the selection handler. The
`onError` path in `TemplateThumbnail` feeds the same set, so a template that
fails to even thumbnail is refused before it is clicked. `bodyTemplates` itself is
never mutated — the set is separate state, so a later reload of the chart clears
it naturally.

### 3. Clinical chrome — `excalidraw/EmbeddedExcalidraw.jsx:259`

```jsx
UIOptions={{
  canvasActions: {
    changeViewBackgroundColor: false,
    clearCanvas: false,
    export: false,
    loadScene: false,
    saveAsImage: false,
    saveToActiveFile: false,
    toggleTheme: false,
  },
}}
renderTopRightUI={() => null}
```

Shape tools, zoom, undo/redo and the properties island are untouched — everything
the practitioner draws with stays. What goes is every route by which a drawing
enters or leaves the app outside do_derma's own Save and Print.

### 4. Cold-open fit — `excalidraw/EmbeddedExcalidraw.jsx`

```jsx
function fitToTemplate(api, attempt = 0) {
  if (!api) return
  const { width, zoom } = api.getAppState()
  if ((!width || !Number.isFinite(zoom?.value)) && attempt < FIT_RETRY_LIMIT) {
    requestAnimationFrame(() => fitToTemplate(api, attempt + 1))
    return
  }
  ...existing scrollToContent...
}
```

Bounded by `FIT_RETRY_LIMIT` (3) — a frame-chained retry, never a loop. Callers
(`resetView`, the import path, `loadSceneIntoApi`) are unchanged.

What stays unchanged: `save_derma_annotation` and every other endpoint, mark
placement and the fan-out, badge computation, the template sex filter, and both
bundle filenames — so the `frappe.require` contract holds.

## Security

No new endpoint and no change to an existing one, so `_ensure_clinical_access`
coverage is unaffected. The chrome trim is itself a small security improvement:
`loadScene` let any local file be dropped onto a patient's canvas, and
`saveAsImage` / `export` wrote patient imagery to disk outside any audit path.
The confirm dialog renders a static translated string — no user content is
interpolated into it.

## Acceptance Criteria

- Clicking the backdrop with unsaved work leaves the studio open and the drawing
  intact.
- `Cancel` and `Escape` on a **dirty** canvas both ask before discarding; both
  close immediately on a **clean** one, including immediately after a save.
- Reopening a saved drawing and closing it without touching anything does not
  prompt.
- Selecting a template whose image 403/404s shows an error, leaves the previous
  template on the canvas, and marks that card unavailable and unselectable.
- A template that loads normally still selects, renders and can be saved — no
  regression to the working path.
- The studio exposes no Library button and no Open / Save to disk / Export image
  / Reset canvas / theme entries; drawing tools, zoom and undo/redo still work.
- First open after a cold page load lands on the template at a finite zoom, with
  no "Scroll back to content".
- The five existing annotation e2e specs stay green.

## Phases

1. **Close guard.** `getSceneElements` handle, signature, `requestClose`, backdrop
   `onClick` removed, Escape wired. *Exit:* a drawing survives a backdrop click,
   and Cancel on a dirty canvas asks first — both asserted in e2e.
2. **Template-failure reporting.** Propagate the load result, alert, disable the
   card. *Exit:* selecting a 403 template reports it and changes nothing.
3. **Chrome trim + fit retry.** *Exit:* no Library/Open/Export in the popup; the
   cold first open lands on the template.

## Open Questions

- Should the confirm text offer "Save instead" as a third button? *Default:* no —
  two buttons, discard or stay; Save is one click away behind the practitioner.
- Should the unavailable-template set persist across studio opens within a
  session? *Default:* no — it is per-mount state, so a fixed file recovers on the
  next open without a reload.

## Reconciliation — what changed vs the plan

- **Frappe dialogs opened invisibly behind the studio.** The studio is `z-index: 2000`; Frappe's
  modals are 1050 and their backdrop 1040. The first working discard confirm was in the DOM and
  unreachable on screen. This was never noticed because *nothing* used to raise a dialog over
  the studio — the pre-existing save-error `msgprint` had the same defect. Fixed with a
  `body.derma-annotation-open` class added while the studio is mounted, scoping the lift so the
  rest of the desk is untouched.
- **`UIOptions` does not cover the Library button in 0.17.6, and `renderTopRightUI` does not
  displace it** — contrary to the plan's reading of `types.d.ts:304`. Verified in the browser:
  with both applied the trigger was still there. The `canvasActions` half worked exactly as
  planned (the menu came down to Help/GitHub/Discord/Twitter). The Library trigger and the
  menu's social links are hidden by two scoped CSS rules instead; there is no prop for either.
- **The plan claimed no e2e spec asserted on Excalidraw's chrome. That was wrong.**
  `annotation-canvas.spec.ts:71` asserted the Library trigger *is* visible — it was deliberately
  restored by `2026-08-10-annotation_studio_parity.md`. Today's decision supersedes that one; the
  test now asserts the opposite and carries a comment naming both specs so the reversal is not
  mistaken for a regression later.
- **The canvas menu's contents are checked manually, not in e2e.** The popup does not open
  reliably under Playwright (three selector strategies failed). The Library assertion — the
  direct regression guard — stays automated.
- **The dirty signature needed a wider exclusion than "no `generated_by`".** Badges, area
  outlines and the template image element all lack that marker, so the first build prompted on
  every close, including one where nothing had been touched. `DERIVED_KINDS` now excludes all
  three by `customData.kind`.
- **The baseline is taken from an explicit `onSceneReady` callback**, not from the first
  `sceneRevision` bump as sketched. `sceneRevision` is bumped *by the user's first stroke*, so
  the sketched version would have folded that stroke into the baseline and never prompted.

## Verification

- **Integration**: `bench --site dermaone.localhost run-tests --app do_derma` — **84 tests OK**.
- **E2E**: `npx playwright test` — **50 passed (7.2m)**, including four new consultation specs
  (clean close without a prompt, backdrop-keeps-the-drawing + discard confirm, areas render and
  toggle, new-drawing-per-click) and the rewritten `annotation-canvas` chrome assertion.
- **Build**: `bench build --app do_derma` clean; no bundle renamed.
- **Lint**: `pipx run ruff check` clean on every file touched here. The 5 repo-wide findings are
  pre-existing (`api.py:1316`, four seed patches) and outside the edited regions.
- **Manual (browser, 2026-08-14)**, demo patient `PAT-2026-1448`:
  - Backdrop click with an unsaved stroke left the studio open and the stroke intact.
  - `Cancel` on that stroke raised "Discard this drawing? Unsaved changes will be lost." above
    the canvas; `No` kept the drawing. `Cancel` on an untouched studio closed with no prompt.
  - All 13 templates whose `/private/files/…` image 403/404s render struck through, faded and
    `disabled`; clicking one does nothing and the canvas keeps the working template.
  - No Library button. The canvas menu holds Help only — `Open`, `Save to disk`,
    `Export image`, `Reset the canvas` and the theme switch are all gone, as are the social links.
  - Studio opened at a finite zoom (88%) on the template every time, with no
    "Scroll back to content".

### Not yet run

- Annotating after **Complete Encounter** — out of scope, would have mutated demo encounter state.
- Male / unknown-sex template fallback.

## Files to touch (summary)

| File | Change |
|---|---|
| `do_derma/public/js/chart/annotation/DermaAnnotationStudio.jsx` | `requestClose` + signature, Escape, backdrop `onClick` removed, unavailable-template state |
| `do_derma/public/js/chart/excalidraw/EmbeddedExcalidraw.jsx` | `getSceneElements` handle, `loadTemplateImage` returns outcome, `UIOptions` trim + `renderTopRightUI`, `fitToTemplate` retry |
| `do_derma/public/js/chart/derma_chart.bundle.css` | unavailable-template card state, Frappe-dialog lift, Library/social hiding |
| `e2e/tests/annotation-consultation.spec.ts` | close guard assertions |
| `e2e/tests/annotation-canvas.spec.ts` | chrome assertion reversed (was "restores … library") |
