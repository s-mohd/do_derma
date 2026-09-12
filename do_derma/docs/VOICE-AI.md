# Voice AI in the Derma Chart

Ambient scribe, three note formats, AI letters and a usage ledger, all inside the Derma Chart page. Built by SOULVD on branch `feat/voice-ai-scribe` (do_derma) with a matching one-line change in do_health.

## What the doctor sees

| Where | What |
|---|---|
| Assessment tab, top strip | **Dictate** records the visit from any microphone (picker when more than one). Live level meter: *No sound / Low – bring the mic closer / Good level / Too loud – move the mic away*. Warning + toast after 6 s of silence. Recording stops itself at the configured maximum. |
| After **Stop** | Transcript → AI note. One dictation drafts all three formats (Structured, SOAP, H&P) and saves them together on the encounter immediately (still a draft); the panel opens for editing. Diagnosis + ICD‑10 chip, collapsible Arabic note and WhatsApp follow-up (EN/AR, Copy). The follow-up is also saved on the encounter as **Patient Advice** (EN + AR, editable on the Patient Encounter form) and shown in a collapsible block on the Assessment tab. |
| Format toggle | **Structured / SOAP / H&P**. The format on screen stays selected after dictation; switching afterwards shows each one already drafted. H&P = Chief Complaint, History of Presenting Complaint, Past Medical History, Examination Findings, Assessment, Management Plan. |
| **Adjust** box | "Ask the AI to adjust the note" – rewrites the active format per the instruction and saves as draft. |
| **Print** (Assessment footer, once filled) | Prints the active format on the clinic letterhead through Print Format **Derma Assessment Note** (patient bar, note, clinician sign-off). Browser print or PDF from the print view. **Include patient advice** (checkbox beside Print, stored as *Include Patient Advice in Print* on the encounter, off by default) appends the Patient Advice block (EN + AR) under the note - optional, exactly like the after-visit message on health.soulvd.com. |
| Review tab, **AI Documents** | Medical Report, Referral Letter (asks addressee), Patient Education, Patient Explainer. Each becomes a *Patient Official Document* (Draft) with English + Arabic body. **Issue** renders the letterhead PDF (page 1 EN, page 2 AR). |

### Note style

SOAP and H&P follow the clinic's house style: clinical register with the subject dropped ("Reports bilateral lower limb swelling."), every detail carried (duration, quantities, what was tried), stated negatives documented as negatives rather than omitted, one plan measure per sentence, and the follow-up interval always last.

## Setup (admin)

1. `bench get-app` both apps on the branch, `bench --site <site> migrate` (creates custom fields, the `Derma AI Usage` doctype, the four `Derma AI *` print templates and the `Derma Assessment Note` print format), `bench build --app do_derma`.
2. **Derma Settings › Voice AI Scribe**:
   - Enable Voice AI Scribe
   - Speech-to-Text Base URL + ElevenLabs API Key
   - LLM Base URL + LLM Model + LLM API Key
   - Max Recording (minutes), Keep Audio (days; 0 = forever)
   - **Let the AI create missing Complaint / Diagnosis records** (default off). Off: a dictated symptom or diagnosis fills the Structured tab only when it already exists in the master list; unmatched terms go into Symptoms Notes / Diagnosis Note as text. On: the missing master is created.
   - Recommended: point both base URLs at the **SOULVD AI Gateway** (`https://gateway.soulvd.com/v1`) and put the clinic's SOULVD key in both key fields. One key, usage metered by SOULVD, no provider accounts needed. Direct ElevenLabs/OpenAI/Groq keys also work.
   - Any of these may instead be set in `site_config.json` under the same names; a value in Derma Settings wins.
3. Structured fields come from the clinic's configured Structured Assessment list (Derma Settings); each field's *Description* is passed to the AI as a hint, so fill it in for fields whose label alone does not explain them.
4. Make sure each Healthcare Practitioner has `practitioner_name` and `designation` (used in sign-offs) and the Company has `company_name` and `country` (used in prompts).
5. Server needs `wkhtmltopdf` (standard Frappe) for Issue → PDF.
6. Workers: with `bench start`/production the AI runs on the `long` queue and the page polls; with a bare `bench serve` (no workers) it runs inline.

Roles: dictation and documents require a clinical role (same check as the rest of the chart); the ledger is readable by System Manager and Healthcare Administrator.

## Data written

| Doctype / field | Purpose |
|---|---|
| Patient Encounter `custom_derma_voice_transcript` (hidden, Long Text) | raw transcript for audit |
| Patient Encounter `custom_derma_hp_*` (6 × Small Text) | H&P format |
| Patient Encounter Structured fields (the configured list: Complaint / Diagnosis child tables, Symptoms Notes, Diagnosis Note, other text fields) | Structured format from the same dictation |
| Print Format `Derma Assessment Note` (Patient Encounter, Jinja, seeded on migrate; a clinic edit that removes the version marker is kept) | letterhead print of the active format |
| File attached to the encounter, `consultation-<ts>.wav`, private | the recording; purged nightly after *Keep Audio* days when set |
| Patient Official Document (`document_type` Medical Report / Referral Letter / Patient Education Material / Patient Explainer Letter) | AI letters; `values_json` = `{title, body, body_ar, addressee}` |
| Derma AI Usage | one row per AI call: kind, user, encounter, patient, audio_seconds, prompt/completion tokens, model, duration, status, error |

## Whitelisted API (`/api/method/...`)

All require a logged-in user with a clinical role and Voice AI enabled.

| Method | Args | Returns |
|---|---|---|
| `do_derma.voice.transcribe` | multipart `audio` (WAV), optional `encounter` | `{text}` |
| `do_derma.voice.queue_note` | `transcript`, `encounter` (or `appointment`/`patient`) | `{job}` |
| `do_derma.voice.job_status` | `job` | `{status: pending|done|failed|unknown, result?, error?}` |
| `do_derma.voice.generate_note` | same as queue_note (synchronous) | `{encounter, values{SOAP fields}, hp_values{H&P fields}, structured_values{Structured fields}, diagnosis, icd10, soap_ar, followup_en, followup_ar}` |
| `do_derma.voice.refine_note` | `instruction`, `encounter` | full assessment payload (same as `get_derma_assessment`) |
| `do_derma.documents.queue_document` | `kind` (report/referral/education/explainer), `encounter`, `addressee?` | `{job}` → result = document row |
| `do_derma.documents.generate_document` | same (synchronous) | document row |
| `do_derma.documents.list_documents` | `encounter` | `[{name, document_type, status, docstatus, creation, title, body, body_ar, pdf_url}]` |
| `do_derma.documents.issue_document` | `name` | document row (status Issued, pdf_url) |
| `do_derma.api.set_derma_assessment_all` | `payloads` `{Structured, SOAP, HP}` (any may be omitted), `mode` (the format on screen, written last and stamped), `encounter` (or `appointment`/`patient`) | full assessment payload. Throws `ValidationError` on a completed encounter unless the active format has an allow-on-submit field |
| `do_derma.api.get_derma_assessment` / `set_derma_assessment` / `set_derma_assessment_mode` | existing; `mode` now accepts `HP` and the payload carries `hp_layout` / `hp_values` | |

`get_patient_derma_chart` and `get_chart_context` carry `voice_scribe_enabled` and `voice_scribe: {enabled, max_recording_minutes}`.

## Provider contract (for the gateway or direct keys)

- STT: `POST {stt_base_url}/speech-to-text`, multipart `model_id`, `file`, `tag_audio_events=false`; headers `xi-api-key` and `Authorization: Bearer` both sent. Response `{text}`.
- LLM: `POST {llm_base_url}/chat/completions`, OpenAI chat schema, `temperature 0.3`, `max_tokens 5000`, JSON-only replies; `usage` from the response is written to the ledger.

## Cost and metering

`Derma AI Usage` gives minutes of audio and tokens per user, encounter and day (list view filters, or export). With the SOULVD gateway the same numbers are metered server-side per clinic key, so invoices can be reconciled against the ledger.

## Tests

`bench --site <test site> run-tests --app do_derma --module do_derma.tests.test_voice` (and `test_hp_mode`, `test_documents`, `test_ai_ops`). `test_voice_all_formats` covers the Structured mapping, `set_derma_assessment_all` and print-format seeding. External calls are mocked; PDF rendering uses a blank PDF.
