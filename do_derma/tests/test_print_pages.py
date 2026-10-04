from __future__ import annotations

import json

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma import consent
from do_derma.schema import ensure_derma_schema
from do_derma.tests.test_api import PIXEL_PNG, TEMPLATE_ELEMENT
from do_derma.tests.test_consent import SIGNATURE, ConsentHelpers
from do_derma.tests.test_letterhead import SIGNATURE_SRC, LetterHeadHelpers


class TestPrintPages(LetterHeadHelpers, ConsentHelpers, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_derma_schema()

	def setUp(self):
		super().setUp()
		self._make_letter_head(is_default=1)
		self.own = self._make_letter_head()
		self.practitioner = self._make_marked_practitioner(letter_head=self.own.name)
		self.encounter.db_set("practitioner", self.practitioner.name)

	def _assert_on_the_practitioners_letter_head(self, html):
		self.assertIn(self.own.content, html)
		self.assertIn(self.own.footer, html)
		self.assertIn(SIGNATURE_SRC, html)

	def test_consent_page_has_identity_body_and_mark(self):
		created = self._create([self.first])
		page = api.get_derma_print_html("consent", created["name"])
		self.assertIn(self.template, page["title"])
		self.assertIn(f"MRN: {self.patient}", page["html"])
		self.assertIn(self.encounter.name, page["html"])
		self.assertIn(f"Shown {self.first.name}", page["html"])
		self._assert_on_the_practitioners_letter_head(page["html"])

	def test_a_legacy_consent_takes_the_procedures_practitioner(self):
		if not frappe.db.exists("DocType", consent.CONSENT_FORM):
			self.skipTest("Consent Form is not installed.")
		self.first.db_set("practitioner", self.practitioner.name)
		legacy = frappe.get_doc(
			{
				"doctype": consent.CONSENT_FORM,
				"patient": self.patient,
				"clinical_procedure": self.first.name,
				"rendered_html": "<p>legacy body</p>",
				"signature": SIGNATURE,
				"signed_by": "Test Patient",
			}
		).insert(ignore_permissions=True)
		html = api.get_derma_print_html("consent", legacy.name)["html"]
		self.assertIn("<p>legacy body</p>", html)
		self._assert_on_the_practitioners_letter_head(html)

	def test_blank_consent_wraps_the_unsaved_body(self):
		page = api.get_derma_print_html("blank_consent", self.encounter.name, "<p>Blank body</p>")
		self.assertIn("<p>Blank body</p>", page["html"])
		self.assertIn(f"MRN: {self.patient}", page["html"])
		self._assert_on_the_practitioners_letter_head(page["html"])

	def test_blank_consent_without_a_body_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			api.get_derma_print_html("blank_consent", self.encounter.name, " ")

	def _make_annotation(self, title):
		name = api.save_derma_annotation(
			{
				"patient": self.patient,
				"encounter": self.encounter.name,
				"file_data": PIXEL_PNG,
				"json_text": json.dumps({"elements": [TEMPLATE_ELEMENT]}),
			}
		)["name"]
		# The label's fallback field: do_derma's own title field is optional and absent on some sites.
		frappe.db.set_value("Health Annotation", name, "annotation_template", title)
		frappe.db.set_value("Health Annotation Table", {"annotation": name}, "annotation_data", "<b>Legend</b>")
		return name

	def test_annotation_page_has_image_legend_and_mark(self):
		name = self._make_annotation("Face")
		page = api.get_derma_print_html("annotation", name)
		image = frappe.db.get_value("Health Annotation", name, "image")
		self.assertIn(image, page["html"])
		self.assertIn("<b>Legend</b>", page["html"])
		self.assertIn(f"MRN: {self.patient}", page["html"])
		self.assertIn("Face", page["title"])
		self._assert_on_the_practitioners_letter_head(page["html"])

	def test_annotation_page_escapes_the_label(self):
		page = api.get_derma_print_html("annotation", self._make_annotation("Face <front>"))
		self.assertIn("Face &lt;front&gt;", page["html"])
		self.assertNotIn("Face <front>", page["html"])

	def test_unknown_kind_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Unknown printable"):
			api.get_derma_print_html("invoice", self.encounter.name)

	def test_users_without_clinical_access_are_refused(self):
		frappe.set_user(self._make_limited_user())
		with self.assertRaises(frappe.PermissionError):
			api.get_derma_print_html("blank_consent", self.encounter.name, "<p>x</p>")
