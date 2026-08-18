"""What each procedure on one encounter consumed."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from do_derma.consumables.defaults import has_consumable_doctypes, select_fields

PRINTED_ROW_FIELDS = ["item_code", "item_name", "qty", "uom", "batch_no"]


def get_encounter_consumables(encounter: str | None) -> list[dict[str, Any]]:
	"""One group per procedure, in visit order, skipping whatever consumed nothing.

	A procedure records its materials on its annotations when it has any, and on itself
	when it has none, so the two sources never describe the same procedure twice.
	"""
	if not encounter or not has_consumable_doctypes():
		return []

	groups = [*_mark_groups(encounter), *_procedure_groups(encounter)]
	return [group["group"] for group in sorted(groups, key=lambda group: group["creation"])]


def _mark_groups(encounter: str) -> list[dict[str, Any]]:
	from do_derma import api

	if not api._has_doctype("Derma Chart Mark") or not api._has_field("Derma Chart Mark", "consumables"):
		return []

	marks = frappe.get_all(
		"Derma Chart Mark",
		filters={"encounter": encounter, "status": ["!=", "Archived"]},
		fields=["name", "procedure_template", "creation"],
		order_by="sequence asc, creation asc",
		limit=0,
	)
	if not marks:
		return []
	rows = _rows_by_parent([mark.name for mark in marks], "Derma Chart Mark")
	return _build_groups(marks, rows)


def _procedure_groups(encounter: str) -> list[dict[str, Any]]:
	"""The procedures no annotation covers, which carry their materials themselves."""
	from do_derma import api

	encounter_field = api._get_clinical_procedure_encounter_field()
	if not encounter_field or not api._has_field("Clinical Procedure", "items"):
		return []

	procedures = frappe.get_all(
		"Clinical Procedure",
		filters={encounter_field: encounter, "docstatus": ["!=", 2]},
		fields=["name", "procedure_template", "creation"],
		order_by="creation asc",
		limit=0,
	)
	marked = _procedures_with_marks([procedure.name for procedure in procedures])
	procedures = [procedure for procedure in procedures if procedure.name not in marked]
	if not procedures:
		return []
	rows = _rows_by_parent([procedure.name for procedure in procedures], "Clinical Procedure")
	return _build_groups(procedures, rows)


def _procedures_with_marks(names: list[str]) -> set[str]:
	from do_derma import api

	if not names or not api._has_doctype("Derma Chart Mark"):
		return set()
	return set(
		frappe.get_all(
			"Derma Chart Mark",
			filters={"clinical_procedure": ["in", names]},
			pluck="clinical_procedure",
			limit=0,
		)
	)


def _rows_by_parent(names: list[str], parenttype: str) -> dict[str, list[dict[str, Any]]]:
	rows = frappe.get_all(
		"Clinical Procedure Item",
		filters={"parent": ["in", names], "parenttype": parenttype},
		fields=["parent", *PRINTED_ROW_FIELDS],
		order_by="parent asc, idx asc",
		limit=0,
	)
	by_parent: dict[str, list[dict[str, Any]]] = {}
	for row in rows:
		by_parent.setdefault(row.get("parent"), []).extend(select_fields([row], PRINTED_ROW_FIELDS))
	return by_parent


def _build_groups(owners: list, rows_by_parent: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
	"""One group per owner that consumed something, each carrying when it happened."""
	titles = _procedure_titles({owner.procedure_template for owner in owners if owner.procedure_template})
	groups = []
	for owner in owners:
		lines = rows_by_parent.get(owner.name)
		if not lines:
			continue
		template = owner.procedure_template or ""
		groups.append(
			{
				"creation": owner.creation,
				"group": {"procedure": titles.get(template) or template or _("Procedure"), "rows": lines},
			}
		)
	return groups


def _procedure_titles(templates: set[str]) -> dict[str, str]:
	if not templates:
		return {}
	rows = frappe.get_all(
		"Clinical Procedure Template",
		filters={"name": ["in", list(templates)]},
		fields=["name", "template"],
		limit=0,
	)
	return {row.name: row.template for row in rows}
