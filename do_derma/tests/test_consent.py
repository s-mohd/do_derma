from __future__ import annotations

import json

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma import consent, schema
from do_derma.tests.test_api import DermaTestHelpers

SIGNATURE = "data:image/png;base64,iVBORw0KGgo="
TEMPLATE_HTML = "<p>{{ patient_name }}: {% for row in procedures %}{{ row.display_name }};{% endfor %}</p>"


class TestConsentSchema(IntegrationTestCase):
	def test_consent_form_carries_the_procedure_table(self):
		if not frappe.db.exists("DocType", "Consent Form"):
			self.skipTest("Consent Form is not installed.")
		schema.ensure_derma_schema()
		field = frappe.get_meta("Consent Form").get_field("custom_derma_procedures")
		self.assertIsNotNone(field)
		self.assertEqual((field.fieldtype, field.options), ("Table", "Derma Consent Procedure"))


class ConsentHelpers(DermaTestHelpers):
	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")
		self.consent_doctype = consent.ConsentDoctype()
		if not self.consent_doctype.is_installed:
			self.skipTest("No consent doctype installed.")
		self.patient = self._make_patient()
		self.encounter = self._make_encounter(self.patient)
		self.first = self._make_visit_procedure()
		self.second = self._make_visit_procedure()
		self.template = self._make_consent_template()

	def _make_visit_procedure(self, encounter=None):
		procedure = self._make_clinical_procedure(self.patient)
		procedure.db_set(api._get_clinical_procedure_encounter_field(), (encounter or self.encounter).name)
		return procedure

	def _make_consent_template(self):
		return (
			frappe.get_doc(
				{
					"doctype": "Consent Form Template",
					"title": f"Derma Test {frappe.generate_hash(length=6)}",
					"language": "en",
					"version": 1,
					"template_html": TEMPLATE_HTML,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _payload(self, procedures, **extra):
		return {
			"patient": self.patient,
			"encounter": self.encounter.name,
			"consent_form_template": self.template,
			"signed_by": "Test Patient",
			"signature": SIGNATURE,
			"procedure_items": [
				{"clinical_procedure": row.name, "display_name": f"Shown {row.name}"} for row in procedures
			],
			**extra,
		}

	def _create(self, procedures, **extra):
		return api.create_derma_consent(payload=json.dumps(self._payload(procedures, **extra)))


class TestConsentCoverage(ConsentHelpers, IntegrationTestCase):
	def test_coverage_lists_every_covered_procedure(self):
		third = self._make_visit_procedure()
		created = self._create([self.first, self.second])

		coverage = consent.get_consent_coverage([self.first.name, self.second.name, third.name])

		self.assertEqual([row["name"] for row in coverage[self.first.name]], [created["name"]])
		self.assertEqual([row["name"] for row in coverage[self.second.name]], [created["name"]])
		self.assertNotIn(third.name, coverage)

	def test_a_draft_consent_covers_nothing(self):
		frappe.get_doc(
			{
				"doctype": self.consent_doctype.name,
				"patient": self.patient,
				"signature": SIGNATURE,
				"signed_by": "Test Patient",
				self.consent_doctype.procedures_field: [{"clinical_procedure": self.first.name}],
			}
		).insert(ignore_permissions=True)
		self.assertEqual(consent.get_consent_coverage([self.first.name]), {})

	def test_a_cancelled_consent_covers_nothing(self):
		created = self._create([self.first])
		frappe.get_doc(created["doctype"], created["name"]).cancel()
		self.assertEqual(consent.get_consent_coverage([self.first.name]), {})

	def test_a_legacy_consent_with_only_its_procedure_link_still_counts(self):
		if not frappe.db.exists("DocType", consent.CONSENT_FORM):
			self.skipTest("Consent Form is not installed.")
		legacy = frappe.get_doc(
			{
				"doctype": consent.CONSENT_FORM,
				"patient": self.patient,
				"clinical_procedure": self.first.name,
				"rendered_html": "<p>legacy</p>",
				"signature": SIGNATURE,
				"signed_by": "Test Patient",
			}
		).insert(ignore_permissions=True)
		legacy.submit()

		coverage = consent.get_consent_coverage([self.first.name])

		self.assertEqual([row["name"] for row in coverage[self.first.name]], [legacy.name])
		self.assertEqual(api.get_derma_consent_html(legacy.name)["rendered_html"], "<p>legacy</p>")

	def test_render_context_joins_the_procedure_names(self):
		doc = frappe.new_doc(self.consent_doctype.name)
		doc.patient = self.patient
		context = consent.get_render_context(doc, [{"display_name": "Laser"}, {"display_name": "Peel"}])
		self.assertEqual(context["procedure_names"], ["Laser", "Peel"])
		self.assertEqual(context["procedure"], "Laser, Peel")
		self.assertEqual(context["procedure_name"], "Laser, Peel")
