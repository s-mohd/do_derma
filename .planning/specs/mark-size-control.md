# Mark Size Control

Status: ready for implementation
Agreed: 2026-08-22
Branch: `feat/mark-size-control`

## Problem Statement

A practitioner charting a patient can choose which mark a procedure stamps and what colour it
draws in, and nothing else. Every stamp lands at one hardcoded size: a dot is always 16 px
across, a target always 36 px, an X always spans 36 px. Anatomy does not work that way. Four
filler points on a nose and four on a back need visibly different marks, and a mole the size of
a pinhead gets the same dot as a lesion covering half a cheek. The practitioner's only recourse
today is dragging the placed mark's Excalidraw handles, which does nothing lasting — generated
mark elements are rebuilt from the mark record on every render, so the resize disappears.

The same gap exists one level up. An administrator configuring a procedure template can set its
marker shape and colour in the derma configuration page, so a template's mark looks right
everywhere except in scale, where it looks like every other template's mark.

## Solution

Mark size becomes a settable property, expressed as a multiplier over the existing geometry.

An administrator sets a default size per procedure template in the configuration page, beside
the marker shape and colour they already set, with a sample rendering at the chosen scale.

A practitioner adjusts size in the chart's procedure tool row while stamping. The chosen size
sticks across successive stamps and resets when they switch procedure template. Selecting a
single placed mark retargets the control to that mark, so a size noticed as wrong after
placement is corrected without deleting and re-stamping.

Each mark records the size it was stamped at, so later edits to a template's default leave the
existing chart untouched, and a mark carried forward into a new visit reproduces last visit's
map exactly.

## User Stories

1. As a clinic administrator, I want to set a default mark size on a procedure template, so that a procedure stamps at a scale that suits the anatomy it treats.
2. As a clinic administrator, I want the size control beside the marker shape and colour controls, so that everything governing how a procedure draws lives in one place.
3. As a clinic administrator, I want to set size with a slider, so that I can judge scale by feel rather than by typing a number.
4. As a clinic administrator, I want step buttons next to the slider, so that I can land on an exact value with a gloved finger or on a touchscreen.
5. As a clinic administrator, I want a sample of the marker rendered at the chosen size, so that I can see what the chart will stamp before saving.
6. As a clinic administrator, I want the marker shape tiles to keep their own fixed size while I drag the slider, so that the picker stays readable and the shapes stay identifiable.
7. As a clinic administrator, I want a reset control that returns the size to the default, so that "unset" is reachable without hunting for the exact slider position.
8. As a clinic administrator, I want a template with no size set to behave exactly as it does today, so that adopting this feature requires no work on templates that are already correct.
9. As a clinic administrator, I want the size to be rejected if it is outside the allowed range, so that a broken caller cannot quietly write a mark nobody can see.
10. As a practitioner, I want to change mark size from the procedure tool row, so that I can adjust scale without leaving the pen or switching panels.
11. As a practitioner, I want a slider with step buttons in the chart too, so that the control behaves the same in both places I meet it.
12. As a practitioner, I want a procedure template's default size loaded when I select it, so that the configured scale is what I get without doing anything.
13. As a practitioner, I want my chosen size to stay put across successive stamps, so that placing eight equal points in a row takes one adjustment, not eight.
14. As a practitioner, I want the size to reset when I switch procedure template, so that a large filler setting cannot silently carry over onto a mole mark.
15. As a practitioner, I want the size control to disappear when the active procedure draws an area or a freehand region, so that I am not offered a control that cannot affect a mark I size by dragging.
16. As a practitioner, I want to select a placed mark and change its size, so that a mark I stamped too small is fixed in place.
17. As a practitioner, I want the resized mark to persist, so that it is still the right size when I reopen the chart.
18. As a practitioner, I want the size control to act on the selected mark only when exactly one mark is selected, so that a multi-select cannot resize marks I did not mean to touch.
19. As a practitioner, I want a mark's stroke width to grow with the mark, so that a larger mark reads as a bolder mark and not as a faded outline.
20. As a practitioner, I want a procedure with a custom marker preset to respect the size too, so that the control never appears to do nothing.
21. As a practitioner, I want the numbering badge to grow with its mark, so that a large mark does not carry a badge that looks detached from it.
22. As a practitioner, I want the badge to stay readable at the smallest sizes, so that mark numbers survive at chart zoom and on the printout.
23. As a practitioner, I want the badge to stay clear of the mark it labels at every size, so that a large mark does not sit under its own number.
24. As a practitioner, I want a mark to keep the size it was stamped at even after the template's default changes, so that the record shows what I charted, not what the configuration says today.
25. As a practitioner, I want marks carried forward from a previous visit to keep their original size, so that a size change between visits never reads as a clinical change.
26. As a practitioner, I want marks from previous visits drawn at their stored size, so that the history layer matches what was actually charted.
27. As a practitioner, I want the printed chart to show marks at their stamped size, so that the printout matches the screen.
28. As a practitioner, I want mark size left out of the legend, the printout text and the generated note sentence, so that a drawing affordance never reads as a clinical fact.

## Implementation Decisions

### Size model

Size is a multiplier over the geometry that is currently hardcoded, not an absolute dimension.
The range is 0.5 to 2.0 with a step of 0.25 — seven positions. Default is 1.0, which reproduces
today's output exactly. An empty or missing value means 1.0.

Below 0.5 a dot disappears on print; above 2.0 a target covers an anatomical region larger than
what it is marking. The coarse step keeps stored values readable and stops floating-point drift
from producing values like 1.0000001.

### Storage

Two levels, deliberately not three. Colour has a category-level root because categories are
colour-coded by convention; size is a property of the individual procedure's anatomy, so a
category default would be a level nobody sets.

- A custom size field on Clinical Procedure Template holds the configured default. It is added
  by a new patch file appended to `patches.txt`. Shipped patches are not edited.
- A size field on Derma Chart Mark holds the snapshot taken at stamp time. This field is the
  sole owner of a placed mark's size.

Both fields join the existing marker field allowlists in the API layer, alongside marker
behaviour and marker colour, so the size travels with the payloads that already carry them: the
config overview, the procedure template read and save, the mark list, and the mark save.

### Validation

The write path rejects a non-numeric or out-of-range size with a thrown error. The read path
treats empty or missing as 1.0. Silently clamping a bad value would hide the broken caller that
produced it; an absent value, by contrast, is a legitimate "not set" and is not an error.

### Geometry

Every stamp behaviour scales about its origin: coordinates, radii, offsets between clustered
elements, and stroke widths, with stroke floored at 1 so a scaled-down mark never becomes
invisible. A 2x shape drawn with a 2 px hairline reads as an artefact rather than a bigger mark,
which is why stroke scales with the rest.

Custom marker preset elements scale the same way — their offsets, dimensions and stroke widths
are all relative to the stamp origin already — so both the built-in and preset paths agree.

The control applies to the stamp behaviours only: numbered dot, blue dot, three dots, finding
dot, triangle, triangle cluster, X mark and target. Hatch, five lines and area are placed by
dragging a rectangle, and freehand is drawn with the pen; all four take their size from the
gesture. When the active procedure uses one of those, the control is hidden rather than shown
disabled — the tool row already changes with the tool, and a permanently dead control invites
clicking.

### Badge layer

The numbering badge scales with its mark: diameter is the current 22 px times the scale, clamped
to 18–34 px; font size is the current 12 px times the scale, clamped to 11–16 px. The badge's
vertical offset from the mark scales with the badge so it stays clear at every size.

The clamps exist because the badge serves legibility, not anatomy. A badge at 0.5x is unreadable
on a printed chart, and one at 2x swallows a neighbouring mark.

### Configuration page

The procedure template detail view gains a slider with decrement and increment buttons and a
reset-to-default button. Landing exactly on the default by dragging is fiddly on a touchscreen,
and the button makes "unset" visibly distinct from a deliberate 1.0.

The existing marker shape tiles keep their fixed rendering size. A single separate sample beside
the slider renders the marker at the chosen scale. Resizing twelve tiles while the slider moves
is visual noise, and at small scales the shapes stop being identifiable in a picker.

### Chart

The annotation studio's procedure tool row gains the same slider and step buttons. Size is a
stamping parameter used while the pen is hot — the same tier as tool choice — so burying it in a
side panel would mean switching panels between placements.

The value is initialised from the active procedure template's default, persists across successive
stamps, and resets to the newly selected template's default on a procedure switch.

When exactly one placed mark is selected on the canvas, the control retargets to that mark and
writes through the existing single-mark save endpoint. The mark is then rebuilt from its record,
which is the same path that already renders it, so no separate redraw path is introduced.

### Canvas resize

Dragging an Excalidraw handle on a generated mark stays cosmetic and unpersisted. Marks are
rebuilt from their records on every render, so such a resize is already discarded today; making
it authoritative would create a second owner of the same value, free to drift from the first.

### Carry-forward

A mark copied into a new visit keeps its source mark's size rather than picking up the template's
current default. Carry-forward exists to reproduce the previous visit's map.

### Downstream surfaces

Size does not appear in the legend table, the printout text or the generated note sentence.

## Testing Decisions

A good test here exercises an endpoint the chart or configuration page actually calls and asserts
on what comes back or what is stored — not on how the geometry helpers are factored. Sizes are
asserted as stored and returned values, not as pixel counts inside a drawing function.

The repository has one test framework, the frappe runner, and no JavaScript test infrastructure.
None is introduced. The scale geometry is JavaScript and stays uncovered; the state that outlives
a session is Python and is covered.

Three seams, all of which already exist:

1. **Procedure template read and save** (`get_derma_procedure_template`, `save_derma_procedure_template`,
   and the config overview payload) — a configured default round-trips, an unset default reads as
   the default value, and an out-of-range value is rejected. Prior art: the marker colour and
   marker inheritance tests in `test_config_workspace.py`.
2. **Mark save and list** (`save_chart_mark`, and the mark rows the chart loads) — a stamped size
   is stored on the mark and returned when the chart reloads, a mark saved without a size reads as
   the default, an out-of-range size is rejected, and changing a template's default afterwards does
   not alter an existing mark. Prior art: the mark persistence tests in `test_api.py`.
3. **Carry-forward** (`carry_forward_marks`) — a copied mark carries the source mark's size, not
   the template's current default. Prior art: `test_copies_a_mark_onto_the_current_encounter`.

## Out of Scope

- A category-level size default. Two levels only.
- Persisting an Excalidraw handle-drag as a mark's size.
- Sizing for area, hatch, five-lines and freehand behaviours, which are sized by the placement
  gesture.
- Per-axis sizing, rotation, or any shape editing beyond uniform scale.
- Retroactively resizing existing marks when a template's default changes.
- Showing size in the legend, printout or note narrative.
- A JavaScript test runner.

## Further Notes

The multiplier is stored as a float even though the control exposes seven discrete positions. If
a finer or continuous control is wanted later, it needs no schema change or data migration.

Marks stamped before this change have no stored size and read as 1.0, which is the geometry they
were drawn with, so no backfill is required.
