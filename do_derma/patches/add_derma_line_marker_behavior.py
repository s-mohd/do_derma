from __future__ import annotations

import frappe

FIELDNAME = "custom_derma_marker_behavior"
BEHAVIOR = "line"


def execute():
	"""Offer "line" when configuring a Clinical Procedure Template's marker behaviour.

	A line procedure arms the annotation studio's line tool in its colour and turns the drawn
	line into one Derma Chart Mark - an incision, a scar, an injection track. Without the option
	a clinic cannot select the behaviour from the form at all, because the field is a Select.
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
