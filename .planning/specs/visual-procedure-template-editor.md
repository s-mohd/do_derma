# Visual Procedure Template Editor

Status: agreed 2026-08-20, not yet implemented
Branch: `feat/visual-procedure-template-editor`

## Problem

The Procedure Templates panel in the derma configuration page is a read-only table whose
only edit affordance routes to the Clinical Procedure Template desk form. A clinic admin who
never opens desk cannot see what a template will draw on the chart, and cannot change it
without meeting an ERPNext form built for a different audience.

## Audience

Non-technical clinic admins. No raw JSON is shown anywhere in the panel. The desk form stays
reachable as an escape hatch, demoted to a single secondary link.

## Grid

`ProcedureTemplatesPanel.vue` becomes a card grid.

- Cards grouped under category headings; templates with no category group under
  "Uncategorised", ordered last, with no warning badge — a category is optional.
- Card contents: template title, marker preview, category, variable count, disabled pill,
  a pill when `custom_derma_marker_preset_json` is non-empty, and the existing warning badges.
- The marker shown is the effective one: a template with no marker of its own displays the
  category's, hinted as inherited, because that is what the chart draws.
- Warning badges are clickable and open the detail view scrolled to the section that owns
  the warning.
- Search filters on template name and category. A "show retired" toggle reveals disabled
  templates, off by default.
- Empty state offers the New button, matching the existing empty-state copy style.

## Detail view

One scrolling view, not tabs, with these sections in order.

1. **Identity & billing** — name (read-only; renaming is a link cascade and stays in desk),
   description, item group, medical department, is billable, rate, disabled.
2. **Chart behavior** — derma category, allowed body templates as a checkbox chip list over
   Derma Body Template (stored comma-separated exactly as today, so
   `shared/allowed_body_templates.js` and `_ensure_body_template_allowed` are untouched;
   empty still means no restriction), marker behavior as preview tiles including an explicit
   "Inherit from category" choice that writes an empty value, marker colour as preset swatches
   with a custom hex fallback.
3. **Requirements** — the four safety checks (consent, before/after photo, product tracking,
   device settings) plus a read-only summary of the required fields and their owners. The
   summary is derived from variables and the safety flags via `_required_fields_with_owners`;
   `custom_derma_required_fields` is never edited directly, so it keeps one owner.
4. **Variables** — the current `TemplateVariableBuilder` table, folded in as a section.
5. **Note sentence** — plain textarea. The chart inserts the text verbatim; no placeholder
   syntax exists to offer.

One Save button covers the whole view. Creating a template uses the same view in a new mode,
saving and then loading the real record. Consumables, sample collection, medical coding,
nursing checklists and the marker preset JSON remain desk-only.

## Server

- New `get_derma_procedure_template(template)` and `save_derma_procedure_template(...)` carry
  the core basics, the derma fields and the variables in one round trip.
  `get_derma_template_variables` and `save_derma_template_variables` are deleted and the
  builder repointed.
- Saves send the document's `modified` timestamp and let Frappe's own check throw on a
  concurrent edit; the panel surfaces the reason rather than overwriting.
- `get_derma_config_overview` gains `can_write`, from
  `frappe.has_permission("Clinical Procedure Template", "write")`. On false the panel renders
  read-only cards. Permissions are never elevated — the doctype's own permissions stay the truth.
- Marker behavior options come from server meta, because
  `add_derma_freehand_marker_behavior` adds options at runtime through a property setter.
- No item logic is added here: the panel sets `is_billable` and `rate`, and the healthcare
  controller creates the Item.

## Marker preview

A new module under `public/js/shared/` renders each marker behavior as SVG. It is a faithful
copy of the shapes `EmbeddedExcalidraw.jsx` stamps, not the same code path: those shapes are
Excalidraw element factories inside the React chart bundle, and the config page is a plain Vue
bundle. The chart is left untouched. An unknown behavior falls back to a plain dot.

## Tests

Python, in `tests/test_config_workspace.py`. The repo has no JS test runner and this change
does not add one.

- Permission gate: no write permission yields read-only payload, and the save endpoint refuses.
- Timestamp mismatch on a stale save.
- Field round trip across the core basics and the derma fields.
- Variables folded into the same save.
- Drift: every marker behavior option in runtime meta has a preview shape in the shared module.

## Out of scope

Renaming templates from the panel, the Categories panel (stays read-only), and any change to
how the chart itself draws marks.
