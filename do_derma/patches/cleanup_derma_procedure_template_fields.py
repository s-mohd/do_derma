from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	add_derma_variables_field()
	remove_obsolete_annotation_treatment_field()


def add_derma_variables_field():
	if not frappe.db.exists("DocType", "Clinical Procedure Template"):
		return
	meta = frappe.get_meta("Clinical Procedure Template")
	insert_after = "custom_derma_allowed_body_regions" if meta.has_field("custom_derma_allowed_body_regions") else "description"
	create_custom_fields(
		{
			"Clinical Procedure Template": [
				{
					"fieldname": "custom_derma_variables_json",
					"fieldtype": "Code",
					"label": "Derma Variables JSON",
					"options": "JSON",
					"description": "Procedure variables shown in the derma annotation studio. Use fieldname, label, fieldtype, options, and required.",
					"insert_after": insert_after,
					"module": "Do Derma",
				},
			]
		},
		ignore_validate=True,
	)
	frappe.clear_cache(doctype="Clinical Procedure Template")


def remove_obsolete_annotation_treatment_field():
	fieldname = "custom_derma_annotation_treatment"
	name = frappe.db.exists("Custom Field", {"dt": "Clinical Procedure Template", "fieldname": fieldname})
	if not name:
		return
	frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
	frappe.clear_cache(doctype="Clinical Procedure Template")
