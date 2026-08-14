# Annotation Output Fidelity

Date: 2026-08-14
Status: **Implemented & verified** (2026-08-14) — see [Verification](#verification). Three of this
spec's premises were wrong and the fix needed a patch and a seeder repair it did not plan for; see
[Reconciliation](#reconciliation--what-changed-vs-the-plan).

## Goal

The same browser QA pass that produced
[`2026-08-14-annotation_studio_safety.md`](2026-08-14-annotation_studio_safety.md)
found four ways the annotation record disagrees with what the practitioner
actually did: **area outlines never come back when a saved drawing is reopened**,
every mark **prints its number twice** from two numbering systems that can
disagree, every clinician-facing surface identifies a drawing by its **docname
hash** (`26ns0a25df`) with no patient on the printed sheet at all, and a
consultation can hold **only one drawing per encounter**, forever, with the button
silently reopening it.

This spec is about what gets stored, shown and printed. Its sibling covers the
paths that lose or leak the drawing, and ships first. One backend change: a field
added to an existing read. No new endpoint, no schema, no migrate.

## Decisions

- **The badge layer becomes the single owner of a mark's visible number** →
  today `createNumberedDot` draws the mark's server-side `sequence` while
  `collectBadgeItems` independently numbers tagged elements `1..n`, and it is the
  *badge* numbering the legend table and printout reference. Two owners of one
  fact is how they drift. Trade-off accepted: with Badges unticked in a procedure
  popup, dot marks show no number — already true of every other stamp behaviour
  (X, target, hatch, area, triangle, dot cluster), none of which draw one.
  Rejected: having the badge layer skip already-numbered stamps, which removes the
  duplicate but leaves both numbering sources alive and still able to disagree.
- **Area outlines are derived state: stripped on persist, re-rendered from the
  template on load** → same rationale as the template image payload strip. A
  drawing that stored its outlines would keep the geometry it was drawn against,
  so editing a template's areas would leave old and new mixed on the next resave.
  Trade-off: one more re-render on the resume path.
- **The export honours `Hide Areas`** → it already does, for free:
  `styleTemplateParts` sets `opacity: 0` when hidden, and `exportToBlob` renders
  the live scene. What the practitioner sees is what prints, with no invisible
  policy.
- **The consultation anchor gets the same two paths the procedure anchor has** →
  a face map and a leg map in one visit is ordinary clinical work and is
  currently impossible. Rejected: one-drawing-per-encounter with a relabelled
  button, and one-per-body-template, which invents a resolution rule the
  procedure side does not have.
- **The printed sheet carries full identity — patient, MRN, template, date,
  practitioner, encounter** → it is a clinical document that ends up in a paper
  file; the extra two fields make it traceable back to the visit.

## Current State (verified)

- `EmbeddedExcalidraw.jsx:189-199` — `renderTemplateParts` is called **only**
  inside the `chartTemplate.image` effect. The resume path (`:154-172`) calls
  `adoptSceneTemplate`, `renderChartMarks` and `styleTemplateParts`, but never
  `renderTemplateParts`, so it styles parts that were never created.
- Verified in the browser: `DEMO Face Map` has **4** `Derma Body Template Part`
  rows (`odokjpcita`, `odoq0l0oem`, `odo0v2103l`, `odo5gmutqr`), and a resumed
  drawing showed **zero** outlines. Re-picking the same template from the drawer
  brought them back — that path runs the image effect.
- `DermaAnnotationStudio.jsx:597-607` — the `Hide Areas` button is gated on
  `selectedParts.length`, i.e. rows fetched from the server, not outlines on the
  canvas. Verified: it was offered on a resumed drawing with no outlines, and
  toggling it flipped the label between `Hide Areas` / `Show Areas` while nothing
  on the canvas changed. It also disappears entirely when the selected template
  fails to load, so the header shifts.
- `styleTemplateParts` (`EmbeddedExcalidraw.jsx:715-736`) sets
  `opacity: state.hidden ? 0 : 100` — so once outlines exist, the toggle already
  governs the exported PNG.
- `stripTemplateImagePayload` (`:1269-1281`) is the only persist-time filter: it
  drops `BADGE_KIND` elements and the template's base64 payload. **Part elements
  are not stripped**, so once rendered they would be written into the saved JSON.
- `createNumberedDot` (`:835-839`) returns `[ellipse, textElement(String(sequence))]`
  — the mark's own number. `collectBadgeItems` /`badgeElements`
  (`DermaAnnotationStudio.jsx:106, 375-384`) add a second numbered pill, and
  `generateAnnotationDataHTML(badgeItems)` (`:551`) is what fills the legend
  table. Verified in the saved output image: pills read `1, 1, 2, 2` beside a
  legend listing `1` and `2`.
- `includeBadges` defaults `true` (`DermaAnnotationStudio.jsx:304`) and the
  checkbox is rendered only for a procedure anchor (`:608-613`), so a consultation
  can never turn the duplicate off.
- `DermaChart.vue:1646-1648` — `annotationTemplateLabel` returns
  `annotation_template || title || name`. These rows have no `annotation_template`
  (it is a Link to the separate `annotation` app's doctype, deliberately left
  blank — `api.py:1986-1990`), so every surface falls through to `name`.
- **The human label already exists server-side.** `_save_health_annotation` is
  passed `body_template_title` and stores it on the do_derma-owned
  `custom_derma_body_template_title` (`api.py:1989-1997`). But
  `_load_annotations_for_parents` selects only
  `["name", "annotation_template", "image", "json", "creation", "modified"]`
  (`api.py:1064`), so the label never reaches the client.
- `printAnnotationReview` (`DermaChart.vue:1621-1640`) writes a hand-built
  document whose `<title>` and `<h2>` are both `annotationTemplateLabel(...)`.
  Verified printout: heading `26ns0a25df`, and **no patient name, MRN, date or
  practitioner anywhere on the page**. The window is hand-written HTML with no
  autoescaping; `escapeHtml` is applied to the title and image URL today.
- `DermaChart.vue:775` — `currentPractitionerName` is already computed from
  `encounter.practitioner_name || appointment.practitioner_name || sessionProvider`.
  Patient name, MRN and encounter name are likewise in Vue state.
- `DermaChart.vue:1655-1682` — `openAnnotationStudio()` passes
  `annotation: anchor.annotation !== undefined ? … : latestAnnotationForAnchor(clinicalProcedure)`,
  and the consultation button (`:121`) calls it with no argument, so the fresh
  path is unreachable there. The procedure anchor uses `annotation: null` at
  `:1715` and `:1730` and the picker at `:1763`.
- `latestAnnotationForAnchor` (`:1684-1691`) carries a load-bearing docstring:
  `encounter_annotations` falls back to the patient's **previous visits** when
  this encounter has none, and resuming one of those would overwrite an earlier
  visit's drawing on save. Its `row.source_name === encounter.value.name` filter
  is the guard.
- `DermaChart.vue:115-141` — the strip is titled **Previous Annotations** while
  holding the drawing being edited right now. Its cards read
  `annotationTemplateLabel` over `formatDate(creation)`; the date renders
  truncated (`14-08-202…`) because `.chart-annotation-list` gives each card
  `minmax(150px, 1fr)` against a 58px thumbnail
  (`derma_chart.bundle.css:423-463`).
- Marks are **not** duplicated by a save: after the QA save, the encounter still
  had exactly its two `Derma Chart Mark` rows, both still pointing at
  `26ns0a25df`. The fan-out's idempotency is intact and stays untouched.

## Non-Goals

- `_sync_chart_marks_for_annotation` and its four properties are untouched — no
  change to element-id keyed upserts, promoted-mark protection, real-time stamp
  re-linking, or the template-element requirement.
- `save_derma_annotation`'s saved-row response, mark placement, stamp geometry
  other than the number, the sex filter, and the badge *computation* all stay as
  they are.
- No new doctype. **Wrong as written**: this said "no new custom field, no patch, no fixture —
  the label field already exists and is already written". The write path existed; the field did
  not. A patch creates it and a migrate is required — see
  [Reconciliation](#reconciliation--what-changed-vs-the-plan).
- The `/private/files/…` template images stay broken; that is site data.
- Annotating after **Complete Encounter** and the male / unknown-sex template
  fallback are untested in the QA pass and out of scope.
- The desk-form `annotations_button.js` viewer is not touched.

## Design

Four independent corrections. The riskiest is **§4**: it edits the resume path
guarded by `latestAnnotationForAnchor`'s docstring, and getting it wrong
overwrites a previous visit's drawing.

### 1. Areas on resume, and never in the file — `excalidraw/EmbeddedExcalidraw.jsx`

The resume path gains the render call it is missing:

```jsx
loadSceneIntoApi(api, scene, false).then(() => {
  latestImported.current = initialAnnotation.name
  pendingSceneImport.current = ""
  adoptSceneTemplate(api, latestTemplateImage)
  renderTemplateParts(api, chartTemplateRef.current?.parts || [])
  renderChartMarks(api, marksRef.current)
  styleTemplateParts(api, partStateRef.current)
})
```

Safe to re-run: `renderTemplateParts` already drops every existing
`derma_template_part` element before drawing (`:635-636`), so it replaces rather
than accumulates — the same property that makes the drawer path idempotent.

Persist-time, parts join badges in the filter that already exists:

```js
elements: elements
  .filter((element) => element.customData?.kind !== BADGE_KIND)
  .filter((element) => element.customData?.kind !== TEMPLATE_PART_KIND)
```

`TEMPLATE_PART_KIND` is extracted next to `BADGE_KIND` (`:6`) so the string
`"derma_template_part"` has one definition instead of the five it has today.
`exportToBlob` keeps receiving the **live** scene, so hidden areas export at
`opacity: 0` and visible ones export as drawn.

### 2. `Hide Areas` reflects the canvas — `annotation/DermaAnnotationStudio.jsx`

The button is gated on outlines actually rendered rather than on rows fetched.
`EmbeddedExcalidraw` gains a `getRenderedPartCount()` handle beside the existing
ones, surfaced through the `sceneRevision` the studio already tracks.

### 3. One number per mark — `excalidraw/EmbeddedExcalidraw.jsx`

```js
function createNumberedDot(origin, color, groupId, template, sequence, procedureVariables) {
  return [ellipseElement(origin.x - 8, origin.y - 8, 16, 16, color, groupId, template, procedureVariables, { backgroundColor: color })]
}
```

The `sequence` parameter stays in the signature — it still reaches
`customData.sequence` through `renderChartMarks` (`:617`), which the fan-out and
the badge collector both read. Only the drawn text goes.

### 4. Identity, not hashes — `api.py` + `DermaChart.vue`

`_load_annotations_for_parents` selects the label it already stores:

```python
wanted = ["name", "annotation_template", "custom_derma_body_template_title", "image", "json", "creation", "modified"]
```

`_select_existing_fields` already guards this — a site without the custom field
simply loads without it, and the client falls back as it does today.

```js
function annotationTemplateLabel(annotation) {
  return (
    annotation?.custom_derma_body_template_title ||
    annotation?.annotation_template ||
    annotation?.title ||
    __("Drawing")
  )
}
```

The docname stops being a label of last resort — `Drawing` is more honest than a
hash. The printed sheet gains a real header, every value escaped:

```js
<h2>${escapeHtml(patientName)}</h2>
<p>${escapeHtml([mrn, templateLabel, drawnOn, practitioner, encounterName].filter(Boolean).join(" · "))}</p>
```

Card dates stop truncating by widening `.chart-annotation-list` to
`minmax(190px, 1fr)`.

### 5. More than one consultation drawing — `DermaChart.vue`

The consultation button passes the explicit fresh marker the procedure anchor
already uses, and the strip resumes a specific drawing:

```js
@click="openAnnotationStudio({ annotation: null })"   // header button: always a new drawing
openAnnotationStudio({ annotation })                  // strip card: resume that one
```

`latestAnnotationForAnchor` is **not** deleted — the strip card path routes
through the same `source_name === encounter.value.name` check, so a card
belonging to a previous visit opens the read-only review dialog exactly as it
does today and can never become a resume target. The strip's heading becomes
**Drawings** (`{n} saved drawing(s)` sub-line unchanged) and its cards gain a
`Review` / `Edit` split so "open the picture" and "keep drawing" stop being the
same click.

What stays unchanged: every endpoint's signature except one field in a `SELECT`,
the fan-out, badge computation, mark placement, and both bundle filenames.

## Security

The one backend change adds an existing do_derma-owned field to an existing
read inside `_load_derma_annotation_context`, which is reached only through
whitelisted endpoints that already call `_ensure_clinical_access()`. No new
endpoint, so the gate's coverage is unchanged and `TestClinicalAccessGate` still
describes the boundary.

The print window is the sensitive surface: it is hand-written HTML in a
`window.open` document with no autoescaping, and this change puts **patient
identity** into it. Every interpolated value — patient name, MRN, template
title, date, practitioner, encounter — goes through the existing `escapeHtml`
(which prefers `frappe.utils.escape_html`). `annotation_data` continues to be
inserted as server-generated HTML that was escaped at generation
(`printing/render.py`'s rule, mirrored here). Regression: the new integration
test asserts the label field round-trips, and the manual pass checks the rendered
header.

## Acceptance Criteria

- Reopening a saved drawing shows the template's area outlines; `Hide Areas`
  visibly clears them and `Show Areas` brings them back.
- `Hide Areas` is not offered when the canvas has no outlines.
- A saved annotation's JSON contains no `derma_template_part` elements, and
  reopening it still shows outlines — proving they are re-derived, not stored.
- Editing a template's parts and reopening an older drawing shows the **new**
  outlines, with none of the old geometry.
- Each mark carries exactly one number, and it matches its row in the legend
  table and on the printout.
- No clinician-facing surface — review dialog title, strip card, print heading —
  shows a docname hash; a drawing with no template title reads `Drawing`.
- The printed sheet shows patient name, MRN, body template, drawing date,
  practitioner and encounter, all escaped.
- Strip card dates render in full.
- `Annotate Consultation` on an encounter that already has a drawing creates a
  **second** one; both appear in the strip and each reopens its own scene.
- Saving a resumed drawing updates that drawing — no regression to the saved-row
  response fixed in `2026-08-13-annotation_studio_flow.md`.
- An annotation belonging to a **previous visit** is still never resumable.
- Marks are not duplicated by any save; the encounter's `Derma Chart Mark` count
  is unchanged by a resave.

## Phases

1. **Areas.** Render on resume, strip on persist, gate the toggle on the canvas.
   *Exit:* outlines appear on a resumed drawing, the toggle changes it, and the
   saved JSON has no part elements.
2. **Numbering.** *Exit:* one number per mark; canvas, exported PNG and legend
   agree.
3. **Identity.** Field in the read, label fallback, print header, card width.
   *Exit:* no hash on any clinician-facing surface; the sheet names the patient.
4. **Multiple drawings.** Fresh path for the consultation button, strip
   Review/Edit split, heading rename. *Exit:* two drawings on one encounter, each
   resumable, with the previous-visit guard intact.

## Open Questions

- Should the strip cap at 8 cards (`annotations.slice(0, 8)`, `:128`) once several
  drawings per encounter are normal? *Default:* keep 8 for now; revisit if a
  clinic reports hitting it.
- Should the legend table be shown for consultation saves with no tagged
  elements? *Default:* yes, empty — the dialog already renders
  "No annotation details."

## Reconciliation — what changed vs the plan

Three premises in Current State were wrong. Each is corrected in place above only where the
code now differs; the record of the error stays here.

- **"No new custom field, no patch, no fixture — the label field already exists."** It does not.
  `custom_derma_body_template_title` is written by `_save_health_annotation` behind a `_has_field`
  guard and read by `get_derma_annotation_summary`, but **nothing in the app ever created it** —
  `_has_field(...)` returned `False` on this site and `Custom Field` held no row for
  `Health Annotation` at all. So the label had never been stored anywhere, and the desk toolbar
  button at `api.py:1755` had been silently falling back to `"Drawing"` for every annotation
  since it was written. Adding the field to the read alone would have fixed nothing. Shipped
  `patches/add_derma_annotation_title_field.py`, mirroring `add_derma_annotation_data_field.py`
  exactly (existence check, `create_custom_fields`, `clear_cache`). **This spec now requires a
  migrate.**
- **Area outlines were not only missing on resume — they had never rendered at all.**
  `parsePartPoints` (`EmbeddedExcalidraw.jsx:799-809`) accepts only an array of `[x, y]` pairs in
  template-relative 0..1 coordinates, which is exactly what the Body Map Designer writes
  (`body-template-editor.bundle.jsx:216`). Both seeders wrote
  `{"type": "rectangle", "x": 30, …}` instead — an object, in 0..100 units — so every seeded part
  was silently dropped by the `!Array.isArray` guard. The resume-path bug was real and is fixed,
  but on demo and E2E data it was masked by unreadable geometry. Both seeders now emit closed
  polygons and **converge the shape on re-run** rather than skipping rows that already exist,
  because the idempotent `if existing: continue` would otherwise preserve the broken value
  forever. Production templates drawn in the designer were never affected.
- **The badge layer's number never rendered on the live canvas.** What the QA pass photographed
  as a numbered pill was the *mark's* own text; the badge circle beside it was blank. Its text
  element was missing `baseline`, a legacy field Excalidraw 0.17 still measures against — the
  export path re-measures and so the number appeared in the saved PNG but never on screen.
  Dropping the mark's number therefore left *no* number visible until `baseline: 11` was added to
  `badgeElements`. Without that one line this spec's decision would have made the canvas worse.
- **`Hide Areas` could not be driven off `sceneRevision`.** `onSceneChanged` fires only when the
  **mark layer** signature changes (`EmbeddedExcalidraw.jsx:320-328`), so a part-only render never
  reaches a memo — the toggle stayed hidden on a canvas full of outlines. The count is now set
  from the same `onSceneReady` callback the safety spec added, which fires exactly when parts are
  rendered.
- **The strip gained a `Review`/`Edit` split** rather than making the whole card resume, so
  "open the picture" and "keep drawing" stop being the same click. `Edit` renders only when
  `isResumableAnnotation` holds, which applies `latestAnnotationForAnchor`'s previous-visit guard
  per row.

## Verification

- **Integration**: `bench --site dermaone.localhost run-tests --app do_derma` — **84 tests OK**.
  Two new tests in `TestAnnotationSummary`: the summary label resolves to the body template title,
  and the chart context carries `custom_derma_body_template_title`. Both proven **RED first** by
  removing the field from the `wanted` list and re-running — `FAILED (failures=2)` — then restored.
  (They skip on a site without the custom field, so the patch was applied before they could pass.)
- **Migrate**: `bench --site dermaone.localhost migrate` — clean; the patch created the field
  (`_has_field` went `False` → `True`).
- **E2E**: `npx playwright test` — **50 passed (7.2m)**, including new consultation specs for the
  areas toggle and for a second drawing on one encounter.
- **Build**: `bench build --app do_derma` clean; no bundle renamed.
- **Lint**: `pipx run ruff check` clean on `api.py`'s edit region, both seeders, the new patch and
  `test_api.py`.
- **Manual (browser, 2026-08-14)**, demo patient `PAT-2026-1448`:
  - Four dashed area outlines render on a new drawing and on a **resumed** one; `Hide Areas`
    clears them and `Show Areas` restores them.
  - Saved scene inspected server-side: `elements=4` — template, 2 marks, 1 freedraw — and
    **no `derma_template_part`**, proving outlines are re-derived rather than stored.
  - Each mark carries exactly one number on canvas, in the exported PNG and in the legend.
  - Review dialog title read `DEMO Face Map · 14-08-2026 17:37`; the strip cards read the
    template title over a full, untruncated timestamp. No docname hash anywhere.
  - Printed sheet headed `DEMO Amina Haddad`, sub-line
    `MRN: PAT-2026-1448 · DEMO Face Map · 14-08-2026 17:37 · DEMO Dr Farah Nasser · HLC-ENC-2026-03308`.
  - `Annotate Consultation` on an encounter that already had a drawing produced a **second** one
    (`ENC_ANNOTATIONS 2`), each resumable from its own card; `Edit` appears only on rows this
    encounter owns.
  - Marks were not duplicated by the save: the encounter's `Derma Chart Mark` count was unchanged.

### Not yet run

- Annotating after **Complete Encounter**.
- A template whose parts are edited between saves — the stale-geometry case the strip-on-persist
  rule exists for is argued from the code, not exercised.

## Files to touch (summary)

| File | Change |
|---|---|
| `do_derma/api.py` | select `custom_derma_body_template_title` in `_load_annotations_for_parents` |
| `do_derma/patches/add_derma_annotation_title_field.py` | *(new)* create the label custom field |
| `do_derma/patches.txt` | register the patch |
| `do_derma/demo_seed.py`, `do_derma/e2e_seed.py` | part outlines as polygons, converged on re-run |
| `do_derma/tests/test_api.py` | label field round-trips on the annotation row |
| `do_derma/public/js/chart/excalidraw/EmbeddedExcalidraw.jsx` | parts on resume, `TEMPLATE_PART_KIND` strip on persist, `getRenderedPartCount`, numbering |
| `do_derma/public/js/chart/annotation/DermaAnnotationStudio.jsx` | `Hide Areas` gated on rendered outlines |
| `do_derma/public/js/chart/DermaChart.vue` | label fallback, print header, fresh-drawing path, strip heading + Review/Edit |
| `do_derma/public/js/chart/derma_chart.bundle.css` | card width so dates stop truncating |
| `e2e/tests/annotation-consultation.spec.ts` | areas toggle, second drawing on one encounter |
