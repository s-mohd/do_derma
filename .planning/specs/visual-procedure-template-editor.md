# Visual Procedure Template Editor

Status: ready for implementation
Agreed: 2026-08-20
Branch: `feat/visual-procedure-template-editor`
Prototype: variant A of the throwaway scratchpad prototype (card grid + full-panel detail) won.

## Problem Statement

A clinic administrator opens the derma configuration page to see how a procedure will behave on
the chart, and the Procedure Templates panel only shows a table of names, counts and warnings.
The one edit affordance routes out to the Clinical Procedure Template desk form, which is built
for an ERPNext audience: the derma settings are scattered among consumables, sample collection
and medical coding, the marker behaviour is a Select of bare keys like `triangle_cluster` with
nothing to look at, and the variables are raw JSON. An administrator cannot see what a template
will draw, and cannot change it without leaving the workspace they were told to use.

## Solution

The Procedure Templates panel becomes a visual editor. Templates appear as cards grouped by
category, each card drawing the marker the chart will actually stamp, in the colour it will use.
Clicking a card opens a detail view inside the same panel, where every setting that governs
derma behaviour — category, body maps, marker, safety requirements, variables, note sentence —
is edited with real controls and saved in one go. Creating and retiring a template happen in the
same place. The desk form stays reachable for the rare ERPNext-shaped fields, as a single link.

## User Stories

1. As a clinic administrator, I want to see every derma procedure template as a card, so that I can survey the whole configuration without reading a table.
2. As a clinic administrator, I want cards grouped under their category, so that I can see which procedures share a workflow.
3. As a clinic administrator, I want templates with no category grouped under "Uncategorised" at the end, so that they are visible without being flagged as broken.
4. As a clinic administrator, I want each card to draw the marker the chart will stamp, so that I can recognise a procedure by its mark.
5. As a clinic administrator, I want a card to draw its category's marker when the template has none of its own, so that the card shows what will really happen rather than an empty field.
6. As a clinic administrator, I want an inherited marker labelled as inherited, so that I know changing the category changes this procedure.
7. As a clinic administrator, I want the card to show the marker colour, so that I can spot two procedures that will look identical on the chart.
8. As a clinic administrator, I want to see how many variables a template records, so that I can tell a fully configured procedure from a bare one.
9. As a clinic administrator, I want retired templates hidden by default and revealed by a toggle, so that the grid shows what my clinic actually offers.
10. As a clinic administrator, I want a retired template to look retired when shown, so that I do not edit it by mistake.
11. As a clinic administrator, I want to search templates by name or category, so that I can reach one procedure in a long list.
12. As a clinic administrator, I want warning badges on the card, so that I can see which templates need attention before opening any of them.
13. As a clinic administrator, I want to click a warning and land on the section that causes it, so that I do not hunt for the setting it refers to.
14. As a clinic administrator, I want a card to tell me when a custom marker preset overrides the marker shape, so that the panel never shows me a shape the chart will not draw.
15. As a clinic administrator, I want to open a template into a detail view inside the panel, so that I stay in the configuration workspace.
16. As a clinic administrator, I want the detail view to be one scrolling page of sections, so that I can see every derma setting without hunting through tabs.
17. As a clinic administrator, I want to edit the description, item group, medical department, billable flag and rate, so that routine corrections do not need the desk form.
18. As a clinic administrator, I want the template name shown read-only, so that I do not rename a document other records link to.
19. As a clinic administrator, I want a link to the full desk form, so that consumables, sample collection and medical coding remain reachable.
20. As a clinic administrator, I want to pick the category from a list, so that a procedure inherits the right workflow and defaults.
21. As a clinic administrator, I want to choose the marker from tiles that draw each shape, so that I pick by appearance instead of by keyword.
22. As a clinic administrator, I want an explicit "inherit from category" choice among those tiles, so that I can hand the decision back to the category.
23. As a clinic administrator, I want to pick a marker colour from preset swatches, so that markers stay visually consistent across the clinic.
24. As a clinic administrator, I want to type an exact colour when a preset does not fit, so that I can match an existing convention.
25. As a clinic administrator, I want to choose the body maps a procedure may be charted on with checkboxes, so that I do not type template names into a text field.
26. As a clinic administrator, I want choosing no body map to mean every map, so that the common case needs no work.
27. As a clinic administrator, I want to set the four safety requirements with checkboxes, so that consent, photos, product tracking and device settings are enforced where they matter.
28. As a clinic administrator, I want to see the resulting list of required fields and who owns each one, so that I understand what the chart will demand at procedure time.
29. As a clinic administrator, I want the required-field list to be read-only, so that it cannot disagree with the variables and flags that produce it.
30. As a clinic administrator, I want a required field the chart cannot enforce called out, so that I can fix a promise the system will not keep.
31. As a clinic administrator, I want to add, relabel, retype and remove variables in the detail view, so that I do not need the separate variables screen.
32. As a clinic administrator, I want variables owned by a safety flag marked as such and locked, so that I cannot half-disable a safety requirement.
33. As a clinic administrator, I want to write the note sentence in a plain box, so that the procedure note starts from the wording my clinic uses.
34. As a clinic administrator, I want one Save button for the whole detail view, so that I know when my changes are stored.
35. As a clinic administrator, I want to be told when someone else changed the template while I was editing, so that I do not silently overwrite their work.
36. As a clinic administrator, I want to create a template from the panel, so that adding a new procedure does not start in the desk form.
37. As a clinic administrator, I want a new template to be billable with a rate by default, so that it can be charged without extra setup.
38. As a clinic administrator, I want to retire a template from its detail view, so that it stops appearing in the chart without being deleted.
39. As a clinic administrator, I want the empty state to offer the New button, so that a fresh site tells me what to do first.
40. As a practitioner, I want the config marker preview to match the chart stamp, so that what an administrator picked is what I see while charting.
41. As a clinic without permission to change procedure templates, I want the panel to be read-only, so that we can review the configuration without risking it.

## Implementation Decisions

### Panel

- `ProcedureTemplatesPanel` is rewritten as a card grid. `TemplateVariableBuilder` stops being a
  standalone screen and becomes the Variables section of the new detail view.
- Grid state (search text, show-retired toggle, selected template) lives in the panel. Grouping
  puts named categories first in alphabetical order and "Uncategorised" last.
- Search matches template name and category only.
- The card renders the effective marker: the template's own behaviour and colour, falling back to
  its category's, matching what `get_derma_procedure_templates` already resolves for the chart.
  An inherited marker is labelled.
- Warning badges carry the section that owns them, and clicking one opens the detail view scrolled
  to that section. `no_required_fields` and `unenforced_required_fields` belong to Requirements;
  `unreadable_variables` belongs to Variables.
- A non-empty marker preset shows as a pill on the card and a notice in the detail view, because
  the preset overrides the shape the tiles show. The preset itself is not editable here.
- The detail view is one scrolling column of five sections in this order: Identity and billing,
  Chart behavior, Requirements, Variables, Note sentence. No tabs.
- New mode uses the same detail view with an editable name; saving creates the record and reloads
  the saved state.
- The panel renders read-only when the overview says the session cannot write.

### Server

- Two new whitelisted endpoints replace `get_derma_template_variables` and
  `save_derma_template_variables`, which are deleted along with their client callers:
  - `get_derma_procedure_template(template)` returns the core basics, the derma fields, the
    variables, the derived required-field list with owners, the marker behaviour options read
    from meta, and the document's `modified`.
  - `save_derma_procedure_template(...)` writes everything in one document save.
- Both reuse the existing gate and helpers rather than re-deriving anything: `_ensure_clinical_access`,
  `_get_template_variables`, `_required_field_owners`, `_validated_variable_rows`, and the
  category defaults used by the chart.
- Saves carry the client's `modified` value and let Frappe's own timestamp check raise on a
  concurrent edit. No merge, no last-write-wins.
- `get_derma_config_overview` gains `can_write`, from
  `frappe.has_permission("Clinical Procedure Template", "write")`. Saving never runs with
  elevated permissions: the doctype's permissions stay the only gate.
- Marker behaviour options come from `frappe.get_meta` at request time, because
  `add_derma_freehand_marker_behavior` appends options through a property setter. No literal list
  of behaviours is added anywhere.
- Allowed body templates keep their storage: a comma-separated string on
  `custom_derma_allowed_body_templates`, empty meaning unrestricted. The panel converts to and
  from a list at the edges, so `_ensure_body_template_allowed` and the shared client helper are
  untouched.
- The required-fields JSON stays derived. The endpoint writes it from the saved variables and the
  safety flags exactly as the existing materialisation does; the client never sends it.
- Creating a template sets `is_billable` and `rate` and leaves Item creation to the healthcare
  controller. No item logic is added to this app.
- Renaming is not supported by these endpoints.

### Marker preview

- A new module under the shared client folder maps a marker behaviour to an SVG shape and is used
  by both the cards and the marker tiles.
- It is a faithful copy of the Excalidraw stamp geometry, not a shared code path: the stamps are
  Excalidraw element factories in the React chart bundle, and the config page is a plain Vue
  bundle. The chart is not modified.
- Resolution follows the same substring chain the chart uses, in the same order, so `five_lines`
  draws hatching and `freehand` draws a stroke. The chain, taken from the prototype:

  ```
  x → cross, target → target, hatch|five_lines → hatch, area → rectangle,
  triangle → triangle cluster, finding_dot|three_dots → dot cluster,
  freehand|stroke|paint → stroke, otherwise → filled dot
  ```

- An unknown behaviour falls back to the filled dot, matching `createStampElements`.

## Testing Decisions

A good test here states a behaviour an administrator or the chart depends on, and reads it back
through the same seam a caller uses. It does not assert on private helpers, JSON string shapes, or
component internals.

The seam is the whitelisted API. Every behaviour above is reachable through
`get_derma_config_overview`, `get_derma_procedure_template` and `save_derma_procedure_template`,
so no new seam is introduced for the server work. Prior art: `tests/test_config_workspace.py`
drives `get_derma_config_overview` directly and asserts on the payload; `tests/test_template_variables.py`
drives the variables endpoints the same way and is the model for the save tests, including its
round-trip style ("writes variables the chart then reads").

Tests to write, all in `tests/test_config_workspace.py` alongside the existing config tests:

- The overview reports `can_write` false for a session without write permission on Clinical
  Procedure Template, and true for one with it.
- The save endpoint refuses a caller without write permission.
- A stale `modified` value is refused rather than overwriting.
- A round trip across the core basics and every derma field returns what was saved.
- Variables saved through the new endpoint are the variables the chart later reads, and a
  flag-owned variable still cannot be saved optional.
- The derived required-field list carries each field's owner and whether the chart enforces it.
- Allowed body templates survive the list-to-string conversion, and an empty list still means
  unrestricted.
- Creating a template through the endpoint yields a template the overview then lists.
- Marker behaviour options in the payload come from meta, so a behaviour added by property setter
  appears without a code change.
- Drift: every marker behaviour option in runtime meta resolves to a shape in the shared preview
  module. The test parses the module's behaviour keys, since the repo has no JavaScript test
  runner and this change does not add one.

The variables tests that currently drive the deleted endpoints move to the new ones rather than
being dropped.

## Out of Scope

- Renaming a procedure template from the panel.
- Editing the marker preset JSON, consumables, sample collection, medical coding or nursing
  checklists in the panel.
- Making the Categories panel editable.
- Any change to how the chart draws marks, or to the stamp factories in the chart bundle.
- A JavaScript test runner.

## Further Notes

The prototype that settled the layout lives outside the repo and is disposable; its three variants
were a card grid with full-panel detail, a master list with live detail, and a marker-grouped board
with a tabbed modal. The first won because it keeps the existing panel's information hierarchy —
category first, then procedure — while making the marker the thing you see first.
