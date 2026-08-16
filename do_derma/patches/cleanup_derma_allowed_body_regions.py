from __future__ import annotations

import frappe

FIELDNAME = "custom_derma_allowed_body_regions"


def execute():
	"""Drop the template's allowed-regions field. Nothing has ever read it - the
	chart scopes a procedure by body template, and a mark's region comes from the
	body template part it lands on."""

	name = frappe.db.exists("Custom Field", {"dt": "Clinical Procedure Template", "fieldname": FIELDNAME})
	if not name:
		return
	frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
	frappe.clear_cache(doctype="Clinical Procedure Template")
