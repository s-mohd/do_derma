"""Consumable rows arriving from the chart, checked before anything is written."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

ITEM_FIELDS = ["item_name", "stock_uom", "has_batch_no"]


def clean_rows(rows: Any) -> list[dict[str, Any]]:
	"""The rows as they will be stored, or a throw naming the first row that is wrong."""
	if not isinstance(rows, list):
		frappe.throw(_("Consumables must be sent as a list of rows."))
	return [clean_row(row) for row in rows]


def clean_row(row: Any) -> dict[str, Any]:
	if not isinstance(row, dict):
		frappe.throw(_("Consumables must be sent as a list of rows."))

	item_code = (row.get("item_code") or "").strip()
	if not item_code:
		frappe.throw(_("Every consumable line needs an item."))
	item = frappe.db.get_value("Item", item_code, ITEM_FIELDS, as_dict=True)
	if not item:
		frappe.throw(_("Item {0} does not exist.").format(item_code))

	quantity = flt(row.get("qty"))
	if quantity <= 0:
		frappe.throw(_("Quantity for {0} must be greater than zero.").format(item_code))

	uom = (row.get("uom") or "").strip() or item.stock_uom
	return {
		"item_code": item_code,
		"item_name": item.item_name,
		"qty": quantity,
		"uom": uom,
		"conversion_factor": validated_conversion_factor(item_code, uom, item.stock_uom),
		"stock_uom": item.stock_uom,
		# A batch-tracked item without a batch is saved and reported as a blocker, so the
		# line the clinician typed survives while they go and find the box.
		"batch_no": _validated_batch(item_code, (row.get("batch_no") or "").strip()),
	}


def is_batch_missing(row: dict[str, Any]) -> bool:
	"""Whether this row names an item that cannot leave stock without a batch."""
	if row.get("batch_no"):
		return False
	return bool(frappe.db.get_value("Item", row.get("item_code"), "has_batch_no"))


def _validated_batch(item_code: str, batch_no: str) -> str | None:
	if not batch_no:
		return None
	batch_item = frappe.db.get_value("Batch", batch_no, "item")
	if not batch_item:
		frappe.throw(_("Batch {0} does not exist.").format(batch_no))
	if batch_item != item_code:
		frappe.throw(_("Batch {0} does not belong to item {1}.").format(batch_no, item_code))
	return batch_no


def validated_conversion_factor(item_code: str, uom: str | None, stock_uom: str | None) -> float:
	"""How many stock units one row unit is worth, refused when the item cannot convert."""
	if not uom or uom == stock_uom:
		return 1.0
	factor = flt(
		frappe.db.get_value(
			"UOM Conversion Detail",
			{"parent": item_code, "parenttype": "Item", "uom": uom},
			"conversion_factor",
		)
	)
	if not factor:
		# Stock would move at zero, so the unit is refused here rather than at completion.
		frappe.throw(
			_("{0} is recorded in {1}, which does not convert to its stock unit.").format(item_code, uom)
		)
	return factor
