from __future__ import annotations

import frappe

from do_derma import api


def execute():
	"""Link existing marks to the Derma Body Template Part they were drawn on.

	Only where `region_label` matches exactly one part on that mark's body template - an
	ambiguous or unmatched label keeps a null link rather than a guess. Re-runnable: marks
	that already carry a link are never revisited.
	"""
	if not (
		api._has_doctype("Derma Body Template Part")
		and api._has_field("Derma Chart Mark", "body_template_part")
	):
		return

	marks = frappe.get_all(
		"Derma Chart Mark",
		filters={
			"body_template_part": ["is", "not set"],
			"region_label": ["is", "set"],
			"body_template": ["is", "set"],
		},
		fields=["name", "body_template", "region_label"],
		limit=0,
	)
	if not marks:
		return

	parts = frappe.get_all(
		"Derma Body Template Part",
		filters={"body_template": ["in", sorted({mark.body_template for mark in marks})]},
		fields=["name", "body_template", "part_name"],
		limit=0,
	)
	by_area: dict[tuple[str, str], list[str]] = {}
	for part in parts:
		by_area.setdefault((part.body_template, part.part_name), []).append(part.name)

	for mark in marks:
		matches = by_area.get((mark.body_template, mark.region_label), [])
		if len(matches) == 1:
			frappe.db.set_value(
				"Derma Chart Mark", mark.name, "body_template_part", matches[0], update_modified=False
			)
