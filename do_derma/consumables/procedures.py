"""A Clinical Procedure's own consumables, for the procedures no annotation covers."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from do_derma.consumables import snapshot
from do_derma.consumables.defaults import CONSUMABLE_FIELDS, get_template_consumables, select_fields


def hydrate(procedure_rows: list[dict[str, Any]]) -> None:
	"""Attach the consumables a markless procedure owns, judged against its template.

	A procedure with annotations is left alone: its marks own that list, and hydrating both
	would put the same rows on screen twice under two owners.
	"""
	if not procedure_rows or not is_available():
		return
	rows = [row for row in procedure_rows if row.get("name") and not row.get("derma_marks")]
	if not rows:
		return

	live = _live_rows([row["name"] for row in rows])
	defaults_by_template: dict[str, list[dict[str, Any]]] = {}
	for row in rows:
		template = row.get("procedure_template") or ""
		if template not in defaults_by_template:
			defaults_by_template[template] = get_template_consumables(template)
		defaults = defaults_by_template[template]
		compared = snapshot.compare(live.get(row["name"], []), defaults)
		row["consumables"] = compared["consumables"]
		row["removed_consumables"] = compared["removed"]
		row["default_consumables"] = defaults


def get_payload(procedure_doc) -> dict[str, Any]:
	"""The shape the chart reads and a save answers with, so the panel can swap state."""
	defaults = get_template_consumables(procedure_doc.procedure_template)
	compared = snapshot.compare(select_fields(procedure_doc.get("items")), defaults)
	return {
		"owner_doctype": "Clinical Procedure",
		"owner_name": procedure_doc.name,
		"consumables": compared["consumables"],
		"removed_consumables": compared["removed"],
		"default_consumables": defaults,
	}


def save(procedure_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
	"""Replace the procedure's own list outright and answer what the chart should show."""
	from do_derma import api

	procedure_doc = frappe.get_doc("Clinical Procedure", procedure_name)
	_ensure_editable(procedure_doc)
	procedure_doc.set("items", rows)
	if rows and api._has_field("Clinical Procedure", "consume_stock"):
		procedure_doc.consume_stock = 1
	procedure_doc.save(ignore_permissions=True)
	return get_payload(procedure_doc)


def get_carriers(procedure_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Hydrated rows reduced to what readiness needs: who consumed, and what."""
	return [
		{"name": row.get("name"), "consumables": row.get("consumables")}
		for row in procedure_rows
		if row.get("consumables")
	]


def is_available() -> bool:
	from do_derma import api

	return api._has_doctype("Clinical Procedure Item") and api._has_field("Clinical Procedure", "items")


def _ensure_editable(procedure_doc) -> None:
	from do_derma import api

	if cint(procedure_doc.docstatus) != 0:
		frappe.throw(_("This procedure is completed and its materials can no longer be edited."))
	if frappe.db.exists("Derma Chart Mark", {"clinical_procedure": procedure_doc.name}):
		frappe.throw(_("This procedure records its materials on its annotations."))
	encounter_field = api._get_clinical_procedure_encounter_field()
	if encounter_field:
		api._ensure_encounter_open(procedure_doc.get(encounter_field))


def _live_rows(names: list[str]) -> dict[str, list[dict[str, Any]]]:
	rows = frappe.get_all(
		"Clinical Procedure Item",
		filters={"parent": ["in", names], "parenttype": "Clinical Procedure"},
		fields=["parent", *CONSUMABLE_FIELDS],
		order_by="parent asc, idx asc",
		# Unpaged for the same reason area variables are: the caller caps the parents.
		limit=0,
	)
	by_parent: dict[str, list[dict[str, Any]]] = {}
	for row in rows:
		by_parent.setdefault(row.get("parent"), []).extend(select_fields([row]))
	return by_parent
