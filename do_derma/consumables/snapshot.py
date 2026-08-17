"""The frozen copy of a template's consumables, and what the live list did to it."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from do_derma.consumables.defaults import normalize_row

# What makes a live row a deviation from the default it came from.
COMPARED_FIELDS = ["qty", "uom", "batch_no"]


def dump(rows: list[dict[str, Any]]) -> str:
	return json.dumps([normalize_row(row) for row in rows], ensure_ascii=False)


def load(value: str | None) -> list[dict[str, Any]]:
	"""The frozen rows, empty for a mark that never had a snapshot written.

	Anything else in the field is this app's own bug, and answering "no defaults" would
	quietly report every live row as overridden and every default as removed.
	"""
	if not value:
		return []
	try:
		rows = json.loads(value)
	except (TypeError, ValueError):
		rows = None
	if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
		frappe.throw(_("The stored template consumables of this mark are unreadable."))
	return [normalize_row(row) for row in rows]


def compare(live_rows: list[dict[str, Any]], frozen_rows: list[dict[str, Any]]) -> dict[str, list]:
	"""Live rows carrying `is_overridden`, plus the frozen rows nothing lives against."""
	claimed: set[int] = set()
	consumables = []
	for row in live_rows:
		matched = _match_index(frozen_rows, claimed, row.get("item_code"))
		if matched is not None:
			claimed.add(matched)
		frozen = frozen_rows[matched] if matched is not None else None
		consumables.append({**row, "is_overridden": _is_overridden(row, frozen)})
	removed = [dict(row) for index, row in enumerate(frozen_rows) if index not in claimed]
	return {"consumables": consumables, "removed": removed}


def _match_index(frozen_rows: list[dict[str, Any]], claimed: set[int], item_code: str | None) -> int | None:
	"""The first unclaimed frozen row for this item, so two live rows of one item cannot
	both claim the same default."""
	for index, row in enumerate(frozen_rows):
		if index not in claimed and row.get("item_code") == item_code:
			return index
	return None


def _is_overridden(row: dict[str, Any], frozen: dict[str, Any] | None) -> bool:
	if frozen is None:
		return True
	return any(_differs(row, frozen, field) for field in COMPARED_FIELDS)


def _differs(row: dict[str, Any], frozen: dict[str, Any], field: str) -> bool:
	if field == "qty":
		return flt(row.get("qty")) != flt(frozen.get("qty"))
	return (row.get(field) or "") != (frozen.get(field) or "")
