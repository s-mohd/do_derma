from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma.patches.cleanup_derma_allowed_body_regions import (
	FIELDNAME as ALLOWED_BODY_REGIONS,
)
from do_derma.patches.cleanup_derma_allowed_body_regions import (
	execute as cleanup_allowed_body_regions,
)
from do_derma.tests.test_api import DermaTestHelpers
from do_derma.tests.test_config_workspace import ConfigTemplateHelpers


class TestBodyTemplateScope(ConfigTemplateHelpers, DermaTestHelpers, IntegrationTestCase):
	"""`custom_derma_allowed_body_templates` used to be a hint buried in the chart's
	auto-select fallback, so nothing refused a face procedure charted on a foot map.
	The mark write is now the gate."""

	def setUp(self):
		self.patient = self._make_patient()
		self.allowed_map = self._make_body_template()
		self.other_map = self._make_body_template()
		if not api._has_field("Clinical Procedure Template", "custom_derma_allowed_body_templates"):
			self.skipTest("Clinical Procedure Template.custom_derma_allowed_body_templates is missing")

	def test_a_body_map_outside_the_allowed_list_is_refused(self):
		procedure = self._make_derma_template(custom_derma_allowed_body_templates=self.allowed_map)

		with self.assertRaises(frappe.ValidationError):
			self._save_mark(self.patient, procedure_template=procedure, body_template=self.other_map)

	def test_the_refusal_names_the_procedure_and_the_body_map(self):
		procedure = self._make_derma_template(custom_derma_allowed_body_templates=self.allowed_map)

		with self.assertRaises(frappe.ValidationError) as caught:
			self._save_mark(self.patient, procedure_template=procedure, body_template=self.other_map)

		message = str(caught.exception)
		self.assertIn(procedure, message)
		self.assertIn(self.other_map, message)

	def test_an_allowed_body_map_is_saved(self):
		procedure = self._make_derma_template(
			custom_derma_allowed_body_templates=f"{self.allowed_map}, {self.other_map}"
		)

		saved = self._save_mark(self.patient, procedure_template=procedure, body_template=self.other_map)

		self.assertEqual(saved["body_template"], self.other_map)

	def test_an_empty_allowed_list_permits_every_body_map(self):
		procedure = self._make_derma_template(custom_derma_allowed_body_templates="")

		saved = self._save_mark(self.patient, procedure_template=procedure, body_template=self.other_map)

		self.assertEqual(saved["body_template"], self.other_map)

	def test_a_mark_with_no_procedure_template_is_unrestricted(self):
		saved = self._save_mark(self.patient, body_template=self.other_map)

		self.assertEqual(saved["body_template"], self.other_map)

	def test_promoting_a_mark_to_a_procedure_checks_the_map_too(self):
		"""`create_procedure_from_mark` writes the mark itself, so a body map that was allowed
		when the mark was placed - or that reached the mark another way - is re-checked here."""
		procedure = self._make_derma_template(custom_derma_allowed_body_templates=self.allowed_map)
		mark = self._save_mark(
			self.patient,
			encounter=self._make_encounter(self.patient).name,
			procedure_template=procedure,
			body_template=self.allowed_map,
		)
		frappe.db.set_value("Derma Chart Mark", mark["name"], "body_template", self.other_map)

		with self.assertRaises(frappe.ValidationError) as caught:
			# The endpoint demands an appointment-linked encounter before it reads the template.
			# It is applied to the in-memory mark and the throw lands before anything is saved.
			api.create_procedure_from_mark(mark["name"], procedure, {"appointment": "not-saved"})

		self.assertIn("cannot be charted on", str(caught.exception))

	def test_the_list_is_read_the_way_a_clinic_types_it(self):
		"""Free text typed into a Small Text field, so spacing and case are the admin's."""
		procedure = self._make_derma_template(
			custom_derma_allowed_body_templates=f"  {self.allowed_map.upper()} ,"
		)

		saved = self._save_mark(self.patient, procedure_template=procedure, body_template=self.allowed_map)

		self.assertEqual(saved["body_template"], self.allowed_map)


class TestAllowedBodyRegionsCleanup(IntegrationTestCase):
	"""The field had zero readers in either layer; once marks link to a body template
	part the part list is the only expression of region scope."""

	def test_the_custom_field_is_gone_after_the_patch(self):
		cleanup_allowed_body_regions()

		self.assertFalse(
			frappe.db.exists(
				"Custom Field", {"dt": "Clinical Procedure Template", "fieldname": ALLOWED_BODY_REGIONS}
			)
		)

	def test_a_second_run_writes_nothing(self):
		cleanup_allowed_body_regions()
		cleanup_allowed_body_regions()

		self.assertFalse(api._has_field("Clinical Procedure Template", ALLOWED_BODY_REGIONS))

	def test_the_chart_no_longer_selects_the_field(self):
		self.assertNotIn(ALLOWED_BODY_REGIONS, api.DERMA_TEMPLATE_FIELDS)
