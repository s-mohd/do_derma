"""Product, lot, expiry and stock readiness for the marks in one session."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from do_derma import api
from do_derma.readiness.templates import templates_for_marks

SOURCE = "inventory"
# Retiring in favour of `custom_derma_product_tracking_required` alone: readiness must not
# depend on how a clinic named its categories.
TRACKED_CATEGORIES = {"Botox", "Filler"}
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
	"""The marks that consume product, gathered by what they consume."""
	templates = templates_for_marks(marks, TEMPLATE_FIELDS)
	grouped: dict[str, dict[str, Any]] = {}
	for mark in marks:
		template = templates.get(mark.get("procedure_template")) or {}
		category = mark.get("category") or template.get("custom_derma_category")
		requires_tracking = (
			bool(template.get("custom_derma_product_tracking_required")) or category in TRACKED_CATEGORIES
		)
		if not requires_tracking and not any(mark.get(field) for field in PRODUCT_FIELDS):
			continue

		key, group = _new_group(mark, template, category)
		row = grouped.setdefault(key, group)
		row["dose"] += flt(mark.get("dose") or 0)
		row["marks"].append(mark.get("name"))
		if not row.get("product_item") and group["product_item"]:
			row["product_item"] = group["product_item"]
	return list(grouped.values())


def _new_group(
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
	lot_no = mark.get("lot_no") or ""
	expiry_date = mark.get("expiry_date") or ""
	dose_unit = mark.get("dose_unit") or ""
	key = "|".join([product_item or product_name or _("Missing product"), lot_no, expiry_date, dose_unit])
	return key, {
		"key": key,
		"product_item": product_item,
		"product_name": product_name,
		"lot_no": lot_no,
		"expiry_date": expiry_date,
		"dose": 0,
		"dose_unit": dose_unit,
		"available_qty": None,
		"status": "ready",
		"severity": "low",
		"blocking": False,
		"marks": [],
		"message": "",
	}


def _resolve_row_status(row: dict[str, Any]) -> dict[str, Any]:
	"""The same row, saying what is missing and whether that blocks."""
	messages = []
	blocking = False
	if not row.get("product_item") and not row.get("product_name"):
		messages.append(_("Product is missing."))
		blocking = True
	if not row.get("dose"):
		messages.append(_("Dose/quantity is missing."))
		blocking = True
	if not row.get("lot_no"):
		messages.append(_("Lot number is missing."))
		blocking = True
	if not row.get("expiry_date"):
		messages.append(_("Expiry date is missing."))
		blocking = True
	elif _is_expired(row.get("expiry_date")):
		messages.append(_("Product is expired."))
		blocking = True

	available_qty = _stock_available_qty(row.get("product_item"))
	if available_qty is not None and row.get("dose") and available_qty < flt(row.get("dose")):
		messages.append(_("Insufficient available stock."))
		blocking = True
	elif row.get("product_item") and available_qty is None:
		messages.append(_("Stock balance is not available for this item."))

	return {
		**row,
		"available_qty": available_qty,
		"blocking": blocking,
		"status": "blocked" if blocking else ("warning" if messages else "ready"),
		"severity": "high" if blocking else ("medium" if messages else "low"),
		"message": " ".join(messages) if messages else _("Ready for product consumption review."),
	}


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
