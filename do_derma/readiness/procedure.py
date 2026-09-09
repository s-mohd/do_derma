"""The gate at Clinical Procedure creation: a different transition from session completion."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from do_derma import api

# A required variable is named by the template but stored on the mark's own fields.
MARK_FIELD_ALIASES = {
	"product": "product_name",
	"item": "product_item",
	"item_code": "product_item",
	"product_item": "product_item",
	"injectable": "product_name",
	"lot": "lot_no",
	"expiry": "expiry_date",
	"units": "dose",
	"ml": "dose",
	"quantity": "dose",
	"site": "body_region",
}


def validate_marks_ready(mark_docs: list[Any], template_doc, clinical_procedure: str | None = None) -> None:
	"""Throw unless every mark carries what its template requires.

	A template that captures its variables once per procedure is exempt from *per-mark*
	completeness, never from completeness: the shared value has to be there instead.
	"""
	required_variables = [row for row in api._get_template_variables(template_doc) if row.get("required")]
	per_procedure = bool(template_doc.get("custom_derma_variables_per_procedure"))
	shared = (
		api._procedure_level_variables(clinical_procedure, template_doc.get("name")) if per_procedure else {}
	)

	def is_satisfied(shared_keys: list[str], from_mark) -> bool:
		if per_procedure:
			if any(shared.get(api._variable_fieldname(key)) not in (None, "") for key in shared_keys):
				return True
			# `all()` over no marks is vacuously true, which would pass a markless procedure
			# with nothing filled at all. The shared value is the only answer left.
			if not mark_docs:
				return False
		return all(from_mark(mark_doc) not in (None, "") for mark_doc in mark_docs)

	missing = []
	for variable in required_variables:
		fieldname = variable.get("fieldname")
		if fieldname and not is_satisfied(
			[fieldname], lambda mark_doc, name=fieldname: mark_variable_value(mark_doc, name)
		):
			missing.append(variable.get("label") or fieldname)

	if template_doc.get("custom_derma_product_tracking_required"):
		if not is_satisfied(
			["product_name", "product_item"],
			lambda mark_doc: mark_doc.get("product_name") or mark_doc.get("product_item"),
		):
			missing.append(_("Product / Device"))
		if not is_satisfied(["lot_no"], lambda mark_doc: mark_doc.get("lot_no")):
			missing.append(_("Lot No"))

	if missing:
		frappe.throw(
			_(
				"Complete required derma procedure details before creating the Clinical Procedure: {0}."
			).format(", ".join(dict.fromkeys(missing)))
		)

	if template_doc.get("custom_derma_before_after_photo_required") and not any(
		mark_doc.get("photo_set") for mark_doc in mark_docs
	):
		frappe.throw(_("Photo evidence is required before creating this Clinical Procedure."))


def mark_variable_value(mark_doc, fieldname: str):
	key = api._variable_fieldname(fieldname)
	value = mark_doc.get(MARK_FIELD_ALIASES.get(key, key))
	if value not in (None, ""):
		return value
	# Only a fieldname Derma Chart Mark happens to own is a DocField; save_chart_mark files
	# the rest as child rows. Reading DocFields alone refused a clinic-named variable the
	# practitioner had filled in, because the gate could not see where it was kept.
	for row in mark_doc.get("area_variables") or []:
		if row.get("source") == "Procedure" and row.get("fieldname") == key:
			return row.get("value")
	return value
