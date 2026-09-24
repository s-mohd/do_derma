from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from do_derma import documents, voice
from do_derma.assessment import SOAP_FIELDS
from do_derma.schema import ensure_derma_schema
from do_derma.tests.test_api import DermaTestHelpers

def blank_pdf() -> bytes:
	from io import BytesIO

	from pypdf import PdfWriter

	writer = PdfWriter()
	writer.add_blank_page(width=595, height=842)
	buffer = BytesIO()
	writer.write(buffer)
	return buffer.getvalue()


REPORT = "## Patient Demographic Data\nName: Test\n## Medications\n- None documented\nDr. Abdulla Sadeq\nDermatologist"


class TestAiDocuments(DermaTestHelpers, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_derma_schema()
		documents.ensure_document_templates()

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")
		self.encounter = self._make_encounter(self._make_patient())
		frappe.db.set_value("Patient Encounter", self.encounter.name, SOAP_FIELDS[2], "Irritant contact dermatitis")
		self.encounter.reload()

	def _enabled(self):
		return patch.object(voice, "_setting", side_effect=lambda name, default=None: {"enable_voice_scribe": 1, "llm_api_key": "k"}.get(name, default))

	def _llm(self, text):
		fake = MagicMock(status_code=200)
		fake.json.return_value = {"choices": [{"message": {"content": json.dumps({"text": text})}}]}
		return patch.object(voice.requests, "post", return_value=fake)

	def test_templates_are_seeded_once(self):
		self.assertEqual(documents.ensure_document_templates(), [])
		for spec in documents.KINDS.values():
			self.assertTrue(frappe.db.exists("Patient Print Template", {"title": documents.TEMPLATE_PREFIX + spec["title"]}))

	def test_prompt_carries_note_diagnosis_and_addressee(self):
		context = documents.build_document_context(self.encounter, addressee="Dr. Salman")
		self.assertEqual(context["diagnosis"], "Irritant contact dermatitis")
		self.assertIn("Assessment: Irritant contact dermatitis", context["note"])
		prompt = documents.build_document_prompt("referral", context)
		self.assertIn("ADDRESSEE (referral recipient): Dr. Salman", prompt)
		self.assertIn("DOCUMENT REQUESTED: Referral Letter", prompt)

	def test_generate_creates_a_draft_official_document(self):
		with self._enabled(), self._llm(REPORT) as post:
			out = documents.generate_document("report", self.encounter.name)
		system = post.call_args.kwargs["json"]["messages"][0]["content"]
		self.assertNotIn("{clinic}", system)
		self.assertIn("Medical Report", system)
		doc = frappe.get_doc("Patient Official Document", out["name"])
		self.assertEqual(doc.document_type, "Medical Report")
		self.assertEqual(doc.status, "Draft")
		self.assertEqual(doc.encounter, self.encounter.name)
		self.assertEqual(doc.get_values()["body"], REPORT)
		self.assertEqual(out["title"], "Medical Report")
		listed = documents.list_documents(self.encounter.name)
		self.assertEqual([row["name"] for row in listed], [out["name"]])

	def test_issue_renders_body_and_attaches_pdf(self):
		with self._enabled(), self._llm(REPORT):
			out = documents.generate_document("education", self.encounter.name)
		with patch("do_health.do_health.doctype.patient_official_document.patient_official_document.get_pdf", return_value=blank_pdf()):
			issued = documents.issue_document(out["name"])
		self.assertEqual(issued["status"], "Issued")
		self.assertTrue(issued["pdf_url"])
		html = frappe.db.get_value("Patient Official Document", out["name"], "rendered_html_snapshot")
		self.assertIn("<h2", html)
		self.assertIn("Patient Demographic Data", html)
		self.assertIn("&bull; None documented", html)

	def test_unknown_kind_and_disabled_are_refused(self):
		with self._enabled():
			with self.assertRaises(frappe.ValidationError):
				documents.generate_document("poem", self.encounter.name)
		with patch.object(voice, "_setting", return_value=0):
			with self.assertRaises(frappe.ValidationError):
				documents.generate_document("report", self.encounter.name)
