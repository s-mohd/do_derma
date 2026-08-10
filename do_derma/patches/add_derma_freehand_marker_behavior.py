from __future__ import annotations

import frappe

FIELDNAME = "custom_derma_marker_behavior"
BEHAVIOR = "freehand"


def execute():
	"""Offer "freehand" when configuring a Clinical Procedure Template's marker behaviour.

	A freehand procedure turns the annotation studio's pen its colour and converts the finished
	stroke into one Derma Chart Mark. Without the option a clinic cannot select the behaviour
	from the form at all, because the field is a Select.
	"""
	if not frappe.db.exists("DocType", "Clinical Procedure Template"):
		return

	field = frappe.get_meta("Clinical Procedure Template").get_field(FIELDNAME)
	if not field:
		return

	options = [option.strip() for option in (field.options or "").split("\n") if option.strip()]
	if BEHAVIOR in options:
		return

	options.append(BEHAVIOR)
	frappe.make_property_setter(
		{
			"doctype": "Clinical Procedure Template",
			"fieldname": FIELDNAME,
			"property": "options",
			"value": "\n".join(options),
			"property_type": "Text",
		}
	)
	frappe.db.commit()
