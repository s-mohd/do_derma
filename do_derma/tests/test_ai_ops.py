from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from do_derma import documents, voice
from do_derma.assessment import HP, SOAP, SOAP_FIELDS
from do_derma.schema import ensure_derma_schema
from do_derma.tests.test_api import DermaTestHelpers
from do_derma.tests.test_voice import NOTE


def wav_bytes(seconds: float, rate: int = 16000) -> bytes:
	import struct

	frames = int(seconds * rate)
	header = b"RIFF" + struct.pack("<I", 36 + frames * 2) + b"WAVE" + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) + b"data" + struct.pack("<I", frames * 2)
	return header + b"\x00" * (frames * 2)


class TestAiOperations(DermaTestHelpers, IntegrationTestCase):
	"""Ledger, jobs, refine and Arabic documents - the delivery-grade layer on top of the scribe."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_derma_schema()
		documents.ensure_document_templates()

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")
		self.encounter = self._make_encounter(self._make_patient())

	def _enabled(self):
		return patch.object(voice, "_setting", side_effect=lambda name, default=None: {"enable_voice_scribe": 1, "llm_api_key": "k", "max_recording_minutes": 20}.get(name, default))

	def _llm(self, payload):
		fake = MagicMock(status_code=200)
		fake.json.return_value = {"model": "gpt-4o-test", "usage": {"prompt_tokens": 120, "completion_tokens": 80}, "choices": [{"message": {"content": json.dumps(payload)}}]}
		return patch.object(voice.requests, "post", return_value=fake)

	def _usage_rows(self, kind):
		return frappe.get_all("Derma AI Usage", filters={"encounter": self.encounter.name, "kind": kind}, fields=["status", "prompt_tokens", "completion_tokens", "model", "audio_seconds"])

	def test_wav_seconds_reads_the_header(self):
		self.assertEqual(voice.wav_seconds(wav_bytes(12.5)), 12.5)
		self.assertEqual(voice.wav_seconds(b"not a wav" * 4000), round(36000 / 32000, 1))

	def test_note_records_usage_with_tokens(self):
		with self._enabled(), self._llm(NOTE):
			voice.generate_note("Patient complains of itchy hands for two weeks after a new detergent.", encounter=self.encounter.name)
		rows = self._usage_rows("Note")
		self.assertEqual(len(rows), 1)
		self.assertEqual((rows[0].status, rows[0].prompt_tokens, rows[0].completion_tokens, rows[0].model), ("Success", 120, 80, "gpt-4o-test"))

	def test_queued_note_runs_inline_in_tests_and_reports_done(self):
		with self._enabled(), self._llm(NOTE):
			job = voice.queue_note("Patient complains of itchy hands for two weeks after a new detergent.", encounter=self.encounter.name)["job"]
			status = voice.job_status(job)
		self.assertEqual(status["status"], "done")
		self.assertEqual(status["result"]["values"][SOAP_FIELDS[0]], NOTE["subjective"])

	def test_failed_job_reports_the_error(self):
		with self._enabled():
			job = voice.queue_note("hi", encounter=self.encounter.name)["job"]
			status = voice.job_status(job)
		self.assertEqual(status["status"], "failed")
		self.assertIn("too short", status["error"])

	def test_refine_rewrites_only_the_active_format(self):
		frappe.db.set_value("Patient Encounter", self.encounter.name, {SOAP_FIELDS[3]: "Emollients.", "custom_derma_assessment_mode": SOAP})
		with self._enabled(), self._llm({"Subjective": "", "Objective": "", "Assessment": "", "Plan": "Emollients. Review in 2 weeks."}) as post:
			out = voice.refine_note("add a 2-week follow-up", encounter=self.encounter.name)
		self.assertIn("INSTRUCTION: add a 2-week follow-up", post.call_args.kwargs["json"]["messages"][1]["content"])
		self.assertEqual(out["mode"], SOAP)
		self.assertEqual(frappe.db.get_value("Patient Encounter", self.encounter.name, SOAP_FIELDS[3]), "Emollients. Review in 2 weeks.")
		self.assertEqual(self._usage_rows("Refine")[0].status, "Success")

	def test_refine_refuses_structured_and_empty_notes(self):
		with self._enabled():
			with self.assertRaises(frappe.ValidationError):
				voice.refine_note("shorten it", encounter=self.encounter.name)
		frappe.db.set_value("Patient Encounter", self.encounter.name, "custom_derma_assessment_mode", HP)
		with self._enabled():
			with self.assertRaises(frappe.ValidationError):
				voice.refine_note("shorten it", encounter=self.encounter.name)

	def test_document_keeps_arabic_and_records_usage(self):
		with self._enabled(), self._llm({"text": "## Symptoms\n- itch", "text_ar": "## الأعراض\n- حكة"}):
			out = documents.generate_document("education", self.encounter.name)
		self.assertEqual(out["body_ar"], "## الأعراض\n- حكة")
		self.assertEqual(self._usage_rows("Document")[0].prompt_tokens, 120)
		letter = frappe.get_doc("Patient Official Document", out["name"])
		letter.values_json = json.dumps({**letter.get_values(), "language": "Both"})
		letter.save(ignore_permissions=True)
		with patch("do_health.do_health.doctype.patient_official_document.patient_official_document.get_pdf", return_value=b"%PDF-1.4\n%%EOF\n"), patch("frappe.core.doctype.file.file.File.check_content", return_value=None):
			issued = documents.issue_document(out["name"])
		html = frappe.db.get_value("Patient Official Document", issued["name"], "rendered_html_snapshot")
		self.assertIn('dir="rtl"', html)
		self.assertIn("الأعراض", html)

	def test_prompts_name_the_company_not_a_hardcoded_clinic(self):
		company = frappe.db.get_value("Company", self.encounter.company, "company_name")
		self.assertIn(company, voice.note_system_prompt(self.encounter.company))
		self.assertNotIn("DermaOne", voice.note_system_prompt(self.encounter.company))
