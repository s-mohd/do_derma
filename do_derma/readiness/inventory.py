"""Product, lot, expiry and stock readiness for the marks in one session."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from do_derma import api
from do_derma.readiness.templates import templates_for_marks

SOURCE = "inventory"
# What produced a row's quantity, so the chart can point the clinician at the field to fix.
DOSE_CONTRIBUTOR = "dose"
CONSUMABLE_CONTRIBUTOR = "consumable"
PRODUCT_FIELDS = ["product_item", "product_name", "dose", "dose_unit", "lot_no", "expiry_date"]
TEMPLATE_FIELDS = [
	"name",
	"template",
	"item",
	"custom_derma_category",
	"custom_derma_product_tracking_required",
]


def build(marks: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""One row per product/lot/expiry/unit group, each saying whether it blocks."""
	if not marks:
		return []

	rows = [_resolve_row_status(row) for row in _group_marks(marks)]
	return sorted(rows, key=lambda row: (row["blocking"] is False, row.get("product_name") or ""))


def _group_marks(marks: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""The marks that consume product, gathered by what they consume.

	A dose field and a consumable row for the same item and stock identity are one
	demand on the clinic, so they land in one group and their quantities add.
	"""
	templates = templates_for_marks(marks, TEMPLATE_FIELDS)
	grouped: dict[str, dict[str, Any]] = {}
	for mark in marks:
		_add_dose(grouped, mark, templates.get(mark.get("procedure_template")) or {})
		for consumable in mark.get("consumables") or []:
			_add_consumable(grouped, mark, consumable)
	return list(grouped.values())


def _add_dose(grouped: dict[str, dict[str, Any]], mark: dict[str, Any], template: dict[str, Any]) -> None:
	category = mark.get("category") or template.get("custom_derma_category")
	requires_tracking = bool(template.get("custom_derma_product_tracking_required"))
	if not requires_tracking and not any(mark.get(field) for field in PRODUCT_FIELDS):
		return

	key, group = _new_dose_group(mark, template, category)
	row = grouped.setdefault(key, group)
	quantity = flt(mark.get("dose") or 0)
	row["dose"] += quantity
	row["stock_qty"] += quantity
	# A dose row identifies its stock by free-text lot and expiry, so it can never say
	# the identity was not required.
	row["is_lot_required"] = True
	_record_contribution(row, mark, DOSE_CONTRIBUTOR)
	if not row.get("product_item") and group["product_item"]:
		row["product_item"] = group["product_item"]


def _add_consumable(
	grouped: dict[str, dict[str, Any]], mark: dict[str, Any], consumable: dict[str, Any]
) -> None:
	item_code = consumable.get("item_code")
	if not item_code:
		return

	key, group = _new_consumable_group(consumable)
	row = grouped.setdefault(key, group)
	quantity = flt(consumable.get("qty"))
	row["dose"] += quantity
	factor = flt(consumable.get("conversion_factor"))
	if factor:
		row["stock_qty"] += quantity * factor
	else:
		# Recorded in a unit the item does not convert: the balance cannot be compared.
		row["is_stock_qty_known"] = False
	_record_contribution(row, mark, CONSUMABLE_CONTRIBUTOR)


def _record_contribution(row: dict[str, Any], mark: dict[str, Any], contributor: str) -> None:
	if contributor not in row["contributors"]:
		row["contributors"].append(contributor)
	if mark.get("name") and mark.get("name") not in row["marks"]:
		row["marks"].append(mark.get("name"))


def _new_dose_group(
	mark: dict[str, Any], template: dict[str, Any], category: str | None
) -> tuple[str, dict[str, Any]]:
	product_item = (
		mark.get("product_item") or template.get("item") or _find_item_for_product(mark.get("product_name"))
	)
	product_name = (
		mark.get("product_name")
		or _item_display_name(product_item)
		or template.get("template")
		or category
		or _("Product")
	)
	return _new_group(
		identity=product_item or product_name or _("Missing product"),
		product_item=product_item,
		product_name=product_name,
		lot_no=mark.get("lot_no") or "",
		expiry_date=mark.get("expiry_date") or "",
		dose_unit=mark.get("dose_unit") or "",
	)


def _new_consumable_group(consumable: dict[str, Any]) -> tuple[str, dict[str, Any]]:
	item_code = consumable.get("item_code")
	batch_no = consumable.get("batch_no") or ""
	return _new_group(
		identity=item_code,
		product_item=item_code,
		product_name=consumable.get("item_name") or _item_display_name(item_code) or item_code,
		lot_no=batch_no,
		expiry_date=_batch_expiry(batch_no) or "",
		dose_unit=consumable.get("uom") or "",
		is_lot_required=_is_batch_tracked(item_code),
	)


def _new_group(
	identity: str,
	product_item: str | None,
	product_name: str | None,
	lot_no: str,
	expiry_date: Any,
	dose_unit: str,
	is_lot_required: bool = False,
) -> tuple[str, dict[str, Any]]:
	key = "|".join([str(identity), str(lot_no), str(expiry_date), str(dose_unit)])
	return key, {
		"key": key,
		"product_item": product_item,
		"product_name": product_name,
		"lot_no": lot_no,
		"expiry_date": expiry_date,
		"dose": 0,
		"stock_qty": 0,
		"dose_unit": dose_unit,
		"available_qty": None,
		"status": "ready",
		"severity": "low",
		"blocking": False,
		"is_lot_required": is_lot_required,
		"is_stock_qty_known": True,
		"contributors": [],
		"marks": [],
		"message": "",
	}


def _resolve_row_status(row: dict[str, Any]) -> dict[str, Any]:
	"""The same row, saying what is missing and whether that blocks."""
	available_qty = _stock_available_qty(row.get("product_item"))
	blockers = _blocking_messages(row, available_qty)
	messages = blockers + _balance_notices(row, available_qty)
	return {
		**row,
		"available_qty": available_qty,
		"blocking": bool(blockers),
		"status": "blocked" if blockers else ("warning" if messages else "ready"),
		"severity": "high" if blockers else ("medium" if messages else "low"),
		"message": " ".join(messages) if messages else _("Ready for product consumption review."),
	}


def _blocking_messages(row: dict[str, Any], available_qty: float | None) -> list[str]:
	messages = []
	if not row.get("product_item") and not row.get("product_name"):
		messages.append(_("Product is missing."))
	if not row.get("dose"):
		messages.append(_("Dose/quantity is missing."))
	messages.extend(_identity_messages(row))
	if _is_balance_comparable(row, available_qty) and available_qty < flt(row.get("stock_qty")):
		messages.append(_("Insufficient available stock."))
	return messages


def _identity_messages(row: dict[str, Any]) -> list[str]:
	"""Lot and expiry, asked of every dose row and of a consumable row whose item is
	tracked by batch."""
	messages = []
	if row.get("is_lot_required") and not row.get("lot_no"):
		is_dose = DOSE_CONTRIBUTOR in row["contributors"]
		messages.append(_("Lot number is missing.") if is_dose else _("Batch is missing."))
	if _is_expired(row.get("expiry_date")):
		messages.append(_("Product is expired."))
	elif row.get("is_lot_required") and not row.get("expiry_date"):
		messages.append(_("Expiry date is missing."))
	return messages


def _balance_notices(row: dict[str, Any], available_qty: float | None) -> list[str]:
	unavailable = _("Stock balance is not available for this item.")
	if not row.get("is_stock_qty_known"):
		return [unavailable]
	if row.get("product_item") and available_qty is None:
		return [unavailable]
	return []


def _is_balance_comparable(row: dict[str, Any], available_qty: float | None) -> bool:
	return bool(row.get("is_stock_qty_known")) and available_qty is not None and bool(row.get("stock_qty"))


def _batch_expiry(batch_no: str) -> Any:
	if not batch_no or not api._has_doctype("Batch"):
		return None
	return frappe.db.get_value("Batch", batch_no, "expiry_date")


def _is_batch_tracked(item_code: str | None) -> bool:
	if not item_code or not api._has_doctype("Item"):
		return False
	return bool(frappe.db.get_value("Item", item_code, "has_batch_no"))


def _find_item_for_product(product_name: str | None) -> str | None:
	if not product_name or not api._has_doctype("Item"):
		return None
	if frappe.db.exists("Item", product_name):
		return product_name
	return frappe.db.get_value("Item", {"item_name": product_name}, "name") or frappe.db.get_value(
		"Item", {"item_code": product_name}, "name"
	)


def _item_display_name(item_code: str | None) -> str | None:
	if not item_code or not api._has_doctype("Item"):
		return None
	return frappe.db.get_value("Item", item_code, "item_name") or item_code


def _stock_available_qty(item_code: str | None) -> float | None:
	if not item_code or not api._has_doctype("Bin"):
		return None
	result = frappe.db.sql("select sum(actual_qty) from `tabBin` where item_code=%s", (item_code,))
	if not result:
		return None
	value = result[0][0]
	return flt(value) if value is not None else None


def _is_expired(expiry_date: str | None) -> bool:
	if not expiry_date:
		return False
	try:
		return getdate(expiry_date) < getdate(nowdate())
	except Exception:
		return False
