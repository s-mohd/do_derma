from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Ensure Health Annotation Table.annotation_data exists without depending on the
	separate `annotation` app's own patch for it - do_derma reads/writes this field directly.
	"""
	if not frappe.db.exists("DocType", "Health Annotation Table"):
		return

	meta = frappe.get_meta("Health Annotation Table")
	if meta.has_field("annotation_data"):
		return

	create_custom_fields(
		{
			"Health Annotation Table": [
				{
					"fieldname": "annotation_data",
					"fieldtype": "Small Text",
					"label": "Annotation Data",
					"insert_after": "type",
				},
			]
		},
		ignore_validate=True,
	)
	frappe.clear_cache(doctype="Health Annotation Table")
