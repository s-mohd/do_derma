"""The consumable rows a Clinical Procedure Template offers a mark."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt

from do_derma.consumables import conversion

# The stock fields do_derma owns on a consumable row. `actual_qty` and `transfer_qty` are
# healthcare's to write during stock movement, so they are never copied.
CONSUMABLE_FIELDS = [
	"item_code",
	"item_name",
	"qty",
	"uom",
	"conversion_factor",
	"stock_uom",
	"batch_no",
]


def get_template_consumables(procedure_template: str | None) -> list[dict[str, Any]]:
	"""Plain rows, empty whenever the template has nothing to say about stock."""
	if not procedure_template or not has_consumable_doctypes():
		return []
	if not frappe.db.get_value("Clinical Procedure Template", procedure_template, "consume_stock"):
		return []

	from healthcare.healthcare.doctype.clinical_procedure.clinical_procedure import (
		get_procedure_consumables,
	)

	return [normalize_row(row) for row in get_procedure_consumables(procedure_template)]


def has_consumable_doctypes() -> bool:
	# Imported inside the function, not at module scope: `api` reads this package, and the
	# Derma Chart Mark controller imports this package before `api` has ever been loaded.
	from do_derma import api

	return api._has_doctype("Clinical Procedure Template") and api._has_doctype("Clinical Procedure Item")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
	"""One template row reduced to the fields do_derma carries, judged against the item master.

	The stock unit and conversion factor are read off the item rather than copied: healthcare's
	template grid keeps the 1.0 it wrote when the item was picked even after the unit is changed
	by hand, so a copied factor can silently consume a whole stock unit per row unit.
	"""
	normalized = {field: row.get(field) for field in CONSUMABLE_FIELDS}
	normalized["qty"] = flt(row.get("qty"))
	normalized["stock_uom"] = conversion.get_stock_unit(normalized["item_code"]) or row.get("stock_uom")
	normalized["conversion_factor"] = conversion.get_factor(
		normalized["item_code"], normalized["uom"], normalized["stock_uom"]
	)
	return normalized


def read_stored_row(row: dict[str, Any]) -> dict[str, Any]:
	"""One already-stored row, taken at its word except for the quantity's type.

	A frozen snapshot is a record of what the template said at the time, so nothing here is
	re-derived from today's item master.
	"""
	return {**{field: row.get(field) for field in CONSUMABLE_FIELDS}, "qty": flt(row.get("qty"))}


def select_fields(rows: list[dict[str, Any]], fields: list[str] | None = None) -> list[dict[str, Any]]:
	"""The same rows reduced to the fields named, defaulting to the ones do_derma carries.

	Unlike `normalize_row` this coerces nothing: a stored row's zero conversion factor means
	the unit could not be converted, and readiness and procedure creation both read it.
	"""
	names = fields or CONSUMABLE_FIELDS
	return [{field: row.get(field) for field in names} for row in rows]
