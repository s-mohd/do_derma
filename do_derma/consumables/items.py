"""What the chart needs in hand before it can add one consumable line."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

ITEM_FIELDS = ["item_name", "stock_uom", "has_batch_no"]


def get_options(item_code: str, owner_doctype: str | None = None, owner_name: str | None = None) -> dict:
	"""One item's units and pickable batches, so the add row can refuse a bad line itself."""
	item = frappe.db.get_value("Item", item_code, ITEM_FIELDS, as_dict=True)
	if not item:
		frappe.throw(_("Item {0} does not exist.").format(item_code))

	return {
		"item_code": item_code,
		"item_name": item.item_name,
		"stock_uom": item.stock_uom,
		"has_batch_no": bool(item.has_batch_no),
		"uoms": get_uoms(item_code, item.stock_uom),
		"batches": get_batches(item_code, get_warehouse(owner_doctype, owner_name))
		if item.has_batch_no
		else [],
	}


def get_uoms(item_code: str, stock_uom: str | None) -> list[str]:
	"""The stock unit and every unit the item converts from, in that order."""
	rows = frappe.get_all(
		"UOM Conversion Detail",
		filters={"parent": item_code, "parenttype": "Item"},
		fields=["uom", "conversion_factor"],
		order_by="idx asc",
		limit=0,
	)
	converted = [row.uom for row in rows if row.uom != stock_uom and flt(row.conversion_factor)]
	return [uom for uom in [stock_uom, *converted] if uom]


def get_batches(item_code: str, warehouse: str | None) -> list[dict[str, Any]]:
	"""Batches with stock left, newest expiry last, expired ones already dropped by ERPNext."""
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	quantities: dict[str, float] = {}
	for row in get_batch_qty(item_code=item_code, warehouse=warehouse) or []:
		batch_no = row.get("batch_no")
		if batch_no:
			quantities[batch_no] = quantities.get(batch_no, 0) + flt(row.get("qty"))

	available = {batch_no: qty for batch_no, qty in quantities.items() if qty > 0}
	if not available:
		return []

	rows = frappe.get_all(
		"Batch",
		filters={"name": ["in", list(available)]},
		fields=["name", "expiry_date"],
		limit=0,
	)
	rows = [{**row, "qty": available[row.name]} for row in rows]
	return sorted(rows, key=lambda row: (row.get("expiry_date") is None, row.get("expiry_date")))


def get_warehouse(owner_doctype: str | None, owner_name: str | None) -> str | None:
	"""The warehouse the owner will consume from, empty when the site never set one."""
	from do_derma import api

	if not owner_doctype or not owner_name:
		return None
	procedure = owner_name
	if owner_doctype == "Derma Chart Mark":
		procedure = frappe.db.get_value("Derma Chart Mark", owner_name, "clinical_procedure")
	if not procedure or not api._has_field("Clinical Procedure", "warehouse"):
		return None
	return frappe.db.get_value("Clinical Procedure", procedure, "warehouse")
