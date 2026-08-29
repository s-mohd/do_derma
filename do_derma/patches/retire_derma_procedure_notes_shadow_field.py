"""Give a procedure note one owner: the core `notes` field.

The chart wrote `custom_derma_notes` because healthcare marks `notes` set_only_once,
so the chart, the desk form, and reports could each show a different note. do_derma
now unlocks `notes`; this copies back anything the shadow field learned and drops it.
"""

import frappe

from do_derma.schema import ensure_derma_schema


def execute():
	ensure_derma_schema()
	if not frappe.db.exists("DocType", "Clinical Procedure"):
		return
	if not frappe.get_meta("Clinical Procedure").has_field("custom_derma_notes"):
		return
	_copy_drifted_notes_back()
	field = frappe.db.get_value(
		"Custom Field", {"dt": "Clinical Procedure", "fieldname": "custom_derma_notes"}
	)
	if field:
		# delete_doc, not db.delete: the controller drops the column with the field.
		frappe.delete_doc("Custom Field", field, ignore_permissions=True)
	frappe.clear_cache(doctype="Clinical Procedure")


def _copy_drifted_notes_back():
	drifted = frappe.db.sql(
		"""
		select name, custom_derma_notes
		from `tabClinical Procedure`
		where ifnull(custom_derma_notes, '') != ''
			and ifnull(custom_derma_notes, '') != ifnull(notes, '')
		""",
		as_dict=True,
	)
	for row in drifted:
		# The shadow value is the edited one - every note edit since the chart shipped went there.
		frappe.db.set_value(
			"Clinical Procedure", row.name, "notes", row.custom_derma_notes, update_modified=False
		)
