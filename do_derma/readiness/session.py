"""One owner for how ready a session is. Every engine is read from here."""

from __future__ import annotations

from typing import Any

from frappe import _

from do_derma import api
from do_derma.readiness import followup, inventory
from do_derma.settings import get_readiness_settings


def get_session_readiness(
	patient: str | None, appointment: str | None = None, encounter: str | None = None
) -> dict[str, Any]:
	"""Every readiness item for one session, plus what completion should do about them."""
	settings = get_readiness_settings()
	marks = api._get_marks(patient, appointment=appointment, encounter=encounter) if patient else []
	items = [
		*[_as_item(row, inventory.SOURCE) for row in inventory.build(marks)],
		*[_as_item(row, followup.SOURCE) for row in followup.build(marks)],
	]
	if settings["todo_downgrades_blockers"]:
		items = [_downgrade_if_todo(item) for item in items]

	return {
		"items": items,
		"blockers": [item for item in items if item.get("blocking")],
		"enforcement": settings["enforcement"],
	}


def _as_item(row: dict[str, Any], source: str) -> dict[str, Any]:
	"""The two engines describe an item differently; a caller reads one shape."""
	return {
		**row,
		"source": source,
		"title": row.get("title") or row.get("product_name") or _("Readiness"),
		"detail": row.get("detail") or row.get("message") or "",
	}


def _downgrade_if_todo(item: dict[str, Any]) -> dict[str, Any]:
	"""An item someone has already booked work for warns instead of blocking - the rule the
	chart used to apply silently, in the browser only."""
	if not item.get("blocking") or not item.get("todo"):
		return item
	return {**item, "blocking": False, "severity": "medium", "downgraded_by_todo": True}
