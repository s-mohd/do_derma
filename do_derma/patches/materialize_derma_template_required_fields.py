from __future__ import annotations

import json

import frappe

from do_derma import api

# What `api._category_required_fields` granted a template whose category was named one
# of these, before the template became the sole owner. Seed data for this migration
# only - nothing reads it afterwards.
CATEGORY_NAME_REQUIRED_FIELDS = {
	"botox": ["product_name", "dose", "dose_unit", "lot_no", "expiry_date"],
	"filler": ["product_name", "dose", "dose_unit", "lot_no", "expiry_date", "plane", "technique"],
	"laser": ["device", "fluence", "spot_size", "pulse_duration", "repetition_rate", "no_of_pulses"],
	"biopsy": ["lesion_id", "diagnosis", "body_region"],
	"lesion": ["lesion_id", "diagnosis", "severity", "status"],
	"acne": ["diagnosis", "severity", "status"],
	"scar": ["diagnosis", "severity", "status"],
	"pigmentation": ["diagnosis", "severity", "status"],
}


def execute():
	"""Write the category-name table's contribution into each template's own required
	fields, so nothing stops being required when the table is deleted.

	The two safety flags are deliberately not materialised - they stay live. Re-runnable:
	a template that already declares its resolved set is skipped, and a template whose
	declared value cannot be read is left untouched and logged.
	"""
	if not (
		api._has_field("Clinical Procedure Template", "custom_derma_required_fields")
		and api._has_field("Clinical Procedure Template", "custom_derma_category")
	):
		return

	rows = frappe.get_all(
		"Clinical Procedure Template",
		filters={"custom_derma_category": ["is", "set"]},
		fields=["name", "custom_derma_category", "custom_derma_required_fields"],
		limit_page_length=0,
	)
	for row in rows:
		_materialize_template(row)


def _materialize_template(row: dict) -> None:
	raw = row.get("custom_derma_required_fields")
	declared = api._parse_required_fields(raw)
	if api._is_unreadable_json(raw, declared):
		frappe.log_error(
			title="Derma required fields left unmigrated",
			message=f"{row['name']} declares required fields this patch cannot read: {raw}",
		)
		return

	resolved = list(
		dict.fromkeys([*declared, *_category_name_required_fields(row.get("custom_derma_category"))])
	)
	if resolved == declared:
		return

	frappe.db.set_value(
		"Clinical Procedure Template",
		row["name"],
		"custom_derma_required_fields",
		json.dumps(resolved),
		update_modified=False,
	)


def _category_name_required_fields(category: str | None) -> list[str]:
	return CATEGORY_NAME_REQUIRED_FIELDS.get((category or "").strip().lower(), [])
