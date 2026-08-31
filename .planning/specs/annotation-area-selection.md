# Annotation Area Selection: unselect, export only what is selected, restore on load

## Problem Statement

A practitioner marking up a body template in the annotation studio clicks a predefined
area to fill in its area variables. Three things then go wrong:

1. **The click cannot be taken back.** Once an area is clicked it stays the Selected
   Area for the rest of the session. Clicking it again does nothing, clicking bare
   canvas does nothing, and there is no control anywhere that clears it. An area
   picked by accident - or picked, filled, then reconsidered - is stuck.

2. **The saved image shows every area, not the ones that matter.** The exported PNG
   is drawn from the whole scene, so every area outline the template declares is
   baked into it: the one the practitioner selected, the ones holding values, and the
   faint dashed ones nobody ever touched. A drawing of one forehead lesion prints with
   the entire face grid over it. The only escape today is "Hide Areas", which is
   all-or-nothing - it removes the selected area from the image too.

3. **Reopening the drawing forgets the selection.** Area *values* survive a save and
   come back, but which areas were selected does not - it is never written anywhere.
   A resumed drawing opens with no area selected, so the practitioner cannot tell
   what the previous session chose, and a resave would export a different image from
   the one already filed.

## Solution

Selection becomes an explicit, plural, durable property of the drawing: the set of
areas this annotation is *about*.

- Clicking an area selects it and opens its variable editor. Clicking the area that is
  already selected **and** already open unselects it. Clicking a selected-but-not-open
  area reopens its editor without unselecting - editing a value must never cost the
  selection. Clicking bare canvas closes the editor and leaves the set alone.
- The Selected Area panel gains an explicit unselect control and a count, so there is
  always a visible way out that does not depend on guessing the canvas rule.
- The exported image renders only the selected areas. Unselected outlines stay on the
  canvas, where they are the practitioner's guide, and stay out of the PNG, which is
  the clinical record. "Hide Areas" is unchanged and still hides everything on screen.
- The selection set is saved with the annotation and restored on reopen, styled as
  selected, so the drawing reopens looking like the image that was filed.

## User Stories

1. As a practitioner, I want to click an area a second time to unselect it, so that a
   mis-click is not permanent.
2. As a practitioner, I want an explicit unselect control in the Selected Area panel,
   so that I do not have to discover the canvas toggle to undo a selection.
3. As a practitioner, I want clicking an already-selected area to reopen its variable
   editor rather than unselect it, so that correcting a typed value is not a trap.
4. As a practitioner, I want clicking empty canvas to close the variable editor, so
   that the panel reflects what I am working on.
5. As a practitioner, I want clicking empty canvas to leave my selections intact, so
   that panning or placing a mark does not silently change what will be exported.
6. As a practitioner, I want to select several areas in one drawing, so that a
   treatment covering forehead and both cheeks produces one image showing all three.
7. As a practitioner, I want each selected area drawn in the bold selected style, so
   that I can see at a glance which areas the drawing is about.
8. As a practitioner, I want a count of selected areas in the panel, so that I know how
   many areas the image will carry without hunting the canvas for outlines.
9. As a practitioner, I want the exported image to contain only my selected areas, so
   that the filed record shows the treated site rather than the template's whole grid.
10. As a practitioner, I want untouched areas absent from the exported image, so that a
    single-site treatment does not print as a face covered in boxes.
11. As a practitioner, I want areas holding values but no longer selected to be absent
    from the exported image, so that unselecting genuinely removes an area from the
    record and not just from the panel.
12. As a practitioner, I want unselected areas to stay visible on the canvas while I
    work, so that I keep the template's guide even though it will not be exported.
13. As a practitioner, I want "Hide Areas" to keep working as a screen-only view
    control, so that a clean canvas view is still one click away.
14. As a practitioner, I want an export made while areas are hidden to contain the same
    selected areas as one made while they are shown, so that a view toggle never
    changes what is filed.
15. As a practitioner, I want a drawing with no selected areas to export with no
    outlines at all, so that free-hand work on a template is not littered with grid.
16. As a practitioner, I want my selection saved with the annotation, so that closing
    and reopening the drawing does not lose it.
17. As a practitioner, I want a reopened drawing to show its saved areas already
    selected, so that I can see what the previous session decided.
18. As a practitioner, I want resaving a reopened drawing without touching it to
    produce the same image, so that the record does not drift between saves.
19. As a practitioner, I want to unselect an area in a reopened drawing and resave, so
    that a correction to yesterday's selection is possible.
20. As a practitioner, I want an area's typed values kept when I unselect it, so that
    reselecting it restores what I typed instead of making me retype it.
21. As a practitioner, I want a drawing saved before this change to reopen with its
    value-holding areas selected, so that resaving an old annotation does not silently
    strip areas out of its image.
22. As a practitioner, I want area badges numbered only for selected areas, so that the
    legend never points at an outline the image does not show.
23. As a practitioner, I want the badge numbering to stay contiguous after I unselect an
    area, so that the printed legend has no gaps.
24. As a practitioner, I want switching body template to reset the selection to that
    template's own areas, so that a selection cannot name an area that is not on screen.
25. As a practitioner, I want placing a mark inside an unselected area to still record
    that area on the mark, so that the mark's region data is unaffected by this change.
26. As a practitioner using the consultation sketchpad (no procedure anchor), I want the
    export to behave the same way, so that the two entry points do not produce
    different images from the same template.
27. As a clinician reading the chart later, I want the annotation image to show only the
    areas the treating practitioner selected, so that I am not misled about which sites
    were involved.
28. As a practitioner, I want the drawing's dirty check to ignore my selection changes
    the same way it ignores the derived area layer today, so that merely clicking around
    does not raise a discard prompt.

## Implementation Decisions

### Selection model

- Selection moves from a single `selectedPart` object to an **ordered set of area
  names** owned by the studio, plus a separate **focused area** that drives the
  Selected Area variable editor. The set is what gets styled, exported and persisted;
  the focus is transient UI state and is never persisted.
- The canvas click rule, as a state machine over `(selected, focused)` for the clicked
  area name:

  | clicked area is | action |
  | --- | --- |
  | not selected | add to set, focus it |
  | selected, not focused | focus it (set unchanged) |
  | selected and focused | remove from set, clear focus |
  | (bare canvas) | clear focus, set unchanged |

- The canvas must report a click that hits no area. Today the embedded canvas only
  calls back on a hit; it will call back with `null` when the pointer lands on no area,
  so the studio can clear focus. Clicks that hit a mark keep their current precedence
  and do not touch area selection.
- Area *values* are keyed by area name and are unaffected by selection. Unselecting
  keeps the values; reselecting shows them again. Values continue to persist through
  their existing paths (`derma_area_values` on the scene, plus the area-variable rows
  written onto marks placed in that area).

### Canvas layer

- The part-state bag the canvas holds gains a `selected` **list** where it holds a
  single name today. Three-state styling is unchanged in intent: selected areas draw
  bold and solid, areas holding values draw solid-tinted, empty areas draw faint
  dashed, and the hide-all override still wins over all three.
- Export gains an **element filter**: the blob export receives the scene minus every
  area-layer element whose area name is not in the selected set. The on-screen scene is
  not modified - no restyle, no hide-and-restore round trip - so nothing flickers and a
  failed export cannot leave the canvas in a half-hidden state.
- The export filter is independent of the hide-all override, so an export taken while
  areas are hidden carries the same selected areas as one taken while they are shown.
- The persisted scene JSON is unchanged in shape: the area layer is already stripped
  before persisting and re-derived from the body template on load, which is exactly why
  the selection needs a key of its own rather than living in the element list.

### Persistence

- The save payload gains `selected_areas`: a list of area names. The server stores it on
  the scene JSON as `derma_selected_areas`, next to `derma_area_values`.
- It follows the same omit-versus-clear contract the area values already use: an absent
  or non-list value leaves whatever is stored alone, an explicit empty list clears the
  selection. Unknown or non-string entries are dropped; order is preserved; duplicates
  are collapsed.
- On load the studio seeds the set from `derma_selected_areas`, then intersects it with
  the areas the current body template actually declares, so a selection can never name
  an area that is not on screen.
- **Backward compatibility:** when `derma_selected_areas` is absent entirely - every
  annotation saved before this change - the studio seeds the set from the area names in
  `derma_area_values` that hold at least one non-empty value. An old drawing therefore
  reopens with the areas it was about already selected, and resaving it does not strip
  them out of its image. An explicitly stored empty list is honoured as empty and is
  not treated as absent.

### Badges

- Area badges are collected for selected areas only, instead of for every area holding
  values. Mark badges are untouched. Badge numbering runs over the filtered list, so it
  stays contiguous.
- Since values can only be typed into a focused area, and focusing selects, filled areas
  are a subset of selected areas in normal use; the filter only bites on legacy data and
  on areas the practitioner deliberately unselected after filling them.

### Panel

- The Selected Area panel keeps binding its editor to the focused area. It gains the
  focused area's selected state as an explicit toggle control and a count of selected
  areas. Its empty text changes to describe selection rather than only value entry.
- The "Hide Areas" header button, its render-count gate, and the badges toggle are
  unchanged.

### Out-of-band behaviour left alone

- Mark placement continues to resolve and record the area under the pointer whether or
  not that area is selected: `body_region`, `region_label` and `body_template_part` on
  the mark are unaffected.
- The dirty-signature already ignores the derived area layer, so selection changes do
  not by themselves make a drawing dirty. This is deliberate and unchanged.

## Testing Decisions

A good test here asserts on what the practitioner or the next clinician can observe -
what the server stored, what came back on reload, what the image contains - not on which
internal helper was called or what shape a ref holds.

### Machine-tested seam: the annotation save API

The only seam in this repo with a runner behind it is the Python API. `test_api.py`
already reaches into the stored scene JSON to assert on `derma_area_values`; the new
tests sit beside those and use the same approach.

- Saving with a list of selected areas stores them on the scene JSON in order.
- Saving with an explicit empty list clears a previously stored selection.
- Saving with the key omitted leaves a previously stored selection alone (mirrors the
  omit-versus-clear rule the area values already prove).
- Non-string and duplicate entries are dropped; the stored value is always a list.
- A selection arriving JSON-encoded from the browser is accepted, as the area-variable
  rows already are.
- Selected areas and area values round-trip together without either clobbering the
  other, in both orders.
- An annotation saved without the key reads back with no selection stored, so the
  client-side legacy fallback has something honest to detect.

Prior art: `do_derma/tests/test_api.py` (annotation save and scene-JSON assertions),
`do_derma/tests/test_body_template_areas.py` (area-variable omit-versus-clear rules and
JSON-encoded payloads from the browser).

### Browser-verified behaviour

The studio is React with no JS test runner in this repo, and adding one is out of scope.
These are verified by driving the running site:

- Click an area, click it again, confirm it is no longer selected and the panel is empty.
- Click a selected area after focusing another, confirm the editor reopens and the area
  stays selected.
- Click bare canvas, confirm the editor closes and the selection count is unchanged.
- Select one area on a template declaring several, save, and confirm the stored image
  shows one outline - the selected one - and no others.
- Fill an area, unselect it, save, confirm its outline is absent from the image and its
  values are still stored.
- Save with areas hidden and with areas shown, confirm both images carry the same areas.
- Reopen a saved annotation, confirm the saved areas come back styled as selected.
- Reopen an annotation saved before this change, confirm its value-holding areas come
  back selected.

Note the standing limitation: a Python test cannot see a payload the studio never sends,
so the API tests prove the contract, not that the studio honours it. The browser pass is
what closes that gap.

## Out of Scope

- Introducing a JavaScript test framework or component tests for the studio.
- Any change to how area *variables* are stored, validated, or fanned out onto marks.
- Any change to mark placement, mark badges, marker sizing, or photo capture.
- Changing "Hide Areas" from a screen-only control into anything that affects the export.
- Per-area export styling (colour, opacity, labels) beyond the existing three-state rule.
- A selected-areas chip list or any other new navigation surface for the selection; the
  panel's toggle and count are the whole UI addition.
- Selecting areas across more than one body template in a single annotation.
- Backfilling or migrating stored annotations; the legacy fallback is read-time only and
  writes nothing until the practitioner saves.
- The chart-side rendering of saved annotations outside the studio.

## Further Notes

- The choice of a plural set rather than a single selection is forced by the export
  requirement: with a single selection, an image could never show two treated sites, and
  every area filled earlier in the session would vanish from the record. Plural is also
  what makes "only selected areas show up" a rule a practitioner can act on rather than
  a surprise.
- Filtering at export rather than restyling the live scene matters for a clinical
  record: an exception mid-save can never leave the canvas showing something other than
  what the practitioner drew, and there is no visible flash during the save.
- The legacy fallback deliberately reads "has a non-empty value" rather than "exists as a
  key", because a cleared area still names itself with a blank value in the stored map -
  a cleared area is not evidence of selection.
- `DermaAnnotationStudio.jsx` (1.5k lines) and `EmbeddedExcalidraw.jsx` (1.7k lines) are
  both large. `EmbeddedExcalidraw.jsx` is a sanctioned exception to the file-size rule;
  `DermaAnnotationStudio.jsx` is not, so prefer extending the existing selection helpers
  in place over adding new top-level functions to it.
