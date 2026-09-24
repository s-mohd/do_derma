from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from do_derma import voice
from do_derma.assessment import HP_FIELDS, SOAP_FIELDS
from do_derma.schema import ensure_derma_schema
from do_derma.tests.test_api import DermaTestHelpers

NOTE = {
	"subjective": "Itchy rash on both hands for two weeks after a new detergent.",
	"objective": "Erythematous scaly plaques on the dorsal hands, no vesicles.",
	"assessment": "Irritant contact dermatitis.",
	"plan": "Avoid the detergent; mometasone 0.1% cream twice daily for 2 weeks.",
	"chief_complaint": "Itchy rash on both hands.",
	"history_of_presenting_complaint": "Two weeks, after a new detergent.",
	"past_medical_history": "Not discussed.",
	"examination_findings": "Erythematous scaly plaques on the dorsal hands.",
	"hp_assessment": "Irritant contact dermatitis.",
	"management_plan": "Avoid the detergent; mometasone cream.",
	"diagnosis": "Irritant contact dermatitis",
	"icd10": "L24.0 - Irritant contact dermatitis due to detergents",
	"soap_ar": "الشكوى والتاريخ: طفح جلدي",
	"followup_en": "Hi, please avoid the detergent.",
	"followup_ar": "مرحباً، يرجى تجنب المنظف.",
}


class TestSafeParseJSON(IntegrationTestCase):
	def test_plain_and_fenced_and_chatter(self):
		body = json.dumps(NOTE)
		self.assertEqual(voice.safe_parse_json(body), NOTE)
		self.assertEqual(voice.safe_parse_json(f"```json\n{body}\n```"), NOTE)
		self.assertEqual(voice.safe_parse_json(f"Here is the note:\n{body}\nDone."), NOTE)

	def test_garbage_is_none(self):
		self.assertIsNone(voice.safe_parse_json(""))
		self.assertIsNone(voice.safe_parse_json("no json here"))
		self.assertIsNone(voice.safe_parse_json("[1, 2]"))


class TestPrompt(IntegrationTestCase):
	def test_prompt_carries_context_and_transcript(self):
		prompt = voice.build_note_prompt(
			"patient says itchy hands",
			patient={"name": "Amina", "age": 34, "gender": "Female"},
			previous="Last visit (2026-08-01): acne | Plan: doxycycline",
			clinician={"name": "Dr. Abdulla Sadeq", "title": "Consultant"},
		)
		for needle in ("Name: Amina", "Age: 34", "Gender: Female", "CLINICIAN: Dr. Abdulla Sadeq (Consultant)", "doxycycline", "itchy hands"):
			self.assertIn(needle, prompt)
		self.assertNotIn("dermatologist", voice.build_note_prompt("itchy hands", clinician={"name": "Dr. A", "title": ""}))


class TestGenerateNote(DermaTestHelpers, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_derma_schema()

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")
		self.encounter = self._make_encounter(self._make_patient())

	def _enabled(self):
		return patch.object(voice, "_setting", side_effect=lambda name, default=None: {"enable_voice_scribe": 1, "llm_api_key": "test-key"}.get(name, default))

	def test_disabled_raises(self):
		with patch.object(voice, "_setting", return_value=0):
			with self.assertRaises(frappe.ValidationError):
				voice.generate_note("long enough transcript for the guard", encounter=self.encounter.name)

	def test_generates_soap_values_and_stores_transcript(self):
		fake = MagicMock(status_code=200)
		fake.json.return_value = {"choices": [{"message": {"content": json.dumps(NOTE)}}]}
		transcript = "Patient complains of itchy hands for two weeks after using a new detergent."
		with self._enabled(), patch.object(voice.requests, "post", return_value=fake) as post:
			out = voice.generate_note(transcript, encounter=self.encounter.name)
		sent = post.call_args.kwargs["json"]
		self.assertEqual(sent["messages"][0]["content"], voice.note_system_prompt(self.encounter.company))
		self.assertNotIn("{clinic}", sent["messages"][0]["content"])
		self.assertIn(transcript, sent["messages"][1]["content"])
		self.assertEqual(out["encounter"], self.encounter.name)
		self.assertEqual(out["values"][SOAP_FIELDS[0]], NOTE["subjective"])
		self.assertEqual(out["values"][SOAP_FIELDS[3]], NOTE["plan"])
		self.assertEqual(out["icd10"], NOTE["icd10"])
		self.assertEqual(out["hp_values"][HP_FIELDS[0]], NOTE["chief_complaint"])
		self.assertEqual(out["hp_values"][HP_FIELDS[5]], NOTE["management_plan"])
		self.assertEqual(out["followup_ar"], NOTE["followup_ar"])
		self.assertEqual(
			frappe.db.get_value("Patient Encounter", self.encounter.name, voice.TRANSCRIPT_FIELD), transcript
		)
		saved = frappe.db.get_value(
			"Patient Encounter",
			self.encounter.name,
			[voice.PATIENT_ADVICE_FIELD, voice.PATIENT_ADVICE_AR_FIELD, "custom_derma_print_patient_advice"],
			as_dict=True,
		)
		self.assertEqual(saved[voice.PATIENT_ADVICE_FIELD], NOTE["followup_en"])
		self.assertEqual(saved[voice.PATIENT_ADVICE_AR_FIELD], NOTE["followup_ar"])
		self.assertEqual(saved["custom_derma_print_patient_advice"], 0)  # opt-in, never printed by default

	def test_unparseable_reply_raises(self):
		fake = MagicMock(status_code=200)
		fake.json.return_value = {"choices": [{"message": {"content": "sorry, cannot help"}}]}
		with self._enabled(), patch.object(voice.requests, "post", return_value=fake):
			with self.assertRaises(frappe.ValidationError):
				voice.generate_note("Patient complains of itchy hands for two weeks.", encounter=self.encounter.name)

	def test_short_transcript_raises(self):
		with self._enabled():
			with self.assertRaises(frappe.ValidationError):
				voice.generate_note("hi", encounter=self.encounter.name)
