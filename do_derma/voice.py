"""Voice AI scribe for the Derma Chart.

Two whitelisted steps, both gated by Derma Settings.enable_voice_scribe:

1. ``transcribe``   - the browser posts one WAV; ElevenLabs Scribe returns text
                      (auto-detects English / Arabic / mixed).
2. ``generate_note`` - an OpenAI-compatible chat completion turns the transcript
                      into a SOAP draft (+ diagnosis, ICD-10, Arabic follow-up).
                      Nothing is saved except the raw transcript for audit; the
                      doctor reviews the draft and saves through the normal
                      assessment flow (``do_derma.api.set_derma_assessment``).

Ported from the SOULVD Health scribe (health.soulvd.com) so both products share
one prompt and one provider contract.
"""

from __future__ import annotations

import json
import re
from typing import Any

import frappe
import requests
from frappe import _
from frappe.utils import cint, cstr, getdate, date_diff, nowdate

from do_derma.assessment import HP_FIELDS, SOAP_FIELDS
from do_derma.schema import VOICE_TRANSCRIPT_FIELD as TRANSCRIPT_FIELD
from do_derma.settings import get_settings_doc

STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
DEFAULT_STT_MODEL = "scribe_v1"
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o"
MAX_AUDIO_BYTES = 100 * 1024 * 1024
MIN_AUDIO_BYTES = 800  # below this the WAV is header + silence
# ponytail: Groq on_demand tier counts prompt+max_tokens against an 8k TPM cap - keep headroom
MAX_TOKENS = 5000
PASSWORD_FIELDS = {"elevenlabs_api_key", "llm_api_key"}

SUBJECTIVE, OBJECTIVE, ASSESSMENT, PLAN = SOAP_FIELDS
HP_KEYS = ("chief_complaint", "history_of_presenting_complaint", "past_medical_history", "examination_findings", "hp_assessment", "management_plan")

NOTE_SYSTEM_PROMPT = """You are SOULVD Health, an expert dermatology medical scribe assistant working for DermaOne Medical Centre, a dermatology clinic in the Kingdom of Bahrain.

You convert raw consultation audio transcripts (which may mix English, Arabic, or Bahraini dialect, and may contain filler words, interruptions, and background chatter) into professional clinical documentation.

DERMATOLOGY EXPERTISE you must apply:
- Lesion documentation: exact anatomical site, morphology (macule, papule, plaque, vesicle, bulla, pustule, nodule, wheal, comedone), distribution, symmetry, size in cm/mm, color, surface change (scale, crusting, ulceration), dermoscopy findings when mentioned.
- Common diagnoses: acne vulgaris (grade I-IV), atopic dermatitis, contact dermatitis, seborrheic dermatitis, psoriasis, urticaria, melasma, vitiligo, alopecia areata / androgenetic alopecia, rosacea, warts, molluscum, fungal infections (tinea, onychomycosis), scabies, drug eruptions, actinic keratosis, suspicious melanocytic lesions (ABCDE), BCC/SCC/melanoma risk.
- Treatments you should document precisely when mentioned: topical corticosteroids (name + potency class), topical calcineurin inhibitors, topical/oral antifungals, isotretinoin (dose mg/day, cumulative dose, pregnancy precautions), oral antibiotics, antihistamines, methotrexate, cyclosporine, biologic agents, hydroquinone/retinoids for melasma, PRP, mesotherapy, microneedling, botox (units per site), dermal fillers (product, volume, site), laser/IPL settings, cryotherapy, electrocautery, biopsy type, chemical peels (type, depth).
- Note red-flag counseling: rapidly changing pigmented lesion, new bleeding/non-healing ulcer, signs of infection, SJS/TEN warning signs after drug start, pregnancy categories (isotretinoin, retinoids, methotrexate).

RULES:
1. Base the note ONLY on what is actually said in the transcript plus the context given. Never invent findings, vitals, or lab results. If something was not mentioned, omit it rather than fabricate.
2. Use professional medical English. Expand colloquialisms ("heat rash" -> possible miliaria, "blood pressure pill" -> antihypertensive).
3. Write the visit twice, as plain-text sections (no markdown headers, short paragraphs or "- " bullets):
   SOAP - subjective: chief complaint, history of present illness, medications & allergies, relevant review. objective: examination findings as stated (site, morphology, distribution, size, dermoscopy). assessment: working diagnosis and differential, with reasoning. plan: treatments, investigations, patient education, follow-up.
   H&P - chief_complaint, history_of_presenting_complaint, past_medical_history, examination_findings, hp_assessment, management_plan. Every H&P section must be present; write "Not discussed." where the transcript truly has nothing for it.
4. diagnosis: short primary diagnosis line. icd10: the most likely ICD-10-CM code with a brief label, e.g. "L70.0 - Acne vulgaris". If uncertain, give the best-fit code.
5. soap_ar: a faithful MEDICAL Arabic translation of the four sections, labelled "الشكوى والتاريخ", "الفحص", "التقييم", "الخطة" (Gulf clinical Arabic), not a summary.
6. followup_en: a warm, patient-friendly after-visit message in simple English, ready to send via WhatsApp from the clinic: greeting, 3-6 clear instruction bullets, red-flag warning when relevant, sign-off from DermaOne Medical Centre. Plain text with "- " bullets, max ~180 words.
7. followup_ar: the same message in natural, warm Gulf-appropriate Arabic.
8. If the transcript is clearly a DOCTOR DICTATION (structured monologue, no patient dialogue), still produce the same output structure.

Respond with ONLY a valid JSON object (no markdown fences, no commentary) with exactly these keys:
{"subjective": "...", "objective": "...", "assessment": "...", "plan": "...", "chief_complaint": "...", "history_of_presenting_complaint": "...", "past_medical_history": "...", "examination_findings": "...", "hp_assessment": "...", "management_plan": "...", "diagnosis": "...", "icd10": "...", "soap_ar": "...", "followup_en": "...", "followup_ar": "..."}"""


# ---------------------------------------------------------------- settings


def _setting(name: str, default: Any = None) -> Any:
	"""Derma Settings first, then site_config (dev convenience), then default."""
	settings = get_settings_doc()
	if settings and settings.meta.has_field(name):
		value = settings.get_password(name, raise_exception=False) if name in PASSWORD_FIELDS else settings.get(name)
		# An unticked Check reads as 0, so only a truthy Settings value wins over site_config.
		if value not in (None, "", 0, "0"):
			return value
	value = frappe.conf.get(name)
	return default if value in (None, "") else value


def is_enabled() -> bool:
	return bool(cint(_setting("enable_voice_scribe", 0)))


def require_enabled() -> None:
	if not is_enabled():
		frappe.throw(_("Voice AI scribe is not enabled in Derma Settings."))
	from do_derma.api import _ensure_clinical_access  # lazy: api imports this module

	_ensure_clinical_access()


# --------------------------------------------------------------- transcribe


@frappe.whitelist()
def transcribe() -> dict[str, str]:
	"""POST multipart with field ``audio`` (WAV). Returns ``{"text": ...}``."""
	require_enabled()
	upload = frappe.request.files.get("audio") if frappe.request else None
	if upload is None:
		frappe.throw(_("No audio file provided."))
	data = upload.read()
	if len(data) > MAX_AUDIO_BYTES:
		frappe.throw(_("Audio too large (max 100 MB)."))
	if len(data) < MIN_AUDIO_BYTES:
		return {"text": ""}
	return {"text": transcribe_bytes(data, upload.filename or "audio.wav")}


def transcribe_bytes(data: bytes, filename: str = "audio.wav") -> str:
	key = _setting("elevenlabs_api_key")
	if not key:
		frappe.throw(_("ElevenLabs API key is not configured."))
	model = cstr(_setting("stt_model", DEFAULT_STT_MODEL))
	last_error: Exception | None = None
	for _attempt in range(2):
		try:
			response = requests.post(
				STT_URL,
				headers={"xi-api-key": key},
				# language unset - Scribe auto-detects and handles Arabic/English code-switching
				data={"model_id": model, "tag_audio_events": "false"},
				files={"file": (filename, data, "audio/wav")},
				timeout=180,
			)
			if response.status_code >= 400:
				raise RuntimeError(f"ElevenLabs STT {response.status_code}: {response.text[:300]}")
			return (response.json().get("text") or "").strip()
		except Exception as exc:  # noqa: BLE001 - one retry, then surface
			last_error = exc
	frappe.log_error(title="Voice scribe: transcription failed", message=cstr(last_error))
	frappe.throw(_("Transcription failed: {0}").format(cstr(last_error)))


# ------------------------------------------------------------ generate note


@frappe.whitelist()
def generate_note(transcript: str, encounter: str | None = None, appointment: str | None = None, patient: str | None = None) -> dict[str, Any]:
	"""Draft SOAP values for the encounter from a transcript. Saves only the transcript."""
	require_enabled()
	transcript = cstr(transcript).strip()
	if len(transcript) < 20:
		frappe.throw(_("The transcript is too short to write a note from."))
	encounter_doc = _resolve_encounter(encounter, appointment, patient)
	if not frappe.has_permission("Patient Encounter", "write", encounter_doc):
		frappe.throw(_("Not permitted to write this encounter."), frappe.PermissionError)

	prompt = build_note_prompt(
		transcript,
		patient=patient_context(encounter_doc.patient),
		previous=_previous_visit_summary(encounter_doc),
		clinician=frappe.db.get_value("Healthcare Practitioner", encounter_doc.practitioner, "practitioner_name")
		if encounter_doc.practitioner
		else None,
	)
	raw = chat_complete(NOTE_SYSTEM_PROMPT, prompt)
	parsed = safe_parse_json(raw)
	if not parsed or not (parsed.get("assessment") or parsed.get("subjective")):
		frappe.log_error(title="Voice scribe: unparseable note", message=raw[:4000])
		frappe.throw(_("The AI note could not be generated. Please try again."))

	if frappe.get_meta("Patient Encounter").has_field(TRANSCRIPT_FIELD):
		frappe.db.set_value("Patient Encounter", encounter_doc.name, TRANSCRIPT_FIELD, transcript, update_modified=False)

	return {
		"encounter": encounter_doc.name,
		"values": {
			SUBJECTIVE: cstr(parsed.get("subjective")).strip(),
			OBJECTIVE: cstr(parsed.get("objective")).strip(),
			ASSESSMENT: cstr(parsed.get("assessment")).strip(),
			PLAN: cstr(parsed.get("plan")).strip(),
		},
		"hp_values": {field: cstr(parsed.get(key)).strip() for field, key in zip(HP_FIELDS, HP_KEYS, strict=True)},
		"diagnosis": cstr(parsed.get("diagnosis")).strip(),
		"icd10": cstr(parsed.get("icd10")).strip(),
		"soap_ar": cstr(parsed.get("soap_ar")).strip(),
		"followup_en": cstr(parsed.get("followup_en")).strip(),
		"followup_ar": cstr(parsed.get("followup_ar")).strip(),
	}


def _resolve_encounter(encounter: str | None, appointment: str | None, patient: str | None):
	if encounter:
		return frappe.get_doc("Patient Encounter", encounter)
	filters: dict[str, Any] = {"docstatus": ["<", 2]}
	if appointment:
		filters["appointment"] = appointment
	elif patient:
		filters["patient"] = patient
	else:
		frappe.throw(_("No encounter to write the note into."))
	name = frappe.db.get_value("Patient Encounter", filters, "name", order_by="encounter_date desc, creation desc")
	if not name:
		frappe.throw(_("No encounter to write the note into. Start the assessment first."))
	return frappe.get_doc("Patient Encounter", name)


def patient_context(patient: str | None) -> dict[str, Any]:
	if not patient:
		return {}
	row = frappe.db.get_value("Patient", patient, ["patient_name", "sex", "dob"], as_dict=True) or {}
	age = None
	if row.get("dob"):
		age = date_diff(nowdate(), getdate(row["dob"])) // 365
	return {"name": row.get("patient_name"), "gender": row.get("sex"), "age": age}


def _previous_visit_summary(encounter_doc) -> str | None:
	if not frappe.get_meta("Patient Encounter").has_field(ASSESSMENT):
		return None
	rows = frappe.get_all(
		"Patient Encounter",
		filters={"patient": encounter_doc.patient, "name": ["!=", encounter_doc.name], ASSESSMENT: ["is", "set"]},
		fields=["encounter_date", ASSESSMENT, PLAN],
		order_by="encounter_date desc, creation desc",
		limit=1,
	)
	if not rows:
		return None
	prev = rows[0]
	return f"Last visit ({prev.encounter_date}): {cstr(prev.get(ASSESSMENT))[:800]} | Plan: {cstr(prev.get(PLAN))[:400]}"


def build_note_prompt(transcript: str, patient: dict[str, Any] | None = None, previous: str | None = None, clinician: str | None = None) -> str:
	parts = ["CONSULTATION TYPE: General dermatology consultation (Derma Chart visit)"]
	if clinician:
		parts.append(f"CLINICIAN: {clinician} (dermatologist)")
	bits = []
	for label, key in (("Name", "name"), ("Age", "age"), ("Gender", "gender")):
		if patient and patient.get(key):
			bits.append(f"{label}: {patient[key]}")
	if bits:
		parts.append("PATIENT CONTEXT:\n" + "\n".join(bits))
	if previous:
		parts.append(f"PREVIOUS VISIT SUMMARY (for follow-up context):\n{previous}")
	parts.append(f'RAW TRANSCRIPT (may be English, Arabic or mixed; clean it up, do not quote verbatim):\n"""\n{transcript.strip()}\n"""')
	parts.append("Generate the JSON object now.")
	return "\n\n".join(parts)


def chat_complete(system: str, user: str, temperature: float = 0.3) -> str:
	key = _setting("llm_api_key")
	if not key:
		frappe.throw(_("LLM API key is not configured."))
	base = cstr(_setting("llm_base_url", DEFAULT_LLM_BASE_URL)).rstrip("/")
	model = cstr(_setting("llm_model", DEFAULT_LLM_MODEL))
	response = requests.post(
		f"{base}/chat/completions",
		headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
		json={
			"model": model,
			"temperature": temperature,
			"max_tokens": MAX_TOKENS,
			"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
		},
		timeout=180,
	)
	if response.status_code >= 400:
		frappe.log_error(title="Voice scribe: LLM error", message=response.text[:2000])
		frappe.throw(_("AI provider error {0}").format(response.status_code))
	choices = response.json().get("choices") or []
	return ((choices[0].get("message") or {}).get("content") or "") if choices else ""


def safe_parse_json(raw: str | None) -> dict[str, Any] | None:
	"""Tolerate markdown fences and chatter around the JSON object."""
	if not raw:
		return None
	text = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.I)
	text = re.sub(r"\s*```$", "", text, flags=re.I)
	start, end = text.find("{"), text.rfind("}")
	if start == -1 or end <= start:
		return None
	for candidate in (text[start : end + 1], text):
		try:
			value = json.loads(candidate)
			return value if isinstance(value, dict) else None
		except json.JSONDecodeError:
			continue
	return None
