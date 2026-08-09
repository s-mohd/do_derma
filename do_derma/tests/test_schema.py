from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from do_derma.schema import DERMA_CUSTOM_FIELDS, ensure_derma_schema, has_field


class TestEnsureDermaSchema(IntegrationTestCase):
	"""The schema spine runs on every migrate, so it must be safe to re-run and
	must never overwrite what a clinic has changed."""

	def test_creates_missing_custom_fields(self):
		ensure_derma_schema()
		for doctype, specs in DERMA_CUSTOM_FIELDS.items():
			if not frappe.db.exists("DocType", doctype):
				continue
			for spec in specs:
				self.assertTrue(
					has_field(doctype, spec["fieldname"]),
					msg=f"{doctype}.{spec['fieldname']} was not created",
				)

	def test_second_run_is_noop(self):
		ensure_derma_schema()
		before = frappe.db.count("Custom Field", {"module": "Do Derma"})
		created = ensure_derma_schema()
		after = frappe.db.count("Custom Field", {"module": "Do Derma"})
		self.assertEqual(created, {})
		self.assertEqual(before, after)

	def test_never_overwrites_an_existing_field(self):
		ensure_derma_schema()
		fieldname = "custom_derma_soap_subjective"
		name = frappe.db.get_value("Custom Field", {"dt": "Patient Encounter", "fieldname": fieldname})
		self.assertTrue(name, msg="expected the SOAP field to exist after ensure_derma_schema")

		field = frappe.get_doc("Custom Field", name)
		original_label = field.label
		self.addCleanup(frappe.db.set_value, "Custom Field", name, "label", original_label)
		frappe.db.set_value("Custom Field", name, "label", "Clinic Renamed This")
		frappe.clear_cache(doctype="Patient Encounter")

		ensure_derma_schema()

		self.assertEqual(
			frappe.db.get_value("Custom Field", name, "label"),
			"Clinic Renamed This",
			msg="ensure_derma_schema clobbered a clinic-set label",
		)

	def test_survives_a_missing_doctype(self):
		"""A site without Healthcare Practitioner must not break the migrate."""
		created = ensure_derma_schema()
		self.assertIsInstance(created, dict)
