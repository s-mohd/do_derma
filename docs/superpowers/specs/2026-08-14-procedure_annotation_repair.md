# Procedure Annotation Popup — Repair

Date: 2026-08-14
Status: **Phase 1 implemented & verified** (2026-08-14) — see [Verification](#verification).
Phases 2–4 not started.

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

All of this is `do_derma`-owned frontend; no doctype or endpoint changes.

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

## Non-Goals

- Not changing when marks are saved, nor `_sync_chart_marks_for_annotation` or any of its four
  properties.
- Not touching the badge geometry, the toggle, the scene-signature loop guard, or the review
  dialog — only which items reach them.
- Not touching the area branch's gate or part rendering (phase 3 owns the rendering race).
- No backend change: `api.py`, patches and fixtures are untouched, so **no migrate is required**.
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

## Phases

1. **Finding 2 — every tagged mark is legend-worthy.** *Exit:* an unparameterised stamp is
   numbered on canvas and printed in the legend; `annotation-badges.spec.ts` green on the new
   contract. **Done.**
2. **Finding 1 — truthful discard.** Either name the surviving marks in the confirm or delete the
   unlinked ones this session created. *Exit:* after a discard, the procedures tab's mark count
   matches what the dialog said would happen.
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

## Verification

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

### Left behind

The browser check placed a real mark on demo procedure `HLC-CPR-2026-02869`, on top of the
leftovers the QA pass recorded. `bench --site dermaone.localhost execute
do_derma.demo_seed.teardown_demo_data` then `setup_demo_data` resets them.

## Files to touch (summary)

| File | Change |
|---|---|
| `public/js/chart/annotation/DermaAnnotationStudio.jsx` | Drop the `hasParams` gate; em dash for an empty parameter cell |
| `e2e/tests/annotation-badges.spec.ts` | Rewrite the "not badge-worthy" assertion to the new contract |
| `docs/superpowers/specs/2026-08-14-procedure_annotation_qa.md` | Point finding 2 at this spec |
