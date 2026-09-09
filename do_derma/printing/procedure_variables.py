"""The shared variables each procedure on one encounter recorded, for the printout.

Opt-in per template. These are clinical settings - fluence, device, passes - and the format
they land in is handed to the patient, so a clinic says which of them belong on that copy.
"""

from __future__ import annotations

from typing import Any

import frappe


def get_encounter_procedure_variables(encounter: str | None) -> list[dict[str, Any]]:
	"""One group per procedure whose template asked for these to be printed, in visit order."""
	from do_derma import api

	if not encounter or not api._has_procedure_variables():
		return []
	encounter_field = api._get_clinical_procedure_encounter_field()
	if not encounter_field:
		return []
	if not api._has_field("Clinical Procedure Template", "custom_derma_print_procedure_variables"):
		return []

	procedures = frappe.get_all(
		"Clinical Procedure",
		filters={encounter_field: encounter},
		fields=["name", "procedure_template", "creation"],
		order_by="creation asc",
		limit=0,
	)
	if not procedures:
		return []

	printable = _printable_templates({row.procedure_template for row in procedures if row.procedure_template})
	if not printable:
		return []

	stored = frappe.get_all(
		"Derma Procedure Variable",
		filters={"parent": ["in", [row.name for row in procedures]], "parenttype": "Clinical Procedure"},
		fields=["parent", "procedure_template", "fieldname", "label", "value"],
		order_by="parent asc, idx asc",
		limit=0,
	)
	by_procedure: dict[str, list[dict[str, Any]]] = {}
	for entry in stored:
		if entry.procedure_template not in printable:
			continue
		if not (entry.value or "").strip():
			continue
		by_procedure.setdefault(entry.parent, []).append(
			{"label": entry.label or entry.fieldname, "value": entry.value}
		)

	groups = []
	for row in procedures:
		rows = by_procedure.get(row.name)
		if not rows:
			continue
		groups.append(
			{"procedure": printable.get(row.procedure_template) or row.procedure_template, "rows": rows}
		)
	return groups


def _printable_templates(template_names: set[str]) -> dict[str, str]:
	"""Template name to the label a clinic reads, for the ones opted in to printing."""
	if not template_names:
		return {}
	rows = frappe.get_all(
		"Clinical Procedure Template",
		filters={
			"name": ["in", list(template_names)],
			"custom_derma_print_procedure_variables": 1,
		},
		fields=["name", "template"],
		limit=0,
	)
	return {row.name: row.template or row.name for row in rows}
