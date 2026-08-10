from __future__ import annotations

import json

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma import assessment
from do_derma.schema import ensure_derma_schema
from do_derma.settings import SETTINGS_DOCTYPE
from do_derma.tests.test_api import DermaTestHelpers


class AssessmentTestBase(DermaTestHelpers, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_derma_schema()

	def setUp(self):
		if not assessment.soap_is_supported():
			self.skipTest("SOAP custom fields are not installed on this site")
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")

	def _draft_encounter(self):
		return self._make_encounter(self._make_patient())


class TestStructuredLayout(AssessmentTestBase):
	def _set_configured_fields(self, fieldnames):
		settings = frappe.get_doc(SETTINGS_DOCTYPE)
		original = [
			{"fieldname": row.fieldname, "enabled": row.enabled}
			for row in settings.get("structured_assessment_fields") or []
		]
		self.addCleanup(self._restore_fields, original)
		settings.set("structured_assessment_fields", [])
		for fieldname in fieldnames:
			settings.append("structured_assessment_fields", {"fieldname": fieldname, "enabled": 1})
		settings.save(ignore_permissions=True)

	def _restore_fields(self, rows):
		settings = frappe.get_doc(SETTINGS_DOCTYPE)
		settings.set("structured_assessment_fields", [])
		for row in rows:
			settings.append("structured_assessment_fields", row)
		settings.save(ignore_permissions=True)

	def test_layout_comes_from_settings_in_order(self):
		self._set_configured_fields(["diagnosis", "symptoms"])
		layout = assessment.get_structured_layout()
		self.assertEqual([row["fieldname"] for row in layout], ["diagnosis", "symptoms"])

	def test_layout_skips_absent_fields(self):
		self._set_configured_fields(["symptoms", "custom_field_that_does_not_exist", "diagnosis"])
		layout = assessment.get_structured_layout()
		fieldnames = [row["fieldname"] for row in layout]
		self.assertNotIn("custom_field_that_does_not_exist", fieldnames)
		self.assertEqual(fieldnames, ["symptoms", "diagnosis"])

	def test_disabled_rows_are_dropped(self):
		settings = frappe.get_doc(SETTINGS_DOCTYPE)
		original = [
			{"fieldname": row.fieldname, "enabled": row.enabled}
			for row in settings.get("structured_assessment_fields") or []
		]
		self.addCleanup(self._restore_fields, original)
		settings.set("structured_assessment_fields", [])
		settings.append("structured_assessment_fields", {"fieldname": "symptoms", "enabled": 1})
		settings.append("structured_assessment_fields", {"fieldname": "diagnosis", "enabled": 0})
		settings.save(ignore_permissions=True)
		self.assertEqual([row["fieldname"] for row in assessment.get_structured_layout()], ["symptoms"])


class TestAssessmentModeStamping(AssessmentTestBase):
	def test_open_does_not_stamp(self):
		encounter = self._draft_encounter()
		result = api.get_derma_assessment(encounter=encounter.name)
		self.assertFalse(result["is_stamped"])
		self.assertFalse(frappe.db.get_value("Patient Encounter", encounter.name, assessment.MODE_FIELD))

	def test_mode_stamped_on_first_content_save(self):
		encounter = self._draft_encounter()
		api.set_derma_assessment(
			payload=json.dumps({"custom_derma_soap_subjective": "Itching for three weeks"}),
			mode=assessment.SOAP,
			encounter=encounter.name,
		)
		self.assertEqual(
			frappe.db.get_value("Patient Encounter", encounter.name, assessment.MODE_FIELD),
			assessment.SOAP,
		)

	def test_empty_save_does_not_stamp(self):
		encounter = self._draft_encounter()
		api.set_derma_assessment(
			payload=json.dumps({"custom_derma_soap_subjective": "   "}),
			mode=assessment.SOAP,
			encounter=encounter.name,
		)
		self.assertFalse(frappe.db.get_value("Patient Encounter", encounter.name, assessment.MODE_FIELD))

	def test_stamped_mode_beats_practitioner_default(self):
		encounter = self._draft_encounter()
		api.set_derma_assessment(
			payload=json.dumps({"custom_derma_soap_plan": "Topical steroid"}),
			mode=assessment.SOAP,
			encounter=encounter.name,
		)

		practitioner = encounter.practitioner
		original = frappe.db.get_value(
			"Healthcare Practitioner", practitioner, assessment.PRACTITIONER_DEFAULT_FIELD
		)
		self.addCleanup(
			frappe.db.set_value,
			"Healthcare Practitioner",
			practitioner,
			assessment.PRACTITIONER_DEFAULT_FIELD,
			original,
		)
		frappe.db.set_value(
			"Healthcare Practitioner",
			practitioner,
			assessment.PRACTITIONER_DEFAULT_FIELD,
			assessment.STRUCTURED,
		)

		self.assertEqual(api.get_derma_assessment(encounter=encounter.name)["mode"], assessment.SOAP)

	def test_practitioner_default_applies_to_a_new_encounter(self):
		encounter = self._draft_encounter()
		practitioner = encounter.practitioner
		original = frappe.db.get_value(
			"Healthcare Practitioner", practitioner, assessment.PRACTITIONER_DEFAULT_FIELD
		)
		self.addCleanup(
			frappe.db.set_value,
			"Healthcare Practitioner",
			practitioner,
			assessment.PRACTITIONER_DEFAULT_FIELD,
			original,
		)
		frappe.db.set_value(
			"Healthcare Practitioner",
			practitioner,
			assessment.PRACTITIONER_DEFAULT_FIELD,
			assessment.SOAP,
		)
		result = api.get_derma_assessment(encounter=encounter.name)
		self.assertEqual(result["mode"], assessment.SOAP)
		self.assertFalse(result["is_stamped"])


class TestAssessmentModeSwitching(AssessmentTestBase):
	def test_switch_preserves_the_other_format(self):
		encounter = self._draft_encounter()
		api.set_derma_assessment(
			payload=json.dumps({"custom_derma_soap_subjective": "Burning sensation"}),
			mode=assessment.SOAP,
			encounter=encounter.name,
		)
		api.set_derma_assessment_mode(assessment.STRUCTURED, encounter=encounter.name)
		result = api.get_derma_assessment(encounter=encounter.name)

		self.assertEqual(result["mode"], assessment.STRUCTURED)
		self.assertEqual(result["soap_values"]["custom_derma_soap_subjective"], "Burning sensation")

		api.set_derma_assessment_mode(assessment.SOAP, encounter=encounter.name)
		restored = api.get_derma_assessment(encounter=encounter.name)
		self.assertEqual(restored["soap_values"]["custom_derma_soap_subjective"], "Burning sensation")

	def test_switch_refused_on_submitted_encounter(self):
		encounter = self._make_encounter(self._make_patient(), docstatus=1)
		with self.assertRaises(frappe.ValidationError):
			api.set_derma_assessment_mode(assessment.STRUCTURED, encounter=encounter.name)

	def test_unknown_mode_is_rejected(self):
		encounter = self._draft_encounter()
		with self.assertRaises(frappe.ValidationError):
			api.set_derma_assessment_mode("Freeform", encounter=encounter.name)

	def test_write_is_whitelisted_to_the_active_mode(self):
		"""A SOAP save must not be able to name an arbitrary encounter column."""
		encounter = self._draft_encounter()
		api.set_derma_assessment(
			payload=json.dumps(
				{
					"custom_derma_soap_objective": "Erythematous plaques",
					"status": "Cancelled",
				}
			),
			mode=assessment.SOAP,
			encounter=encounter.name,
		)
		self.assertNotEqual(frappe.db.get_value("Patient Encounter", encounter.name, "status"), "Cancelled")


class TestAssessmentAccessGate(AssessmentTestBase):
	def test_set_mode_requires_a_clinical_role(self):
		encounter = self._draft_encounter()
		frappe.set_user(self._make_limited_user())
		with self.assertRaises(frappe.PermissionError):
			api.set_derma_assessment_mode(assessment.STRUCTURED, encounter=encounter.name)

	def test_get_assessment_requires_a_clinical_role(self):
		frappe.set_user(self._make_limited_user())
		with self.assertRaises(frappe.PermissionError):
			api.get_derma_assessment(encounter="does-not-matter")
