"""The consumable rows a Clinical Procedure Template offers a mark."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt

from do_derma import api

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
	return api._has_doctype("Clinical Procedure Template") and api._has_doctype("Clinical Procedure Item")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
	"""One row reduced to the fields do_derma carries, with quantities as numbers."""
	normalized = {field: row.get(field) for field in CONSUMABLE_FIELDS}
	normalized["qty"] = flt(row.get("qty"))
	normalized["conversion_factor"] = flt(row.get("conversion_factor")) or 1.0
	return normalized
