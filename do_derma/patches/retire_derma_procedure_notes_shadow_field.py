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
	# Runs before the guard: a site that dropped the field on an earlier run of this
	# patch still has the dangling anchor to repair.
	_reanchor_dependent_fields()
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


def _reanchor_dependent_fields():
	"""A field anchored on the retired one would drift to the end of the form."""
	for name in frappe.get_all(
		"Custom Field",
		filters={"dt": "Clinical Procedure", "insert_after": "custom_derma_notes"},
		pluck="name",
	):
		frappe.db.set_value("Custom Field", name, "insert_after", "notes")


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
