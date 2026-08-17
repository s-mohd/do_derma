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

	batch_no = _validated_batch(item_code, item, (row.get("batch_no") or "").strip())
	uom = (row.get("uom") or "").strip() or item.stock_uom
	return {
		"item_code": item_code,
		"item_name": item.item_name,
		"qty": quantity,
		"uom": uom,
		"conversion_factor": conversion_factor(item_code, uom, item.stock_uom),
		"stock_uom": item.stock_uom,
		"batch_no": batch_no,
	}


def _validated_batch(item_code: str, item: dict[str, Any], batch_no: str) -> str | None:
	if not batch_no:
		if item.get("has_batch_no"):
			frappe.throw(_("Item {0} is tracked by batch, so a batch is required.").format(item_code))
		return None
	batch_item = frappe.db.get_value("Batch", batch_no, "item")
	if not batch_item:
		frappe.throw(_("Batch {0} does not exist.").format(batch_no))
	if batch_item != item_code:
		frappe.throw(_("Batch {0} does not belong to item {1}.").format(batch_no, item_code))
	return batch_no


def conversion_factor(item_code: str, uom: str | None, stock_uom: str | None) -> float:
	"""How many stock units one row unit is worth, or 0 when the item does not say."""
	if not uom or uom == stock_uom:
		return 1.0
	value = frappe.db.get_value(
		"UOM Conversion Detail",
		{"parent": item_code, "parenttype": "Item", "uom": uom},
		"conversion_factor",
	)
	return flt(value)
