from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma import assessment, voice
from do_derma.assessment import HP, HP_FIELDS, SOAP, SOAP_FIELDS, STRUCTURED
from do_derma.printing import note
from do_derma.schema import ensure_derma_schema
from do_derma.tests.test_api import DermaTestHelpers


class TestStructuredFromAI(DermaTestHelpers, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_derma_schema()

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")
		if "symptoms" not in {row["fieldname"] for row in voice.structured_layout()}:
			self.skipTest("symptoms is not on the Structured layout of this site")

	def _creates_masters(self, on):
		return patch.object(
			voice, "_setting", side_effect=lambda name, default=None: {"ai_creates_clinical_masters": on}.get(name, default)
		)

	def _make_complaint(self, title):
		doc = frappe.get_doc({"doctype": "Complaint", "complaints": title}).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Complaint", doc.name, True)
		return doc.name

	def test_prompt_block_lists_text_fields_and_marks_tables_as_list(self):
		block = voice.structured_prompt_block()
		self.assertIn("- symptoms (LIST): Symptoms", block)
		self.assertIn("- custom_symptoms_notes: Symptoms Notes", block)
		self.assertNotIn("custom_symptoms_notes (LIST)", block)
		self.assertIn(block, voice.build_note_prompt("patient says itchy hands for a week"))

	def test_matched_term_links_and_unmatched_term_spills_into_notes(self):
		token = frappe.generate_hash(length=6)
		known = self._make_complaint(f"Pruritus {token}")
		unknown = f"Zzz nothing {token}"
		with self._creates_masters(0):
			values = voice.structured_values_from_ai(
				{"symptoms": [known.lower(), unknown], "custom_physical_examination": "  Scaly plaques  "}
			)
		self.assertEqual(values["custom_physical_examination"], "Scaly plaques")
		self.assertEqual(values["symptoms"], [{"complaint": known}])
		self.assertIn(unknown, values["custom_symptoms_notes"])
		self.assertFalse(frappe.db.exists("Complaint", unknown))

	def test_setting_on_creates_and_links_the_master(self):
		unknown = f"Zzz new {frappe.generate_hash(length=6)}"
		self.addCleanup(lambda: frappe.delete_doc("Complaint", unknown, force=True, ignore_missing=True))
		with self._creates_masters(1):
			values = voice.structured_values_from_ai({"symptoms": [unknown]})
		self.assertTrue(frappe.db.exists("Complaint", unknown))
		self.assertEqual(values["symptoms"], [{"complaint": unknown}])
		self.assertNotIn("custom_symptoms_notes", values)


class TestSetAssessmentAll(DermaTestHelpers, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_derma_schema()

	def setUp(self):
		if not assessment.hp_is_supported():
			self.skipTest("H&P custom fields are not installed on this site")
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")

	PAYLOADS = {
		STRUCTURED: {"custom_physical_examination": "Scaly plaques on both hands"},
		SOAP: {SOAP_FIELDS[0]: "Itchy hands for two weeks"},
		HP: {HP_FIELDS[0]: "Itchy hands"},
	}

	def test_draft_writes_all_three_formats_and_stamps_the_mode(self):
		encounter = self._make_encounter(self._make_patient())
		out = api.set_derma_assessment_all(payloads=json.dumps(self.PAYLOADS), mode=SOAP, encounter=encounter.name)
		self.assertEqual(out["mode"], SOAP)
		self.assertTrue(out["is_filled"])
		self.assertEqual(out["soap_values"][SOAP_FIELDS[0]], "Itchy hands for two weeks")
		self.assertEqual(out["hp_values"][HP_FIELDS[0]], "Itchy hands")
		self.assertEqual(
			frappe.db.get_value("Patient Encounter", encounter.name, "custom_physical_examination"),
			"Scaly plaques on both hands",
		)
		self.assertEqual(frappe.db.get_value("Patient Encounter", encounter.name, assessment.MODE_FIELD), SOAP)

	def test_submitted_encounter_raises_instead_of_silently_skipping(self):
		encounter = self._make_encounter(self._make_patient(), docstatus=1)
		with self.assertRaises(frappe.ValidationError) as caught:
			api.set_derma_assessment_all(payloads=self.PAYLOADS, mode=SOAP, encounter=encounter.name)
		self.assertIn("completed", str(caught.exception))
		self.assertFalse(frappe.db.get_value("Patient Encounter", encounter.name, SOAP_FIELDS[0]))


class TestAssessmentPrintFormat(DermaTestHelpers, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_derma_schema()

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")
		if frappe.db.exists("Print Format", note.PRINT_FORMAT):
			frappe.delete_doc("Print Format", note.PRINT_FORMAT, force=True)
		self.addCleanup(lambda: frappe.delete_doc("Print Format", note.PRINT_FORMAT, force=True, ignore_missing=True))

	def test_seeded_once(self):
		self.assertEqual(note.ensure_assessment_print_format(), note.PRINT_FORMAT)
		self.assertEqual(note.ensure_assessment_print_format(), "")
		self.assertEqual(frappe.db.count("Print Format", {"name": note.PRINT_FORMAT}), 1)
		self.assertEqual(frappe.db.get_value("Print Format", note.PRINT_FORMAT, "doc_type"), "Patient Encounter")

	def test_renders_patient_and_active_mode_content(self):
		note.ensure_assessment_print_format()
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		api.set_derma_assessment_all(
			payloads={STRUCTURED: {"custom_physical_examination": "Scaly plaques on both hands"}},
			mode=STRUCTURED,
			encounter=encounter.name,
		)
		printed = frappe.get_print("Patient Encounter", encounter.name, print_format=note.PRINT_FORMAT)
		self.assertIn(frappe.db.get_value("Patient", patient, "patient_name"), printed)
		self.assertIn("Scaly plaques on both hands", printed)
		self.assertIn('class="derma-structured"', printed)
