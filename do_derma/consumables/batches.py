from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import date_diff, flt, formatdate, getdate, nowdate
from frappe.utils.caching import request_cache

from do_derma import api


@request_cache
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
	expiry_date = get_batch_expiry(batch_no) or expiry_date
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


@request_cache
def get_batch_expiry(batch_no: str | None) -> Any:
	if not batch_no or not api._has_doctype("Batch"):
		return None
	return frappe.db.get_value("Batch", batch_no, "expiry_date")


def get_past_facts(batch_no: str | None, line_qty: float | None) -> dict[str, Any]:
	"""A consumed line's lot and expiry, with no claim about stock or expiry today."""
	expiry_date = get_batch_expiry(batch_no)
	return {
		"name": batch_no or "",
		"expiry_date": str(expiry_date) if expiry_date else "",
		"available_qty": None,
		"line_qty": line_qty,
		"is_expired": False,
		"days_to_expiry": None,
		"is_expiring_soon": False,
		"is_short": False,
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
		message = (_("This lot has {0} left;") if facts.get("name") else _("{0} left in stock;")).format(left)
		uses = _("these lines use {0}.") if facts.get("line_count", 1) > 1 else _("the line uses {0}.")
		message = f"{message} {uses.format(needed)}"
		notices.append({"message": message, "tone": "caution"})
	return notices


def _quantity(value: Any) -> str:
	number = flt(value)
	return str(int(number)) if number == int(number) else f"{number:g}"


def annotate_rows(
	rows: list[dict[str, Any]],
	owner_doctype: str,
	owner_name: str | None,
	window_days: int,
	is_current: bool = True,
) -> None:
	"""Attach each line's lot facts and its worst notice, the shape the editor renders.

	Lines on the same item and lot are compared together, as readiness does. A past line
	(a submitted procedure, an earlier visit) keeps its lot but claims nothing about today.
	Lots shared across owners in one session are summed by readiness only.
	"""
	from do_derma.consumables.items import get_warehouse

	warehouse = get_warehouse(owner_doctype, owner_name) if is_current else None
	totals = get_lot_totals(rows)
	for row in rows or []:
		if not row.get("item_code"):
			row.update(batch=None, readiness_message="", readiness_tone="")
			continue
		key = (row["item_code"], row.get("batch_no") or None)
		line_qty, line_count = totals[key]
		if not is_current:
			row.update(batch=get_past_facts(key[1], line_qty), readiness_message="", readiness_tone="")
			continue
		facts = {
			**get_batch_facts(key[0], key[1], warehouse, line_qty, window_days),
			"line_count": line_count,
		}
		notices = get_line_notices(facts)
		tones = {notice["tone"] for notice in notices}
		row["batch"] = facts
		row["readiness_message"] = " ".join(notice["message"] for notice in notices)
		row["readiness_tone"] = "danger" if "danger" in tones else ("caution" if tones else "")


def get_lot_totals(rows: list[dict[str, Any]]) -> dict[tuple, tuple[float | None, int]]:
	"""Stock quantity and line count per (item, lot); unknown when any line cannot convert."""
	totals: dict[tuple, list] = {}
	for row in rows or []:
		if not row.get("item_code"):
			continue
		key = (row["item_code"], row.get("batch_no") or None)
		total = totals.setdefault(key, [0.0, 0])
		factor = flt(row.get("conversion_factor"))
		total[0] = total[0] + flt(row.get("qty")) * factor if factor and total[0] is not None else None
		total[1] += 1
	return {key: (value[0], value[1]) for key, value in totals.items()}
