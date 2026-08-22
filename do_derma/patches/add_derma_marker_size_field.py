from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	if not frappe.db.exists("DocType", "Clinical Procedure Template"):
		return
	create_custom_fields(
		{
			"Clinical Procedure Template": [
				{
					"fieldname": "custom_derma_marker_size",
					"fieldtype": "Float",
					"label": "Marker Size",
					"precision": "2",
					"description": "Multiplier the chart stamps this marker at. Empty means 1.0.",
					"insert_after": "custom_derma_marker_color",
					"module": "Do Derma",
				},
			]
		},
		ignore_validate=True,
	)
	frappe.clear_cache(doctype="Clinical Procedure Template")
