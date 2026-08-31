from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Ensure Health Annotation.custom_derma_body_template_title exists.

	`_save_health_annotation` has always written this field behind a `_has_field` guard and
	`get_derma_annotation_summary` has always read it, but nothing ever created it - so every
	annotation fell back to labelling itself by its docname hash.
	"""
	if not frappe.db.exists("DocType", "Health Annotation"):
		return

	meta = frappe.get_meta("Health Annotation")
	if meta.has_field("custom_derma_body_template_title"):
		return

	create_custom_fields(
		{
			"Health Annotation": [
				{
					"fieldname": "custom_derma_body_template_title",
					"fieldtype": "Data",
					"label": "Body Template Title",
					"insert_after": "annotation_template",
					"read_only": 1,
					"module": "Do Derma",
				},
			]
		},
		ignore_validate=True,
	)
	frappe.clear_cache(doctype="Health Annotation")
