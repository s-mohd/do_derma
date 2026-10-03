from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import date_diff, flt, formatdate, getdate, nowdate

from do_derma import api


def get_available_qty(item_code: str | None, batch_no: str | None, warehouse: str | None) -> float | None:
	"""What is left of the lot, or of the item when it has no batch, where the line consumes."""
	if not item_code:
		return None
	if batch_no:
		if not api._has_doctype("Batch"):
			return None
		from erpnext.stock.doctype.batch.batch import get_batch_qty

		if warehouse:
			return flt(get_batch_qty(batch_no=batch_no, warehouse=warehouse))
		return flt(sum(flt(row.get("qty")) for row in get_batch_qty(batch_no=batch_no) or []))
	if not api._has_doctype("Bin"):
		return None
	filters = {"item_code": item_code, **({"warehouse": warehouse} if warehouse else {})}
	rows = frappe.get_all("Bin", filters=filters, pluck="actual_qty")
	return flt(sum(flt(qty) for qty in rows)) if rows else None


def get_batch_facts(
	item_code: str | None,
	batch_no: str | None,
	warehouse: str | None,
	line_qty: float | None,
	window_days: int,
	expiry_date: Any = None,
	today: Any = None,
) -> dict[str, Any]:
	"""Lot, stock left and expiry for one line, judged against the expiring-soon window."""
	if batch_no and api._has_doctype("Batch"):
		expiry_date = frappe.db.get_value("Batch", batch_no, "expiry_date") or expiry_date
	days = date_diff(getdate(expiry_date), getdate(today or nowdate())) if expiry_date else None
	available = get_available_qty(item_code, batch_no, warehouse)
	return {
		"name": batch_no or "",
		"expiry_date": str(expiry_date) if expiry_date else "",
		"available_qty": available,
		"line_qty": line_qty,
		"is_expired": days is not None and days < 0,
		"days_to_expiry": days,
		"is_expiring_soon": days is not None and 0 <= days <= window_days and window_days > 0,
		"is_short": available is not None and line_qty is not None and flt(line_qty) > flt(available),
	}


def get_line_notices(facts: dict[str, Any]) -> list[dict[str, str]]:
	"""What the line says about its lot, the expired notice first."""
	notices = []
	expiry = formatdate(facts["expiry_date"]) if facts.get("expiry_date") else ""
	if facts.get("is_expired"):
		notices.append({"message": _("Product is expired."), "tone": "danger"})
	elif facts.get("is_expiring_soon"):
		days = facts["days_to_expiry"]
		message = (
			_("Expires today ({0}).").format(expiry)
			if days == 0
			else _("Expires in {0} days ({1}).").format(days, expiry)
		)
		notices.append({"message": message, "tone": "caution"})
	if facts.get("is_short"):
		left, needed = _quantity(facts["available_qty"]), _quantity(facts["line_qty"])
		message = (
			_("This lot has {0} left; the line uses {1}.").format(left, needed)
			if facts.get("name")
			else _("{0} left in stock; the line uses {1}.").format(left, needed)
		)
		notices.append({"message": message, "tone": "caution"})
	return notices


def _quantity(value: Any) -> str:
	number = flt(value)
	return str(int(number)) if number == int(number) else f"{number:g}"
