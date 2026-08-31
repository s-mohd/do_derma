from __future__ import annotations

import frappe

TEMPLATE_IMAGES = {}


def execute():
	if not frappe.db.exists("DocType", "Derma Body Template"):
		return
	for template, image in TEMPLATE_IMAGES.items():
		if frappe.db.exists("Derma Body Template", template):
			frappe.db.set_value("Derma Body Template", template, "image", image, update_modified=False)
