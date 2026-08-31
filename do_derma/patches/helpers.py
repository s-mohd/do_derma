from __future__ import annotations

import frappe


def upsert_sidebar_item(values: dict) -> None:
	"""Converge one do_health sidebar item, skipping the columns this site's version of
	the doctype does not have. Keyed on section plus label, which is how it is named."""
	if not frappe.db.exists("DocType", "Health Sidebar Item"):
		return

	name = frappe.db.get_value(
		"Health Sidebar Item",
		{"section": values["section"], "label": values["label"]},
		"name",
	)
	payload = {
		"route_params": "",
		"client_action": "",
		"parent_item": "",
		"requires_capability": "",
		"open_mode": "Current Tab",
		"badge_method": "",
		"css_class": "",
		**values,
	}
	requirement = (payload.get("context_requirement") or "none").strip().lower()
	columns = set(frappe.db.get_table_columns("Health Sidebar Item"))
	if "requires_patient" in columns:
		payload["requires_patient"] = 1 if requirement in {"patient", "appointment", "encounter"} else 0
	if "require_session" in columns:
		payload["require_session"] = 1 if requirement == "encounter" else 0
	payload = {key: value for key, value in payload.items() if key in columns or key == "doctype"}

	if name:
		frappe.db.set_value("Health Sidebar Item", name, payload)
	else:
		frappe.get_doc({"doctype": "Health Sidebar Item", **payload}).insert(ignore_permissions=True)


def ensure_standard_page(page_name: str, title: str) -> None:
	"""Converge a source-backed desk Page row on sites without developer mode.

	Field-by-field so an unchanged row is never written and `modified` stays put.
	"""
	values = {
		"page_name": page_name,
		"title": title,
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
