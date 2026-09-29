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

	def test_a_legacy_consent_without_a_procedure_opens_unchanged(self):
		if not frappe.db.exists("DocType", consent.CONSENT_FORM):
			self.skipTest("Consent Form is not installed.")
		legacy = frappe.get_doc(
			{
				"doctype": consent.CONSENT_FORM,
				"patient": self.patient,
				"rendered_html": "<p>old</p>",
				"signature": SIGNATURE,
				"signed_by": "Test Patient",
			}
		).insert(ignore_permissions=True)
		legacy.submit()
		self.assertEqual(api.get_derma_consent_html(legacy.name)["rendered_html"], "<p>old</p>")

	def test_render_context_joins_the_procedure_names(self):
		doc = frappe.new_doc(self.consent_doctype.name)
		doc.patient = self.patient
		context = consent.get_render_context(doc, [{"display_name": "Laser"}, {"display_name": "Peel"}])
		self.assertEqual(context["procedure_names"], ["Laser", "Peel"])
		self.assertEqual(context["procedure"], "Laser, Peel")
		self.assertEqual(context["procedure_name"], "Laser, Peel")


class TestCreateConsent(ConsentHelpers, IntegrationTestCase):
	def _stored_procedures(self, name):
		doc = frappe.get_doc(self.consent_doctype.name, name)
		return [row.clinical_procedure for row in doc.get(self.consent_doctype.procedures_field)]

	def test_one_consent_covers_every_selected_procedure(self):
		created = self._create([self.first, self.second])
		self.assertEqual(self._stored_procedures(created["name"]), [self.first.name, self.second.name])
		self.assertEqual(created["docstatus"], 1)

	def test_consent_form_keeps_the_first_procedure_on_its_own_link(self):
		if self.consent_doctype.is_encounter_consent:
			self.skipTest("Encounter Consent has no single procedure link.")
		created = self._create([self.first, self.second])
		self.assertEqual(
			frappe.db.get_value(consent.CONSENT_FORM, created["name"], "clinical_procedure"), self.first.name
		)

	def test_a_procedure_picked_twice_is_stored_once(self):
		created = self._create([self.first, self.first])
		self.assertEqual(self._stored_procedures(created["name"]), [self.first.name])

	def test_a_consent_needs_at_least_one_procedure(self):
		with self.assertRaisesRegex(frappe.ValidationError, "at least one procedure"):
			self._create([])

	def test_a_procedure_from_another_visit_is_refused(self):
		other = self._make_visit_procedure(self._make_encounter(self.patient))
		with self.assertRaisesRegex(frappe.ValidationError, "not part of this visit"):
			self._create([self.first, other])

	def test_a_procedure_of_another_patient_is_refused(self):
		stranger = self._make_patient()
		procedure = self._make_clinical_procedure(stranger)
		procedure.db_set(api._get_clinical_procedure_encounter_field(), self.encounter.name)
		with self.assertRaisesRegex(frappe.ValidationError, "not part of this visit"):
			self._create([self.first, procedure])

	def test_a_cancelled_procedure_is_refused(self):
		self.second.db_set("docstatus", 2)
		with self.assertRaisesRegex(frappe.ValidationError, "not part of this visit"):
			self._create([self.first, self.second])

	def test_renders_every_selected_procedure(self):
		created = self._create([self.first, self.second])
		html = frappe.db.get_value(created["doctype"], created["name"], "rendered_html")
		self.assertIn(f"Shown {self.first.name};", html)
		self.assertIn(f"Shown {self.second.name};", html)

	def test_preview_renders_the_selected_procedures(self):
		result = api.render_derma_consent_preview(payload=json.dumps(self._payload([self.first, self.second])))
		self.assertIn(f"Shown {self.first.name};Shown {self.second.name};", result["rendered_html"])


class TestChartConsentState(ConsentHelpers, IntegrationTestCase):
	def _rows(self):
		rows = api._get_derma_procedures(self.patient, encounter=self.encounter.name)
		return {row["name"]: row for row in rows}

	def test_rows_list_the_consents_covering_them(self):
		created = self._create([self.first])
		rows = self._rows()
		self.assertEqual([row["name"] for row in rows[self.first.name]["consents"]], [created["name"]])
		self.assertEqual(rows[self.second.name]["consents"], [])

	def test_rows_say_whether_their_template_requires_consent(self):
		fieldname = "custom_derma_consent_required"
		template = self.first.procedure_template
		previous = frappe.db.get_value("Clinical Procedure Template", template, fieldname)
		self.addCleanup(frappe.db.set_value, "Clinical Procedure Template", template, fieldname, previous)
		frappe.db.set_value("Clinical Procedure Template", template, fieldname, 1)

		self.assertEqual(self._rows()[self.first.name]["consent_required"], 1)

	def test_a_covered_procedure_cannot_be_deleted(self):
		self._create([self.first])
		with self.assertRaisesRegex(frappe.ValidationError, "signed consent covers"):
			api.delete_clinical_procedure_entry("Clinical Procedure", self.first.name)
		self.assertTrue(frappe.db.exists("Clinical Procedure", self.first.name))


class TestWaivedConsent(ConsentHelpers, IntegrationTestCase):
	def _waive(self, procedures, reason="Signed on paper"):
		return self._create(
			procedures, signature="", signed_by="", signature_waived=1, waiver_reason=reason
		)

	def test_a_waived_consent_is_kept_as_a_draft_with_its_reason(self):
		created = self._waive([self.first], reason="Verbal")
		doc = frappe.get_doc(created["doctype"], created["name"])
		self.assertEqual(doc.docstatus, 0)
		self.assertEqual(doc.custom_derma_signature_waived, 1)
		self.assertEqual(doc.custom_derma_waiver_reason, "Verbal")

	def test_a_waived_consent_covers_its_procedures(self):
		created = self._waive([self.first, self.second])
		coverage = consent.get_consent_coverage([self.first.name, self.second.name])
		for procedure in (self.first.name, self.second.name):
			self.assertEqual([row["name"] for row in coverage[procedure]], [created["name"]])
			self.assertEqual(coverage[procedure][0]["custom_derma_signature_waived"], 1)

	def test_a_waiver_needs_a_reason(self):
		with self.assertRaisesRegex(frappe.ValidationError, "reason"):
			self._waive([self.first], reason="   ")

	def test_markup_in_a_reason_is_dropped(self):
		created = self._waive([self.first], reason="Emergency <b>test</b>")
		values = frappe.db.get_value(
			created["doctype"], created["name"], ["custom_derma_waiver_reason", "rendered_html"], as_dict=True
		)
		self.assertEqual(values.custom_derma_waiver_reason, "Emergency test")
		self.assertIn("Signature waived: Emergency test", values.rendered_html)
		self.assertNotIn("&lt;", values.rendered_html)

	def test_a_reason_that_is_only_markup_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "reason"):
			self._waive([self.first], reason="<b></b>")

	def test_without_a_waiver_a_signature_is_still_required(self):
		with self.assertRaises(frappe.ValidationError):
			self._create([self.first], signature="", signed_by="")
