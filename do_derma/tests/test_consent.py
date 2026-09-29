from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from do_derma import schema


class TestConsentSchema(IntegrationTestCase):
	def test_consent_form_carries_the_procedure_table(self):
		if not frappe.db.exists("DocType", "Consent Form"):
			self.skipTest("Consent Form is not installed.")
		schema.ensure_derma_schema()
		field = frappe.get_meta("Consent Form").get_field("custom_derma_procedures")
		self.assertIsNotNone(field)
		self.assertEqual((field.fieldtype, field.options), ("Table", "Derma Consent Procedure"))
