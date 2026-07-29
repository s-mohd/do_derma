from __future__ import annotations

import frappe


def execute():
	"""Ensure the standard Derma Chart desk page exists on non-developer sites.

	The page is shipped as a source-backed Page, but a live site can still lose the
	database row if it was deleted manually. Creating it in a patch avoids the need
	to enable developer mode on production.
	"""
	page_name = "derma-chart"
	values = {
		"page_name": page_name,
		"title": "Derma Chart",
		"module": "Do Derma",
		"standard": "Yes",
		"system_page": 0,
	}

	if frappe.db.exists("Page", page_name):
		doc = frappe.get_doc("Page", page_name)
		changed = False
		for fieldname, value in values.items():
			if doc.get(fieldname) != value:
				doc.set(fieldname, value)
				changed = True
		if changed:
			doc.save(ignore_permissions=True)
	else:
		frappe.get_doc({"doctype": "Page", "name": page_name, **values}).insert(ignore_permissions=True)

	frappe.clear_cache()
