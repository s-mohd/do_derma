from __future__ import annotations

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


CATEGORIES = [
	{
		"title": "Botox",
		"workflow": "Aesthetic",
		"sequence": 10,
		"marker_behavior": "numbered_dot",
		"marker_color": "#2563eb",
		"marker_label": "U",
		"default_body_template": "Face Front",
		"required_fields": ["dose", "dose_unit", "product_name", "lot_no"],
		"consent_required": 1,
		"before_after_photo_required": 1,
		"product_tracking_required": 1,
		"note_sentence_template": "{dose} {dose_unit} of {product_name} injected at {region_label}.",
	},
	{
		"title": "Filler",
		"workflow": "Aesthetic",
		"sequence": 20,
		"marker_behavior": "triangle",
		"marker_color": "#16a34a",
		"default_body_template": "Face Front",
		"required_fields": ["dose", "dose_unit", "product_name", "plane", "technique", "lot_no"],
		"consent_required": 1,
		"before_after_photo_required": 1,
		"product_tracking_required": 1,
		"note_sentence_template": "{dose} {dose_unit} {product_name} placed in {region_label}.",
	},
	{
		"title": "Laser",
		"workflow": "Aesthetic",
		"sequence": 30,
		"marker_behavior": "hatch",
		"marker_color": "#dc2626",
		"default_body_template": "Face Front",
		"required_fields": ["device", "settings", "passes"],
		"consent_required": 1,
		"before_after_photo_required": 1,
		"device_settings_required": 1,
		"note_sentence_template": "{device} laser treatment to {region_label}; settings: {settings}.",
	},
	{
		"title": "Acne",
		"workflow": "Medical",
		"sequence": 40,
		"marker_behavior": "finding_dot",
		"marker_color": "#0ea5e9",
		"default_body_template": "Face Front",
		"required_fields": ["diagnosis", "severity", "status"],
		"before_after_photo_required": 1,
		"note_sentence_template": "{severity} acne at {region_label}, status {status}.",
	},
	{
		"title": "Scar",
		"workflow": "Both",
		"sequence": 50,
		"marker_behavior": "area",
		"marker_color": "#7c3aed",
		"default_body_template": "Face Front",
		"required_fields": ["diagnosis", "severity", "status"],
		"before_after_photo_required": 1,
		"note_sentence_template": "{severity} scarring at {region_label}.",
	},
	{
		"title": "Pigmentation",
		"workflow": "Medical",
		"sequence": 60,
		"marker_behavior": "area",
		"marker_color": "#92400e",
		"default_body_template": "Face Front",
		"required_fields": ["diagnosis", "severity", "status"],
		"before_after_photo_required": 1,
		"note_sentence_template": "{severity} pigmentation at {region_label}.",
	},
	{
		"title": "Lesion",
		"workflow": "Medical",
		"sequence": 70,
		"marker_behavior": "target",
		"marker_color": "#ea580c",
		"default_body_template": "Body Front",
		"required_fields": ["lesion_id", "diagnosis", "status"],
		"note_sentence_template": "Lesion {lesion_id} reviewed at {region_label}.",
	},
	{
		"title": "Biopsy",
		"workflow": "Medical",
		"sequence": 80,
		"marker_behavior": "x_mark",
		"marker_color": "#eab308",
		"default_body_template": "Body Front",
		"required_fields": ["lesion_id", "diagnosis"],
		"consent_required": 1,
		"note_sentence_template": "Biopsy marked for lesion {lesion_id} at {region_label}.",
	},
]


BODY_TEMPLATES = []


PROCEDURE_TEMPLATES = [
	("Derma Botox Injection", "Botox", "numbered_dot", "#2563eb", "Botulinum toxin injection charted by facial point with units, product, lot, consent, and follow-up."),
	("Derma Filler Injection", "Filler", "triangle", "#16a34a", "Dermal filler placement charted by region, product, ml, plane, technique, lot, and consent."),
	("Derma Laser Treatment", "Laser", "hatch", "#dc2626", "Laser treatment charted by region, device settings, passes, endpoint, and post-care plan."),
	("Derma Acne Review", "Acne", "finding_dot", "#0ea5e9", "Acne severity, distribution, response, medication tolerance, and follow-up reviewed."),
	("Derma Scar Treatment", "Scar", "area", "#7c3aed", "Scar treatment charted by region, severity, treatment method, and response tracking."),
	("Derma Lesion Review", "Lesion", "target", "#ea580c", "Lesion reviewed and tracked with location, diagnosis, status, photos, and follow-up plan."),
	("Derma Biopsy", "Biopsy", "x_mark", "#eab308", "Biopsy/excision charted with lesion identifier, specimen note, consent, and pathology follow-up."),
]


def execute():
	add_clinical_procedure_template_fields()
	seed_body_templates()
	seed_categories()
	seed_procedure_templates()


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
					"fieldname": "custom_derma_allowed_body_regions",
					"fieldtype": "Small Text",
					"label": "Allowed Body Regions",
					"description": "Comma-separated body region labels.",
					"insert_after": "custom_derma_allowed_body_templates",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_annotation_treatment",
					"fieldtype": "Link",
					"label": "Annotation Treatment Variables",
					"options": "Annotation Treatment",
					"description": "Optional variable schema reused from the annotation app.",
					"insert_after": "custom_derma_allowed_body_regions",
					"module": "Do Derma",
				},
				{
					"fieldname": "custom_derma_marker_behavior",
					"fieldtype": "Select",
					"label": "Marker Behavior",
					"options": "numbered_dot\nblue_dot\nthree_dots\ntriangle\ntriangle_cluster\nhatch\nfive_lines\nx_mark\ntarget\narea\nfinding_dot",
					"insert_after": "custom_derma_annotation_treatment",
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


def seed_categories():
	for row in CATEGORIES:
		if frappe.db.exists("Derma Procedure Category", row["title"]):
			doc = frappe.get_doc("Derma Procedure Category", row["title"])
		else:
			doc = frappe.new_doc("Derma Procedure Category")
			doc.title = row["title"]
		for field, value in row.items():
			if field == "required_fields":
				value = json.dumps(value)
			doc.set(field, value)
		doc.disabled = 0
		doc.save(ignore_permissions=True)


def seed_procedure_templates():
	item_group = frappe.db.exists("Item Group", "Services") or frappe.db.get_value("Item Group", {"is_group": 0}, "name")
	if not item_group:
		return

	for template, category, behavior, color, description in PROCEDURE_TEMPLATES:
		if frappe.db.exists("Clinical Procedure Template", template):
			doc = frappe.get_doc("Clinical Procedure Template", template)
		else:
			doc = frappe.new_doc("Clinical Procedure Template")
			doc.template = template
		doc.item_code = f"DERMA-{category.upper().replace(' ', '-')}"
		doc.description = description
		doc.item_group = item_group
		doc.is_billable = 1
		doc.rate = doc.rate or 0
		if doc.meta.has_field("disabled"):
			doc.disabled = 0
		doc.custom_derma_category = category
		if doc.meta.has_field("custom_derma_annotation_treatment"):
			doc.custom_derma_annotation_treatment = "Laser" if category == "Laser" else "Injection" if category in {"Botox", "Filler"} else ""
		doc.custom_derma_marker_behavior = behavior
		doc.custom_derma_marker_color = color
		doc.custom_derma_allowed_body_templates = "Face Front, Face Left, Face Right" if category in {"Botox", "Filler", "Laser", "Acne", "Scar"} else "Body Front, Body Back, Face Front"
		doc.custom_derma_required_fields = frappe.db.get_value("Derma Procedure Category", category, "required_fields")
		doc.custom_derma_consent_required = frappe.db.get_value("Derma Procedure Category", category, "consent_required")
		doc.custom_derma_before_after_photo_required = frappe.db.get_value("Derma Procedure Category", category, "before_after_photo_required")
		doc.custom_derma_product_tracking_required = frappe.db.get_value("Derma Procedure Category", category, "product_tracking_required")
		doc.custom_derma_device_settings_required = frappe.db.get_value("Derma Procedure Category", category, "device_settings_required")
		doc.custom_derma_note_template = frappe.db.get_value("Derma Procedure Category", category, "note_sentence_template")
		doc.save(ignore_permissions=True)
