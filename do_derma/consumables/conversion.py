"""How many stock units one consumable row's unit is worth."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def get_factor(item_code: str | None, uom: str | None, stock_uom: str | None) -> float:
	"""The item master's own factor, zero when the item cannot convert that unit.

	Only the item master is trusted: a stored row can name a unit the item never converted,
	and taking its word would move stock at the wrong ratio.
	"""
	if not uom or uom == stock_uom:
		return 1.0
	if not item_code:
		return 0.0
	return flt(
		frappe.db.get_value(
			"UOM Conversion Detail",
			{"parent": item_code, "parenttype": "Item", "uom": uom},
			"conversion_factor",
		)
	)


def ensure_convertible(item_code: str | None, uom: str | None, factor: float) -> None:
	"""Refuse a row whose unit has no conversion, rather than letting stock move at zero."""
	if flt(factor):
		return
	frappe.throw(
		_("{0} is recorded in {1}, which does not convert to its stock unit.").format(item_code, uom)
	)
