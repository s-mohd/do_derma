from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma import assessment
from do_derma.assessment import HP, HP_FIELDS, SOAP, SOAP_FIELDS
from do_derma.printing import render
from do_derma.schema import ensure_derma_schema
from do_derma.tests.test_api import DermaTestHelpers


class TestHistoryAndPhysicalMode(DermaTestHelpers, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_derma_schema()

	def setUp(self):
		if not assessment.hp_is_supported():
			self.skipTest("H&P custom fields are not installed on this site")
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")
		self.encounter = self._make_encounter(self._make_patient())

	def test_hp_is_an_available_mode_with_six_fields(self):
		self.assertIn(HP, assessment.available_modes())
		layout = assessment.get_hp_layout()
		self.assertEqual([row["fieldname"] for row in layout], list(HP_FIELDS))
		self.assertEqual(layout[0]["label"], "Chief Complaint")

	def test_mode_select_carries_hp(self):
		options = frappe.get_meta("Patient Encounter").get_field(assessment.MODE_FIELD).options
		self.assertIn("HP", options.split("\n"))

	def test_hp_content_stamps_hp_and_reads_back(self):
		api.set_derma_assessment(
			payload={HP_FIELDS[0]: "Itchy hands", HP_FIELDS[5]: "Emollients"}, mode=HP, encounter=self.encounter.name
		)
		out = api.get_derma_assessment(encounter=self.encounter.name)
		self.assertEqual(out["mode"], HP)
		self.assertTrue(out["is_filled"])
		self.assertEqual(out["hp_values"][HP_FIELDS[0]], "Itchy hands")
		self.assertEqual(out["hp_values"][HP_FIELDS[5]], "Emollients")
		self.assertIn("hp_layout", out)

	def test_hp_write_cannot_touch_soap_fields(self):
		api.set_derma_assessment(payload={SOAP_FIELDS[0]: "leak"}, mode=HP, encounter=self.encounter.name)
		self.assertFalse(frappe.db.get_value("Patient Encounter", self.encounter.name, SOAP_FIELDS[0]))

	def test_switching_to_hp_keeps_soap_content(self):
		api.set_derma_assessment(payload={SOAP_FIELDS[2]: "Acne"}, mode=SOAP, encounter=self.encounter.name)
		api.set_derma_assessment_mode(HP, encounter=self.encounter.name)
		out = api.get_derma_assessment(encounter=self.encounter.name)
		self.assertEqual(out["mode"], HP)
		self.assertEqual(out["soap_values"][SOAP_FIELDS[2]], "Acne")

	def test_print_block_uses_hp_heading_and_falls_back_across_modes(self):
		api.set_derma_assessment(payload={HP_FIELDS[4]: "Psoriasis"}, mode=HP, encounter=self.encounter.name)
		html = str(render.derma_assessment_html(self.encounter.name))
		self.assertIn("Assessment (H&amp;P)", html)
		self.assertIn("Psoriasis", html)
		# Stamp a different mode that holds nothing: the H&P content must still print.
		frappe.db.set_value("Patient Encounter", self.encounter.name, assessment.MODE_FIELD, SOAP)
		self.assertIn("Psoriasis", str(render.derma_assessment_html(self.encounter.name)))
