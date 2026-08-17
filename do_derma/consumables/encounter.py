"""What each procedure on one encounter consumed."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from do_derma import api
from do_derma.consumables.defaults import has_consumable_doctypes

PRINTED_ROW_FIELDS = ["item_code", "item_name", "qty", "uom", "batch_no"]


def get_encounter_consumables(encounter: str | None) -> list[dict[str, Any]]:
	"""One group per procedure template, in chart order, skipping procedures that
	consumed nothing."""
	if not encounter or not has_consumable_doctypes():
		return []
	if not api._has_doctype("Derma Chart Mark") or not api._has_field("Derma Chart Mark", "consumables"):
		return []

	marks = frappe.get_all(
		"Derma Chart Mark",
		filters={"encounter": encounter, "status": ["!=", "Archived"]},
		fields=["name", "procedure_template"],
		order_by="sequence asc, creation asc",
		limit=0,
	)
	if not marks:
		return []

	rows = frappe.get_all(
		"Clinical Procedure Item",
		filters={"parent": ["in", [mark.name for mark in marks]], "parenttype": "Derma Chart Mark"},
		fields=["parent", *PRINTED_ROW_FIELDS],
		order_by="parent asc, idx asc",
		limit=0,
	)
	by_parent: dict[str, list[dict[str, Any]]] = {}
	for row in rows:
		by_parent.setdefault(row.get("parent"), []).append(
			{field: row.get(field) for field in PRINTED_ROW_FIELDS}
		)
	return _group_by_procedure(marks, by_parent)


def _group_by_procedure(marks: list, by_parent: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
	"""One group per mark, since a mark is what becomes a Clinical Procedure."""
	titles = _procedure_titles({mark.procedure_template for mark in marks if mark.procedure_template})
	groups = []
	for mark in marks:
		lines = by_parent.get(mark.name)
		if not lines:
			continue
		template = mark.procedure_template or ""
		groups.append({"procedure": titles.get(template) or template or _("Procedure"), "rows": lines})
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
