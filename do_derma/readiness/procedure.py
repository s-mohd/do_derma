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


def validate_marks_ready(mark_docs: list[Any], template_doc) -> None:
	"""Throw unless every mark carries what its template requires."""
	required_variables = [row for row in api._get_template_variables(template_doc) if row.get("required")]
	missing = []
	for variable in required_variables:
		fieldname = variable.get("fieldname")
		if fieldname and not all(
			mark_variable_value(mark_doc, fieldname) not in (None, "") for mark_doc in mark_docs
		):
			missing.append(variable.get("label") or fieldname)

	if template_doc.get("custom_derma_product_tracking_required"):
		if not all(mark_doc.get("product_name") or mark_doc.get("product_item") for mark_doc in mark_docs):
			missing.append(_("Product / Device"))
		if not all(mark_doc.get("lot_no") for mark_doc in mark_docs):
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
	return mark_doc.get(MARK_FIELD_ALIASES.get(key, key))
