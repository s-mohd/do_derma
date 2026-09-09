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
import struct
import time
from typing import Any

import frappe
import requests
from frappe import _
from frappe.utils import add_days, cint, cstr, date_diff, getdate, nowdate

from do_derma.assessment import HP_FIELDS, SOAP_FIELDS
from do_derma.schema import VOICE_TRANSCRIPT_FIELD as TRANSCRIPT_FIELD
from do_derma.settings import get_settings_doc

DEFAULT_STT_BASE_URL = "https://api.elevenlabs.io/v1"
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

NOTE_SYSTEM_PROMPT = """You are SOULVD Health, an expert dermatology medical scribe assistant working for {clinic}, a dermatology clinic in {country}.

You convert raw consultation audio transcripts (which may mix English, Arabic, or a local Arabic dialect, and may contain filler words, interruptions, and background chatter) into professional clinical documentation.

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
5. soap_ar: a faithful MEDICAL Arabic translation of the four sections, labelled "الشكوى والتاريخ", "الفحص", "التقييم", "الخطة" (clinical Arabic as used in {country}), not a summary.
6. followup_en: a warm, patient-friendly after-visit message in simple English, ready to send via WhatsApp from the clinic: greeting, 3-6 clear instruction bullets, red-flag warning when relevant, sign-off from {clinic}. Plain text with "- " bullets, max ~180 words.
7. followup_ar: the same message in natural, warm Arabic as used with patients in {country}.
8. If the transcript is clearly a DOCTOR DICTATION (structured monologue, no patient dialogue), still produce the same output structure.

Respond with ONLY a valid JSON object (no markdown fences, no commentary) with exactly these keys:
{"subjective": "...", "objective": "...", "assessment": "...", "plan": "...", "chief_complaint": "...", "history_of_presenting_complaint": "...", "past_medical_history": "...", "examination_findings": "...", "hp_assessment": "...", "management_plan": "...", "diagnosis": "...", "icd10": "...", "soap_ar": "...", "followup_en": "...", "followup_ar": "..."}"""


def clinic_context(company: str | None = None) -> dict[str, str]:
	"""Clinic name and country for prompts and sign-offs, from the Company (never hardcoded)."""
	company = company or frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
	row = (frappe.db.get_value("Company", company, ["company_name", "country"], as_dict=True) if company else None) or {}
	return {"clinic": row.get("company_name") or company or "the clinic", "country": row.get("country") or "the region"}


def fill_clinic(prompt: str, company: str | None = None) -> str:
	"""Substitute {clinic}/{country}; prompts also contain JSON braces, so no str.format."""
	context = clinic_context(company)
	return prompt.replace("{clinic}", context["clinic"]).replace("{country}", context["country"])


def note_system_prompt(company: str | None = None) -> str:
	return fill_clinic(NOTE_SYSTEM_PROMPT, company)


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


def client_config() -> dict[str, Any]:
	"""What the chart needs to know before recording."""
	return {"enabled": is_enabled(), "max_recording_minutes": cint(_setting("max_recording_minutes", 20)) or 20}


def require_enabled() -> None:
	if not is_enabled():
		frappe.throw(_("Voice AI scribe is not enabled in Derma Settings."))
	from do_derma.api import _ensure_clinical_access  # lazy: api imports this module

	_ensure_clinical_access()


# --------------------------------------------------------------------- jobs

JOB_TTL_SECONDS = 3600


def has_workers() -> bool:
	"""True when at least one RQ worker listens; a dev bench with only `bench serve` has none."""
	try:
		from rq import Worker

		from frappe.utils.background_jobs import get_redis_conn

		return Worker.count(connection=get_redis_conn()) > 0
	except Exception:
		return False


def enqueue_ai_job(method: str, **kwargs: Any) -> dict[str, str]:
	"""Run `method` in the long queue (or inline when nothing would pick it up); poll with job_status."""
	job = frappe.generate_hash(length=16)
	_set_job(job, {"status": "pending"})
	frappe.enqueue(method, queue="long", timeout=900, now=frappe.in_test or not has_workers(), job=job, **kwargs)
	return {"job": job}


def run_ai_job(job: str, work) -> None:
	try:
		_set_job(job, {"status": "done", "result": work()})
	except Exception as exc:  # noqa: BLE001 - the browser shows this message
		_set_job(job, {"status": "failed", "error": cstr(exc)[:500]})
		frappe.log_error(title="Derma AI job failed", message=frappe.get_traceback())


def _set_job(job: str, value: dict[str, Any]) -> None:
	frappe.cache().set_value(f"derma_ai_job:{job}", value, expires_in_sec=JOB_TTL_SECONDS)


@frappe.whitelist()
def job_status(job: str) -> dict[str, Any]:
	require_enabled()
	return frappe.cache().get_value(f"derma_ai_job:{job}") or {"status": "unknown"}


@frappe.whitelist()
def queue_note(transcript: str, encounter: str | None = None, appointment: str | None = None, patient: str | None = None) -> dict[str, str]:
	require_enabled()
	return enqueue_ai_job("do_derma.voice.note_job", transcript=transcript, encounter=encounter, appointment=appointment, patient=patient)


def note_job(job: str, transcript: str, encounter: str | None, appointment: str | None, patient: str | None) -> None:
	run_ai_job(job, lambda: generate_note(transcript, encounter=encounter, appointment=appointment, patient=patient))


# ------------------------------------------------------------------- ledger


def record_usage(kind: str, encounter: str | None = None, patient: str | None = None, **units: Any) -> None:
	"""One Derma AI Usage row per AI call. Never raises: billing must not break charting."""
	try:
		row = frappe.get_doc({"doctype": "Derma AI Usage", "kind": kind, "user": frappe.session.user, "encounter": encounter, "patient": patient, **units})
		row.flags.ignore_permissions = True
		row.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Derma AI Usage not recorded", message=frappe.get_traceback())


def wav_seconds(data: bytes) -> float:
	"""Duration from the RIFF header; falls back to 16 kHz mono 16-bit when it is not a WAV."""
	try:
		if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
			channels, rate = struct.unpack_from("<HI", data, 22)
			bits = struct.unpack_from("<H", data, 34)[0]
			return round((len(data) - 44) / (rate * channels * (bits // 8)), 1)
	except Exception:
		pass
	return round(len(data) / 32000, 1)


def purge_old_audio() -> int:
	"""Daily job: delete consultation recordings older than Derma Settings.audio_retention_days (0 = keep)."""
	days = cint(_setting("audio_retention_days", 0))
	if days <= 0:
		return 0
	files = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Patient Encounter", "file_name": ["like", "consultation-%.wav"], "creation": ["<", add_days(nowdate(), -days)]},
		pluck="name",
	)
	for name in files:
		frappe.delete_doc("File", name, ignore_permissions=True, delete_permanently=True)
	return len(files)


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
	seconds = wav_seconds(data)
	if seconds > (cint(_setting("max_recording_minutes", 20)) or 20) * 60 + 30:
		frappe.throw(_("Recording is longer than the allowed maximum."))
	started = time.monotonic()
	encounter = frappe.form_dict.get("encounter") if frappe.form_dict else None
	try:
		text = transcribe_bytes(data, upload.filename or "audio.wav")
	except Exception as exc:
		record_usage("Transcription", encounter=encounter, status="Failed", audio_seconds=seconds, error=cstr(exc)[:500], duration_ms=int((time.monotonic() - started) * 1000))
		raise
	record_usage("Transcription", encounter=encounter, audio_seconds=seconds, model=cstr(_setting("stt_model", DEFAULT_STT_MODEL)), duration_ms=int((time.monotonic() - started) * 1000))
	return {"text": text}


def transcribe_bytes(data: bytes, filename: str = "audio.wav") -> str:
	key = _setting("elevenlabs_api_key")
	if not key:
		frappe.throw(_("ElevenLabs API key is not configured."))
	model = cstr(_setting("stt_model", DEFAULT_STT_MODEL))
	last_error: Exception | None = None
	for _attempt in range(2):
		try:
			response = requests.post(
				f"{cstr(_setting('stt_base_url', DEFAULT_STT_BASE_URL)).rstrip('/')}/speech-to-text",
				# ElevenLabs rejects a second auth header; the SOULVD gateway accepts xi-api-key too.
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
	raw, usage = chat_complete_with_usage(note_system_prompt(encounter_doc.company), prompt)
	parsed = safe_parse_json(raw)
	if not parsed or not (parsed.get("assessment") or parsed.get("subjective")):
		record_usage("Note", encounter=encounter_doc.name, patient=encounter_doc.patient, status="Failed", error="unparseable reply", **usage)
		frappe.log_error(title="Voice scribe: unparseable note", message=raw[:4000])
		frappe.throw(_("The AI note could not be generated. Please try again."))
	record_usage("Note", encounter=encounter_doc.name, patient=encounter_doc.patient, **usage)

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


REFINE_SYSTEM_PROMPT = """You edit a dermatology clinical note for {clinic} exactly as the doctor instructs.
You receive the current note as a JSON object of sections and one instruction. Apply the instruction; leave every other section unchanged; never invent findings. Keep the language of each section as it is.
Respond with ONLY a JSON object with the same keys and the full updated text of every section."""


@frappe.whitelist()
def refine_note(instruction: str, encounter: str | None = None, appointment: str | None = None, patient: str | None = None) -> dict[str, Any]:
	"""Rewrite the active-format note per the doctor's instruction and save it as a draft."""
	from do_derma import assessment

	require_enabled()
	instruction = cstr(instruction).strip()
	if len(instruction) < 3:
		frappe.throw(_("Tell the AI what to change."))
	encounter_doc = _resolve_encounter(encounter, appointment, patient)
	if not frappe.has_permission("Patient Encounter", "write", encounter_doc):
		frappe.throw(_("Not permitted to write this encounter."), frappe.PermissionError)
	mode = assessment.get_assessment_mode(encounter_doc)
	if mode not in assessment.MODE_FIELDS:
		frappe.throw(_("Switch the note to SOAP or H&P before asking the AI to adjust it."))
	layout = assessment.get_layout(mode)
	current = {row["label"]: cstr(encounter_doc.get(row["fieldname"])) for row in layout}
	if not any(value.strip() for value in current.values()):
		frappe.throw(_("There is no note to adjust yet."))
	user_prompt = f"CURRENT NOTE:\n{json.dumps(current, ensure_ascii=False)}\n\nINSTRUCTION: {instruction}\n\nReturn the JSON object now."
	raw, usage = chat_complete_with_usage(fill_clinic(REFINE_SYSTEM_PROMPT, encounter_doc.company), user_prompt)
	parsed = safe_parse_json(raw)
	if not parsed:
		record_usage("Refine", encounter=encounter_doc.name, patient=encounter_doc.patient, status="Failed", error="unparseable reply", **usage)
		frappe.throw(_("The AI could not adjust the note. Please try again."))
	record_usage("Refine", encounter=encounter_doc.name, patient=encounter_doc.patient, **usage)
	values = {row["fieldname"]: cstr(parsed.get(row["label"], current[row["label"]])) for row in layout}
	assessment.apply_assessment(encounter_doc, values, mode=mode)
	encounter_doc.save(ignore_permissions=True)
	return assessment.read_assessment(encounter_doc)


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
	return chat_complete_with_usage(system, user, temperature)[0]


def chat_complete_with_usage(system: str, user: str, temperature: float = 0.3) -> tuple[str, dict[str, Any]]:
	"""Returns (content, usage) where usage = {model, prompt_tokens, completion_tokens, duration_ms}."""
	started = time.monotonic()
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
	body = response.json()
	choices = body.get("choices") or []
	usage = body.get("usage") or {}
	meta = {
		"model": body.get("model") or model,
		"prompt_tokens": cint(usage.get("prompt_tokens")),
		"completion_tokens": cint(usage.get("completion_tokens")),
		"duration_ms": int((time.monotonic() - started) * 1000),
	}
	return (((choices[0].get("message") or {}).get("content") or "") if choices else "", meta)


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
