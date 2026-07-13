from __future__ import annotations

import frappe


def execute():
	"""Extend Health Annotation Table.type with a "Derma Annotation" option.

	The field only ships with Investigation/Treatment, but do_derma's annotation studio
	always tags its rows "Derma Annotation" - without this the child-table save fails
	validation every time (Select field rejects an option outside its list).
	"""
	if not frappe.db.exists("DocType", "Health Annotation Table"):
		return

	meta = frappe.get_meta("Health Annotation Table")
	type_field = meta.get_field("type")
	if not type_field:
		return

	options = [opt.strip() for opt in (type_field.options or "").split("\n") if opt.strip()]
	if "Derma Annotation" in options:
		return

	options.append("Derma Annotation")
	frappe.make_property_setter(
		{
			"doctype": "Health Annotation Table",
			"fieldname": "type",
			"property": "options",
			"value": "\n".join(options),
			"property_type": "Text",
		}
	)
	frappe.db.commit()
