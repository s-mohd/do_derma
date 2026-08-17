"""What each mark still owes after the visit: review, photo, product, next session."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, nowdate

from do_derma import api
from do_derma.readiness.templates import templates_for_marks

SOURCE = "followup"
STATUS_DUE_DAYS = {"Worse": 7, "Biopsied": 3, "Excised": 14, "Monitoring": 30}
STATUS_BLOCKING = {"Worse", "Biopsied"}
NEXT_SESSION_INTERVALS = {"Botox": 90, "Filler": 180, "Laser": 28}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
TEMPLATE_FIELDS = [
	"name",
	"template",
	"custom_derma_category",
	"custom_derma_before_after_photo_required",
	"custom_derma_product_tracking_required",
	"custom_derma_device_settings_required",
]


def build(marks: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Every follow-up item for these marks, most urgent and soonest due first."""
	if not marks:
		return []

	templates = templates_for_marks(marks, TEMPLATE_FIELDS)
	open_todos = open_todos_for_marks([mark.get("name") for mark in marks if mark.get("name")])
	items: list[dict[str, Any]] = []
	for mark in marks:
		template = templates.get(mark.get("procedure_template")) or {}
		items.extend(_items_for_mark(mark, template, open_todos.get(mark.get("name"))))

	items.sort(key=lambda row: (SEVERITY_ORDER.get(row.get("severity"), 3), row.get("due_date") or ""))
	return items


def _items_for_mark(mark: dict[str, Any], template: dict[str, Any], todo: str | None) -> list[dict[str, Any]]:
	category = mark.get("category") or template.get("custom_derma_category") or _("Derma")
	location = api._meaningful_location(mark) or mark.get("body_view") or _("charted area")
	status = mark.get("status") or "Active"
	base = {
		"mark": mark.get("name"),
		"category": category,
		"location": location,
		"clinical_procedure": mark.get("clinical_procedure"),
		"todo": todo,
	}

	items: list[dict[str, Any]] = []
	if status in STATUS_DUE_DAYS:
		items.append(
			{
				**base,
				"key": f"{mark.get('name')}-status",
				"type": "Pathology" if status == "Biopsied" else "Review",
				"severity": "high" if status in STATUS_BLOCKING else "medium",
				"title": _("{0} follow-up").format(status),
				"detail": ", ".join(
					value for value in [mark.get("diagnosis") or category, location] if value
				),
				"due_date": add_days(nowdate(), STATUS_DUE_DAYS[status]),
				"blocking": status in STATUS_BLOCKING,
			}
		)

	if template.get("custom_derma_before_after_photo_required") and not mark.get("photo_set"):
		items.append(
			{
				**base,
				"key": f"{mark.get('name')}-photo",
				"type": "Photo",
				"severity": "medium",
				"title": _("Photo evidence needed"),
				"detail": _("Capture or link before/after photos for {0}.").format(location),
				"due_date": nowdate(),
				"blocking": True,
			}
		)

	if template.get("custom_derma_product_tracking_required") and (
		not mark.get("product_name") or not mark.get("lot_no")
	):
		items.append(
			{
				**base,
				"key": f"{mark.get('name')}-inventory",
				"type": "Inventory",
				"severity": "high",
				"title": _("Product / lot missing"),
				"detail": _("Product and lot are required for {0}.").format(category),
				"due_date": nowdate(),
				"blocking": True,
			}
		)

	if category in NEXT_SESSION_INTERVALS and mark.get("clinical_procedure"):
		items.append(
			{
				**base,
				"key": f"{mark.get('name')}-next-session",
				"type": "Next Session",
				"severity": "low",
				"title": _("{0} next session due").format(category),
				"detail": _("Plan next {0} review for {1}.").format(category, location),
				"due_date": add_days(nowdate(), NEXT_SESSION_INTERVALS[category]),
				"blocking": False,
			}
		)
	return items


def open_todos_for_marks(mark_names: list[str]) -> dict[str, str]:
	"""The open ToDo per mark, which is what downgrades a blocker."""
	mark_names = [name for name in mark_names if name]
	if not mark_names or not frappe.db.exists("DocType", "ToDo"):
		return {}
	rows = frappe.get_all(
		"ToDo",
		filters={
			"reference_type": "Derma Chart Mark",
			"reference_name": ["in", mark_names],
			"status": ["!=", "Closed"],
		},
		fields=api._select_existing_fields("ToDo", ["name", "reference_type", "reference_name", "status"]),
		limit=200,
	)
	return {row.get("reference_name"): row.get("name") for row in rows if row.get("reference_name")}
