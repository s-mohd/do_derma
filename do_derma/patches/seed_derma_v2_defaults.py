from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

BODY_TEMPLATES = []


def execute():
	add_clinical_procedure_template_fields()
	seed_body_templates()


def add_clinical_procedure_template_fields():
	create_custom_fields(
		{
			"Clinical Procedure Template": [
				{
					"fieldname": "custom_derma_section",
					"fieldtype": "Section Break",
					"label": "Dermatology Chart Behavior",
					"insert_after": "description",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_category",
					"fieldtype": "Link",
					"label": "Derma Category",
					"options": "Derma Procedure Category",
					"insert_after": "custom_derma_section",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_allowed_body_templates",
					"fieldtype": "Small Text",
					"label": "Allowed Body Templates",
					"description": "Comma-separated Derma Body Template names.",
					"insert_after": "custom_derma_category",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_variables_json",
					"fieldtype": "Code",
					"label": "Derma Variables JSON",
					"options": "JSON",
					"description": "Procedure variables shown in the derma annotation studio. Use fieldname, label, fieldtype, options, and required.",
					"insert_after": "custom_derma_allowed_body_templates",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_marker_behavior",
					"fieldtype": "Select",
					"label": "Marker Behavior",
					"options": "numbered_dot\nblue_dot\nthree_dots\ntriangle\ntriangle_cluster\nhatch\nfive_lines\nx_mark\ntarget\narea\nfinding_dot",
					"insert_after": "custom_derma_variables_json",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_marker_color",
					"fieldtype": "Data",
					"label": "Marker Color",
					"insert_after": "custom_derma_marker_behavior",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_marker_preset_json",
					"fieldtype": "Code",
					"label": "Marker Preset JSON",
					"options": "JSON",
					"description": "Optional future-ready Excalidraw element preset for click-to-stamp charting.",
					"insert_after": "custom_derma_marker_color",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_required_fields",
					"fieldtype": "Code",
					"label": "Required Fields JSON",
					"options": "JSON",
					"insert_after": "custom_derma_marker_preset_json",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_consent_required",
					"fieldtype": "Check",
					"label": "Consent Required",
					"insert_after": "custom_derma_required_fields",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_before_after_photo_required",
					"fieldtype": "Check",
					"label": "Before / After Photo Required",
					"insert_after": "custom_derma_consent_required",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_product_tracking_required",
					"fieldtype": "Check",
					"label": "Product / Lot Required",
					"insert_after": "custom_derma_before_after_photo_required",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_device_settings_required",
					"fieldtype": "Check",
					"label": "Device Settings Required",
					"insert_after": "custom_derma_product_tracking_required",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_note_template",
					"fieldtype": "Small Text",
					"label": "Note Sentence Template",
					"insert_after": "custom_derma_device_settings_required",
					"module": "Do Derma",
				},
			]
		},
		ignore_validate=True,
	)


def seed_body_templates():
	for title, template_type, gender, view_key, sequence, image in BODY_TEMPLATES:
		if frappe.db.exists("Derma Body Template", title):
			doc = frappe.get_doc("Derma Body Template", title)
		else:
			doc = frappe.new_doc("Derma Body Template")
			doc.title = title
		doc.template_type = template_type
		if doc.meta.has_field("gender"):
			doc.gender = gender
		if doc.meta.has_field("is_standard"):
			doc.is_standard = 1
		doc.view_key = view_key
		doc.image = image
		doc.sequence = sequence
		doc.disabled = 0
		doc.save(ignore_permissions=True)
