# Procedure Annotation Popup — Repair

Date: 2026-08-14
Status: **Phases 1–2 implemented & verified** (2026-08-14) — see [Verification](#verification).
Phase 2 deviated from the plan (it needed a new endpoint) — see
[Reconciliation](#reconciliation--what-changed-vs-the-plan). Phases 3–4 not started.

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

## Phases

1. **Finding 2 — every tagged mark is legend-worthy.** *Exit:* an unparameterised stamp is
   numbered on canvas and printed in the legend; `annotation-badges.spec.ts` green on the new
   contract. **Done.**
2. **Finding 1 — truthful discard.** Delete the marks this session created and left unlinked, and
   name them in the confirm. *Exit:* after a discard, the procedures tab's mark count matches what
   the dialog said would happen. **Done.**
3. **Finding 3 — resume race.** Fit and part geometry both wait on the template *element* having
   non-zero bounds, not just the canvas. *Exit:* a resumed procedure drawing opens fitted with its
   area outlines drawn.
4. **Findings 4 and 5 — drawer filter/search, header wording.** *Exit:* the drawer filters to the
   procedure's own category with a search box; the header names the patient once.

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

### Left behind

The browser check placed a real mark on demo procedure `HLC-CPR-2026-02869`, on top of the
leftovers the QA pass recorded. `bench --site dermaone.localhost execute
do_derma.demo_seed.teardown_demo_data` then `setup_demo_data` resets them.

## Files to touch (summary)

| File | Change |
|---|---|
| `public/js/chart/annotation/DermaAnnotationStudio.jsx` | Phase 1: drop the `hasParams` gate; em dash for an empty parameter cell. Phase 2: `sessionMarks`, the counted confirm, `discardDrawing`, and the close result |
| `do_derma/api.py` | Phase 2: `discard_chart_marks` + `_is_mark_documented` |
| `public/js/chart/DermaChart.vue` | Phase 2: refresh the chart when a discard removed marks |
| `do_derma/tests/test_api.py` | Phase 2: `TestDiscardChartMarks` *(5 cases)* |
| `e2e/tests/annotation-discard.spec.ts` | Phase 2 *(new)*: discard deletes what it placed, keeps what it did not |
| `e2e/tests/annotation-badges.spec.ts` | Rewrite the "not badge-worthy" assertion to the new contract |
| `docs/superpowers/specs/2026-08-14-procedure_annotation_qa.md` | Point findings 1 and 2 at this spec |
