# Derma Prints on Letter Head Records Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every Derma Chart printable prints on the site's default Letter Head, or the practitioner's own, and carries the practitioner's signature and/or stamp.

**Architecture:** `do_derma/printing/letterhead.py` becomes the single owner of the print shell: it resolves the Letter Head (practitioner override → site default → loud error) and exposes three Jinja globals that the seeded templates call at render time. Client-built prints (consent, blank consent, annotation review) move server-side behind one endpoint, with page assembly in a new `printing/pages.py`; the browser only opens a window and prints what the server returns.

**Tech Stack:** Frappe v16 (Python, Jinja print formats, Custom Fields), do_health Patient Print Templates, Vue 3 chart (`public/js/chart`), built with `bench build`.

**Spec:** `.planning/specs/2026-10-04-derma-letter-head.md`

## Global Constraints

- Branch: `feat/derma-letter-head`. Commit after every task; message format `<type>: <description>`, ending with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Python is tab-indented. No comment at the top of a new file; use short docstrings. Keep comments terse.
- Custom Fields live in `schema.py` (`DERMA_CUSTOM_FIELDS`), never only in a patch.
- Whitelisted endpoints call `_ensure_clinical_access()` first.
- Fieldname: `custom_derma_letter_head` (Link → Letter Head), `insert_after` = `custom_official_document_mark`.
- Error text, exact: `Set a default Letter Head to print derma documents.` and `Unknown printable: {0}`.
- Footer room stays 42mm, held in one constant `FOOTER_ROOM`.
- Mark rule: Signature → `custom_signature`; Stamp → `custom_stamp`; Both → both; empty/unknown → Signature; missing image skipped.
- Templates: `printing/note.py` `TEMPLATE_VERSION` 20 → 21; `documents.py` `TEMPLATE_VERSION` 21 → 22.
- Tests: run from `/Users/hameed/Developer/bench-v16` as `bench --site dermaone.localhost run-tests --module <module> [--test <bare_method_name>]`, filtered with `2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"`. `--test ClassName` silently runs nothing. A run that prints no `Ran N tests` line ran nothing.
- Known red baseline on main (do not chase): `test_ai_ops.test_document_keeps_arabic_and_records_usage`, `test_documents.test_generate_creates_a_draft_official_document`, `test_documents.test_issue_renders_body_and_attaches_pdf`, `test_readiness.test_an_inventory_row_with_no_product_name_still_names_its_item` (flaky), `test_ai_ops.test_prompts_name_the_company_not_a_hardcoded_clinic`, `test_printing.test_advice_language_follows_the_report_or_the_doctor`; plus `test_documents` tests reaching `get_form_preview`.
- `IntegrationTestCase` rolls back once per class, not per test: every test that needs a default Letter Head creates its own.
- Lint changed Python files only: `pipx run ruff check <files>`.

## Review Focus

- A legacy Consent Form with no encounter prints the practitioner of its linked Clinical Procedure → Task 5 `test_a_legacy_consent_takes_the_procedures_practitioner`.
- An AI letter printed in both languages carries the mark under each language block → Task 4 `test_a_letter_in_both_languages_is_marked_twice`.
- A practitioner who chose Stamp but never uploaded one still gets a place to sign by hand → Task 2 `test_a_missing_image_falls_back_to_the_ink_line`.
- An encounter whose practitioner is empty prints on the default Letter Head with no signature block, instead of crashing → Task 3 `test_note_without_a_practitioner_prints_on_the_default_without_a_mark`.
- Drawing labels typed by a clinician never reach the printed page unescaped → Task 5 `test_annotation_page_escapes_the_label`.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `do_derma/schema.py` | modify | declare `LETTER_HEAD_FIELD` and its Custom Field |
| `do_derma/printing/letterhead.py` | modify | resolve the Letter Head; shell open/close; practitioner mark |
| `do_derma/printing/pages.py` | create | whole pages for consent, blank consent, annotation |
| `do_derma/printing/note.py` | modify | note template calls the Jinja globals |
| `do_derma/documents.py` | modify | AI letter template calls the Jinja globals |
| `do_derma/api.py` | modify | `get_consent_doc`, `get_derma_print_html`; drop `letterhead_logo` |
| `do_derma/hooks.py` | modify | register the three Jinja globals; drop the logo one |
| `do_derma/public/js/shared/print_window.js` | modify | `printPage(loadPage)` replaces `printHtml` |
| `do_derma/public/js/chart/DermaChart.vue` | modify | prints go through the endpoint |
| `do_derma/public/images/derma-one-logo.png`, `dr-sadiq-abdulla-logo.png` | delete | replaced by Letter Head records |
| `do_derma/tests/test_letterhead.py` | create | `LetterHeadHelpers` fixtures + letterhead unit tests |
| `do_derma/tests/test_print_pages.py` | create | endpoint and page tests |
| `do_derma/tests/test_schema.py`, `test_printing.py`, `test_documents.py` | modify | new field; note and letter print on Letter Heads |

---

### Task 1: The practitioner's Letter Head field

**Files:**
- Modify: `do_derma/schema.py` (constants near line 57; `"Healthcare Practitioner"` list near line 449)
- Test: `do_derma/tests/test_schema.py`

**Interfaces:**
- Produces: `do_derma.schema.LETTER_HEAD_FIELD = "custom_derma_letter_head"`

- [ ] **Step 1: Write the failing test** — append to `class TestEnsureDermaSchema` in `tests/test_schema.py`:

```python
	def test_practitioner_gets_a_letter_head_link_next_to_the_document_mark(self):
		ensure_derma_schema()
		field = frappe.get_meta("Healthcare Practitioner").get_field("custom_derma_letter_head")
		self.assertIsNotNone(field)
		self.assertEqual((field.fieldtype, field.options), ("Link", "Letter Head"))
		insert_after = frappe.db.get_value(
			"Custom Field", {"dt": "Healthcare Practitioner", "fieldname": "custom_derma_letter_head"}, "insert_after"
		)
		self.assertEqual(insert_after, "custom_official_document_mark")
```

- [ ] **Step 2: Run it, expect FAIL** (`field` is None)

Run: `bench --site dermaone.localhost run-tests --module do_derma.tests.test_schema --test test_practitioner_gets_a_letter_head_link_next_to_the_document_mark 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"`

- [ ] **Step 3: Implement** — in `schema.py`, after `WAIVER_REASON_FIELD = ...`:

```python
LETTER_HEAD_FIELD = "custom_derma_letter_head"
```

and append to the `"Healthcare Practitioner"` list in `DERMA_CUSTOM_FIELDS`:

```python
		{
			"fieldname": LETTER_HEAD_FIELD,
			"fieldtype": "Link",
			"label": "Letter Head",
			"options": "Letter Head",
			"insert_after": "custom_official_document_mark",
			"description": "Derma chart prints use this instead of the site's default Letter Head.",
		},
```

- [ ] **Step 4: Run the whole module, expect PASS**

Run: `bench --site dermaone.localhost run-tests --module do_derma.tests.test_schema 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"`

- [ ] **Step 5: Commit**

```bash
git add do_derma/schema.py do_derma/tests/test_schema.py
git commit -m "feat(printing): practitioners can carry their own Letter Head"
```

---

### Task 2: Letter Head resolution, shell and mark

**Files:**
- Modify: `do_derma/printing/letterhead.py`, `do_derma/hooks.py` (jinja methods, near line 46)
- Create: `do_derma/tests/test_letterhead.py`

**Interfaces:**
- Consumes: `schema.LETTER_HEAD_FIELD`
- Produces (all in `do_derma.printing.letterhead`):
  - `FOOTER_ROOM: str = "42mm"`
  - `get_letter_head(practitioner=None) -> Document` (Letter Head)
  - `get_mark_images(practitioner) -> list[str]`
  - `derma_letterhead_open(practitioner=None) -> Markup`
  - `derma_letterhead_close(practitioner=None) -> Markup`
  - `derma_practitioner_mark(practitioner=None) -> Markup` (empty when no practitioner)
  - `practitioner` is a Healthcare Practitioner doc, a `frappe._dict`, or None.
- Produces (in `do_derma.tests.test_letterhead`): `SIGNATURE_SRC`, `STAMP_SRC`, `class LetterHeadHelpers` with `_make_letter_head(is_default=0, **extra)` and `_make_marked_practitioner(mark="Signature", letter_head=None, signature=SIGNATURE_SRC, stamp=STAMP_SRC)`.

The old `OPEN`, `HEADER`, `SIGNATURE`, `CLOSE`, logo and footer code stay in this task (the templates still use them); Task 7 deletes them.

- [ ] **Step 1: Write the failing tests** — create `do_derma/tests/test_letterhead.py`:

```python
from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from do_derma.printing import letterhead
from do_derma.schema import LETTER_HEAD_FIELD, ensure_derma_schema

SIGNATURE_SRC = "data:image/png;base64,iVBORw0KGgo="
STAMP_SRC = "/files/derma-test-stamp.png"


class LetterHeadHelpers:
	"""Letter Heads and marked practitioners built per test, never read from site data."""

	def _make_letter_head(self, is_default=0, **extra):
		token = frappe.generate_hash(length=8)
		return frappe.get_doc(
			{
				"doctype": "Letter Head",
				"letter_head_name": f"Derma Test {token}",
				"source": "HTML",
				"content": f"<p>Header {token}</p>",
				"footer_source": "HTML",
				"footer": f"<p>Footer {token}</p>",
				"is_default": is_default,
				**extra,
			}
		).insert(ignore_permissions=True)

	def _make_marked_practitioner(self, mark="Signature", letter_head=None, signature=SIGNATURE_SRC, stamp=STAMP_SRC):
		name = (
			frappe.get_doc(
				{"doctype": "Healthcare Practitioner", "first_name": f"Mark{frappe.generate_hash(length=8)}", "status": "Active"}
			)
			.insert(ignore_permissions=True)
			.name
		)
		frappe.db.set_value(
			"Healthcare Practitioner",
			name,
			{
				"custom_signature": signature,
				"custom_stamp": stamp,
				"custom_official_document_mark": mark,
				"custom_specialty": "Dermatologist",
				LETTER_HEAD_FIELD: letter_head,
			},
		)
		return frappe.get_doc("Healthcare Practitioner", name)


class TestLetterHead(LetterHeadHelpers, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_derma_schema()

	def setUp(self):
		self.default = self._make_letter_head(is_default=1)

	def test_the_practitioners_own_letter_head_wins(self):
		own = self._make_letter_head()
		practitioner = self._make_marked_practitioner(letter_head=own.name)
		self.assertEqual(letterhead.get_letter_head(practitioner).name, own.name)

	def test_a_disabled_own_letter_head_falls_back_to_the_default(self):
		own = self._make_letter_head(disabled=1)
		practitioner = self._make_marked_practitioner(letter_head=own.name)
		self.assertEqual(letterhead.get_letter_head(practitioner).name, self.default.name)

	def test_without_an_own_letter_head_the_default_prints(self):
		self.assertEqual(letterhead.get_letter_head(self._make_marked_practitioner()).name, self.default.name)
		self.assertEqual(letterhead.get_letter_head(None).name, self.default.name)

	def test_no_default_letter_head_refuses_to_print(self):
		frappe.db.set_value("Letter Head", {"is_default": 1}, "is_default", 0)
		with self.assertRaisesRegex(frappe.ValidationError, "Set a default Letter Head"):
			letterhead.get_letter_head(None)

	def test_the_shell_wraps_the_body_in_the_letter_heads_header_and_footer(self):
		own = self._make_letter_head()
		practitioner = self._make_marked_practitioner(letter_head=own.name)
		page = letterhead.derma_letterhead_open(practitioner) + "<p>Body</p>" + letterhead.derma_letterhead_close(practitioner)
		self.assertLess(page.index(own.content), page.index("<p>Body</p>"))
		self.assertLess(page.index("<p>Body</p>"), page.index(own.footer))
		self.assertIn('id="footer-html"', page)
		self.assertIn(f"height:{letterhead.FOOTER_ROOM};", page)

	def test_the_mark_follows_the_official_document_mark(self):
		cases = {
			"Signature": [SIGNATURE_SRC],
			"Stamp": [STAMP_SRC],
			"Both": [SIGNATURE_SRC, STAMP_SRC],
			"": [SIGNATURE_SRC],
			"Unknown": [SIGNATURE_SRC],
		}
		for mark, expected in cases.items():
			with self.subTest(mark=mark):
				self.assertEqual(letterhead.get_mark_images(self._make_marked_practitioner(mark=mark)), expected)

	def test_the_mark_prints_the_images_above_the_name_and_title(self):
		practitioner = self._make_marked_practitioner(mark="Both")
		mark = letterhead.derma_practitioner_mark(practitioner)
		self.assertLess(mark.index(SIGNATURE_SRC), mark.index(practitioner.practitioner_name))
		self.assertLess(mark.index(STAMP_SRC), mark.index(practitioner.practitioner_name))
		self.assertIn("Dermatologist", mark)

	def test_a_missing_image_falls_back_to_the_ink_line(self):
		practitioner = self._make_marked_practitioner(mark="Stamp", stamp="")
		mark = letterhead.derma_practitioner_mark(practitioner)
		self.assertNotIn("<img", mark)
		self.assertIn('class="derma-signature-mark"', mark)
		self.assertIn(practitioner.practitioner_name, mark)

	def test_no_practitioner_prints_no_mark(self):
		self.assertEqual(letterhead.derma_practitioner_mark(None), "")
		self.assertEqual(letterhead.derma_practitioner_mark(frappe._dict()), "")

	def test_the_jinja_globals_are_registered(self):
		methods = frappe.get_hooks("jinja")["methods"]
		for name in ("derma_letterhead_open", "derma_letterhead_close", "derma_practitioner_mark"):
			self.assertIn(f"do_derma.printing.letterhead.{name}", methods)
```

- [ ] **Step 2: Run, expect FAIL** (`AttributeError: ... has no attribute 'get_letter_head'`)

Run: `bench --site dermaone.localhost run-tests --module do_derma.tests.test_letterhead 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"`

- [ ] **Step 3: Implement** — in `printing/letterhead.py`:

Add imports:

```python
import frappe
from frappe import _
from markupsafe import Markup, escape

from do_derma.schema import LETTER_HEAD_FIELD
```

Replace the first line of `STYLE` so the footer room is one constant (define `FOOTER_ROOM` above `STYLE`):

```python
FOOTER_ROOM = "42mm"

STYLE = """<style>
.print-format { margin-bottom: """ + FOOTER_ROOM + """; }
```

(the rest of `STYLE` is unchanged). Then add, below `CLOSE`:

```python
MARKS = {
	"Signature": ("custom_signature",),
	"Stamp": ("custom_stamp",),
	"Both": ("custom_signature", "custom_stamp"),
}


def get_letter_head(practitioner=None):
	"""The practitioner's own enabled Letter Head, else the site default."""
	own = practitioner.get(LETTER_HEAD_FIELD) if practitioner else None
	if own and not frappe.db.get_value("Letter Head", own, "disabled"):
		return frappe.get_cached_doc("Letter Head", own)
	default = frappe.db.get_value("Letter Head", {"is_default": 1, "disabled": 0}, "name")
	if not default:
		frappe.throw(_("Set a default Letter Head to print derma documents."), frappe.ValidationError)
	return frappe.get_cached_doc("Letter Head", default)


def derma_letterhead_open(practitioner=None) -> Markup:
	"""Jinja global: the page shell and the Letter Head's header, ahead of the letter body."""
	header = get_letter_head(practitioner).content or ""
	return Markup(
		STYLE
		+ '<table class="derma-letterhead"><tfoot class="hidden-pdf"><tr><td>'
		+ f'<div style="height:{FOOTER_ROOM};"></div></td></tr></tfoot><tbody><tr><td>'
		+ f'<div class="derma-letterhead-head" style="margin:0 0 20px;">{header}</div>'
	)


def derma_letterhead_close(practitioner=None) -> Markup:
	"""Jinja global: closes the shell; the Letter Head's footer sits at the foot of every sheet."""
	footer = get_letter_head(practitioner).footer or ""
	return Markup(
		"</td></tr></tbody></table>"
		f'<div id="footer-html" class="visible-pdf derma-letterhead-foot"><div style="padding-bottom:12mm;">{footer}</div></div>'
	)


def get_mark_images(practitioner) -> list[str]:
	"""The signature and/or stamp the practitioner's Official Document Mark asks for, minus missing ones."""
	fields = MARKS.get(practitioner.get("custom_official_document_mark"), MARKS["Signature"])
	return [practitioner.get(field) for field in fields if practitioner.get(field)]


def derma_practitioner_mark(practitioner=None) -> Markup:
	"""Jinja global: the signature and/or stamp, overlaid, above the clinician's name and title."""
	if not practitioner:
		return Markup("")
	images = "".join(
		f'<img src="{escape(src)}" alt="" style="position:absolute;left:0;bottom:2px;max-width:220px;max-height:22mm;">'
		for src in get_mark_images(practitioner)
	)
	title = practitioner.get("custom_specialty") or practitioner.get("designation")
	subtitle = f'<br><span style="color:#666;">{escape(title)}</span>' if title else ""
	return Markup(
		'<div class="derma-signature" style="margin-top:3mm;margin-bottom:-5mm;font-size:12px;">'
		f'<div class="derma-signature-mark" style="position:relative;height:22mm;width:240px;">{images}</div>'
		'<div style="border-top:1px solid #333;width:240px;padding-top:6px;">'
		f'{escape(practitioner.get("practitioner_name") or "")}{subtitle}</div>'
		"</div>"
	)
```

In `hooks.py`, add to `jinja["methods"]` (keep `derma_letterhead_logo` for now):

```python
		"do_derma.printing.letterhead.derma_letterhead_open",
		"do_derma.printing.letterhead.derma_letterhead_close",
		"do_derma.printing.letterhead.derma_practitioner_mark",
```

- [ ] **Step 4: Run, expect PASS** (same command as Step 2: `Ran 10 tests` … `OK`)

- [ ] **Step 5: Lint and commit**

```bash
pipx run ruff check do_derma/printing/letterhead.py do_derma/tests/test_letterhead.py
git add do_derma/printing/letterhead.py do_derma/hooks.py do_derma/tests/test_letterhead.py
git commit -m "feat(printing): resolve the Letter Head and draw the practitioner's mark"
```

---

### Task 3: The assessment note prints on the Letter Head

**Files:**
- Modify: `do_derma/printing/note.py:86-106`
- Test: `do_derma/tests/test_printing.py` (`PrintingTestBase` near line 30; tests near lines 526-547)

**Interfaces:**
- Consumes: the three Jinja globals; `LetterHeadHelpers`, `SIGNATURE_SRC`, `STAMP_SRC` from `do_derma.tests.test_letterhead`.

- [ ] **Step 1: Write the failing tests** — in `tests/test_printing.py`:

Add import `from do_derma.tests.test_letterhead import SIGNATURE_SRC, STAMP_SRC, LetterHeadHelpers`. Make the base class `class PrintingTestBase(LetterHeadHelpers, DermaTestHelpers, IntegrationTestCase):` and add to its `setUp`, after `frappe.set_user("Administrator")`:

```python
		self.letter_head = self._make_letter_head(is_default=1)
```

Replace `test_note_prints_on_the_clinic_letterhead` and `test_doctor_with_own_logo_prints_it_instead_of_the_clinic_logo` with:

```python
	def test_note_prints_on_the_default_letter_head(self):
		note.ensure_assessment_print_format()
		encounter = self._soap_encounter(custom_derma_soap_plan="Topical steroid twice daily")
		printed = frappe.get_print("Patient Encounter", encounter.name, print_format=note.PRINT_FORMATS[assessment.SOAP])
		self.assertLess(printed.index(self.letter_head.content), printed.index("Topical steroid twice daily"))
		self.assertIn(self.letter_head.footer, printed)
		self.assertIn('id="footer-html"', printed)
		self.assertNotIn("CR No. 100506-1", printed)
		# Frappe's `table td div { page-break-inside: avoid }` would push the whole body to page 2.
		self.assertIn(".derma-letterhead td div { page-break-inside: auto !important; }", printed)
		self.assertIn('class="derma-signature"', printed)

	def test_doctor_with_own_letter_head_prints_it_with_their_signature_and_stamp(self):
		note.ensure_assessment_print_format()
		own = self._make_letter_head()
		practitioner = self._make_marked_practitioner(mark="Both", letter_head=own.name)
		encounter = self._soap_encounter(custom_derma_soap_plan="Compression stockings")
		encounter.db_set("practitioner", practitioner.name)
		printed = frappe.get_print("Patient Encounter", encounter.name, print_format=note.PRINT_FORMATS[assessment.SOAP])
		self.assertIn(own.content, printed)
		self.assertIn(own.footer, printed)
		self.assertNotIn(self.letter_head.content, printed)
		self.assertIn(SIGNATURE_SRC, printed)
		self.assertIn(STAMP_SRC, printed)

	def test_note_without_a_practitioner_prints_on_the_default_without_a_mark(self):
		note.ensure_assessment_print_format()
		encounter = self._soap_encounter(custom_derma_soap_plan="Emollients")
		encounter.db_set("practitioner", None)
		printed = frappe.get_print("Patient Encounter", encounter.name, print_format=note.PRINT_FORMATS[assessment.SOAP])
		self.assertIn(self.letter_head.content, printed)
		self.assertNotIn('class="derma-signature"', printed)
```

- [ ] **Step 2: Run, expect FAIL** (the note still prints the bundled logo)

Run: `bench --site dermaone.localhost run-tests --module do_derma.tests.test_printing 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"`

- [ ] **Step 3: Implement** — in `printing/note.py`:

- `TEMPLATE_VERSION = 21`
- In `TEMPLATE`, replace `""" + letterhead.OPEN + """` with `{{ derma_letterhead_open(practitioner) }}`, `""" + letterhead.SIGNATURE + """` with `  {{ derma_practitioner_mark(practitioner) }}`, and the trailing `""" + letterhead.CLOSE` with `{{ derma_letterhead_close(practitioner) }}"""`. The result:

```python
TEMPLATE = f"""{TEMPLATE_MARKER}{TEMPLATE_VERSION} -->
""" + """
{%- set patient = frappe.get_doc("Patient", doc.patient) if doc.patient else None -%}
{%- set practitioner = frappe.get_doc("Healthcare Practitioner", doc.practitioner) if doc.practitioner else None -%}
{{ derma_letterhead_open(practitioner) }}
<div style="font-family:Arial,Helvetica,sans-serif;max-width:720px;margin:0 auto;color:#1a1a1a;line-height:1.4;padding:0 24px;">
  ... (the patient table, diagnosis, assessment and advice lines, unchanged) ...
  {{ derma_practitioner_mark(practitioner) }}
</div>
{{ derma_letterhead_close(practitioner) }}"""
```

- Remove `from do_derma.printing import letterhead` if nothing else in `note.py` uses it (`grep -n letterhead do_derma/printing/note.py`).
- Reseed: `bench --site dermaone.localhost migrate`

- [ ] **Step 4: Run, expect PASS** apart from the baseline `test_advice_language_follows_the_report_or_the_doctor`. `test_logo_file_matches_the_doctor_name_loosely` still passes (Task 7 removes it). Same command as Step 2.

- [ ] **Step 5: Lint and commit**

```bash
pipx run ruff check do_derma/printing/note.py
git add do_derma/printing/note.py do_derma/tests/test_printing.py
git commit -m "feat(printing): the assessment note prints on the practitioner's Letter Head"
```

---

### Task 4: AI letters print on the Letter Head

**Files:**
- Modify: `do_derma/documents.py:100-136`
- Test: `do_derma/tests/test_documents.py`

**Interfaces:**
- Consumes: the three Jinja globals; `LetterHeadHelpers`, `SIGNATURE_SRC`, `STAMP_SRC`; do_health's `render_service.render_string(template_html=..., practitioner=..., values=...)`.

- [ ] **Step 1: Write the failing tests** — in `tests/test_documents.py`:

Add imports `from do_health.services.patient_print import render as render_service` and `from do_derma.tests.test_letterhead import SIGNATURE_SRC, STAMP_SRC, LetterHeadHelpers`. Make the class `class TestAiDocuments(LetterHeadHelpers, DermaTestHelpers, IntegrationTestCase):` and add to its `setUp`, after `frappe.set_user("Administrator")`:

```python
		self.letter_head = self._make_letter_head(is_default=1)
```

In `test_issue_renders_body_and_attaches_pdf`, replace `self.assertIn(letterhead.LOGO_SRC, get_pdf.call_args.args[0])  # embedded, ...` with `self.assertIn(self.letter_head.content, get_pdf.call_args.args[0])` and `self.assertIn("CR No. 100506-1", html)` with `self.assertIn(self.letter_head.footer, html)`. Remove the now-unused `from do_derma.printing import letterhead`.

Add:

```python
	def _render_letter(self, practitioner, language="English"):
		return render_service.render_string(
			template_html=documents.LETTER_TEMPLATE,
			practitioner=practitioner,
			values={"title": "Medical Report", "body": "## Findings\nClear skin", "body_ar": "جلد سليم", "language": language},
		)

	def test_a_letter_prints_on_the_doctors_letter_head_with_their_mark(self):
		own = self._make_letter_head()
		html = self._render_letter(self._make_marked_practitioner(mark="Both", letter_head=own.name))
		self.assertLess(html.index(own.content), html.index("Clear skin"))
		self.assertIn(own.footer, html)
		self.assertNotIn(self.letter_head.content, html)
		self.assertIn(SIGNATURE_SRC, html)
		self.assertIn(STAMP_SRC, html)

	def test_a_letter_in_both_languages_is_marked_twice(self):
		html = self._render_letter(self._make_marked_practitioner(), language="Both")
		self.assertEqual(html.count('class="derma-signature"'), 2)
```

- [ ] **Step 2: Run, expect FAIL** on the two new tests

Run: `bench --site dermaone.localhost run-tests --module do_derma.tests.test_documents 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"`

- [ ] **Step 3: Implement** — in `documents.py`:

- `TEMPLATE_VERSION = 22`
- In `LETTER_TEMPLATE`, replace `""" + letterhead.OPEN + """` with `{{ derma_letterhead_open(practitioner) }}`, both `""" + letterhead.SIGNATURE + """` with `{{ derma_practitioner_mark(practitioner) }}`, and the trailing `""" + letterhead.CLOSE` with `{{ derma_letterhead_close(practitioner) }}"""`.
- Remove `from do_derma.printing import letterhead`.
- Reseed: `bench --site dermaone.localhost migrate`

- [ ] **Step 4: Run, expect PASS** for the two new tests; the rest match the baseline (same command as Step 2).

- [ ] **Step 5: Lint and commit**

```bash
pipx run ruff check do_derma/documents.py do_derma/tests/test_documents.py
git add do_derma/documents.py do_derma/tests/test_documents.py
git commit -m "feat(documents): AI letters print on the practitioner's Letter Head with their mark"
```

---

### Task 5: Server-built pages for consent, blank consent and annotation

**Files:**
- Create: `do_derma/printing/pages.py`
- Modify: `do_derma/api.py` (`get_derma_consent_html` near line 3497; imports near line 27)
- Create: `do_derma/tests/test_print_pages.py`

**Interfaces:**
- Consumes: `derma_letterhead_open/close`, `derma_practitioner_mark`.
- Produces:
  - `do_derma.printing.pages.get_page(title: str, practitioner, body: str) -> dict[str, str]`
  - `pages.get_consent_page(doc) -> dict`, `pages.get_blank_consent_page(encounter: str, body: str | None) -> dict`, `pages.get_annotation_page(name: str) -> dict`
  - `do_derma.api.get_consent_doc(name: str) -> Document`
  - Whitelisted `do_derma.api.get_derma_print_html(kind: str, name: str, body: str | None = None) -> {"title": str, "html": str}`; kinds `consent`, `blank_consent`, `annotation`.

- [ ] **Step 1: Write the failing tests** — create `do_derma/tests/test_print_pages.py`:

```python
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
		frappe.db.set_value("Health Annotation", name, "custom_derma_body_template_title", title)
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
```

- [ ] **Step 2: Run, expect FAIL** (`AttributeError: module 'do_derma.api' has no attribute 'get_derma_print_html'`)

Run: `bench --site dermaone.localhost run-tests --module do_derma.tests.test_print_pages 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"`

- [ ] **Step 3: Implement `printing/pages.py`**

```python
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import escape_html, formatdate

from do_derma.printing.letterhead import derma_letterhead_close, derma_letterhead_open, derma_practitioner_mark

BODY_STYLE = "font-family:Arial,Helvetica,sans-serif;max-width:720px;margin:0 auto;color:#1a1a1a;line-height:1.4;padding:0 24px;"
DRAWING_PARENTS = ("Patient Encounter", "Clinical Procedure")


def get_page(title: str, practitioner, body: str) -> dict[str, str]:
	"""A whole page: the Letter Head, the body, then the practitioner's mark."""
	html = (
		derma_letterhead_open(practitioner)
		+ f'<div style="{BODY_STYLE}">{body}{derma_practitioner_mark(practitioner)}</div>'
		+ derma_letterhead_close(practitioner)
	)
	return {"title": title, "html": str(html)}


def get_identity_line(parts: list) -> str:
	"""Who and what a sheet is for, so a paper copy can be filed. Escapes every part."""
	text = " · ".join(escape_html(str(part)) for part in parts if part)
	return f'<p style="margin:0 0 16px;color:#475569;font-size:13px;">{text}</p>'


def get_practitioner(*sources: tuple[str, str | None]):
	"""The Healthcare Practitioner of the first linked record that names one."""
	for doctype, name in sources:
		practitioner = name and frappe.db.get_value(doctype, name, "practitioner")
		if practitioner:
			return frappe.get_doc("Healthcare Practitioner", practitioner)
	return None


def get_patient_page(patient: str | None, encounter: str | None, title: str, body: str, practitioner) -> dict[str, str]:
	"""A consent-style page: patient, MRN and encounter above the body."""
	patient_name = frappe.db.get_value("Patient", patient, "patient_name") if patient else ""
	identity = get_identity_line([patient_name, f"{_('MRN')}: {patient}" if patient else "", encounter])
	return get_page(" - ".join(filter(None, [patient_name, title])), practitioner, identity + body)


def get_consent_page(doc) -> dict[str, str]:
	practitioner = get_practitioner(
		("Patient Encounter", doc.get("encounter")), ("Clinical Procedure", doc.get("clinical_procedure"))
	)
	title = doc.get("consent_form_template") or _("Consent Form")
	return get_patient_page(doc.get("patient"), doc.get("encounter"), title, doc.get("rendered_html") or "", practitioner)


def get_blank_consent_page(encounter: str, body: str | None) -> dict[str, str]:
	"""The unsaved consent the Consent panel built. Not sanitised: it returns only to its sender's window."""
	if not (body or "").strip():
		frappe.throw(_("Nothing to print: the consent preview is empty."), frappe.ValidationError)
	doc = frappe.get_doc("Patient Encounter", encounter)
	practitioner = get_practitioner(("Patient Encounter", doc.name))
	return get_patient_page(doc.patient, doc.name, _("Consent Form"), body, practitioner)


def get_annotation_page(name: str) -> dict[str, str]:
	"""A saved drawing with its legend, for the paper file."""
	annotation = frappe.get_doc("Health Annotation", name)
	row = frappe.db.get_value(
		"Health Annotation Table",
		{"annotation": name, "parenttype": ["in", DRAWING_PARENTS]},
		["parent", "parenttype", "annotation_data"],
		as_dict=True,
		order_by="creation desc",
	) or frappe._dict()
	practitioner = get_practitioner((row.parenttype, row.parent)) if row.parent else None
	patient = frappe.db.get_value(row.parenttype, row.parent, "patient") if row.parent else None
	patient_name = frappe.db.get_value("Patient", patient, "patient_name") if patient else ""
	label = annotation.get("custom_derma_body_template_title") or annotation.get("annotation_template") or _("Drawing")
	identity = get_identity_line(
		[
			f"{_('MRN')}: {patient}" if patient else "",
			label,
			formatdate(annotation.creation),
			practitioner and practitioner.practitioner_name,
			row.parent if row.parenttype == "Patient Encounter" else "",
		]
	)
	image = annotation.get("image")
	body = (
		f'<h2 style="margin:0 0 4px;">{escape_html(patient_name)}</h2>'
		+ identity
		+ (f'<img src="{escape_html(image)}" style="max-width:100%;max-height:60vh;" alt="">' if image else "")
		# The legend is escaped when it is generated.
		+ f'<div style="margin-top:16px;">{row.annotation_data or ""}</div>'
	)
	return get_page(" - ".join(filter(None, [patient_name, label])), practitioner, body)
```

- [ ] **Step 4: Implement the endpoint in `api.py`**

Add `from do_derma.printing import pages` next to the existing `from do_derma.printing import letterhead`. Replace `get_derma_consent_html` with the extracted lookup plus the slimmer endpoint, and add the new endpoint after it:

```python
def get_consent_doc(name: str):
	"""The consent under either consent doctype, rendered from its template if it never was."""
	doctype = consent.ConsentDoctype().name
	if not frappe.db.exists(doctype, name):
		doctype = consent.CONSENT_FORM
	doc = frappe.get_doc(doctype, name)
	if not doc.get("rendered_html") and doc.get("consent_form_template") and hasattr(doc, "render_template"):
		doc.render_template()
		doc.save(ignore_permissions=True)
	return doc


@frappe.whitelist()
def get_derma_consent_html(name: str):
	_ensure_clinical_access()
	if not name:
		frappe.throw(_("Consent is required."), frappe.ValidationError)
	doc = get_consent_doc(name)
	return {
		"name": doc.name,
		"doctype": doc.doctype,
		"consent_form_template": doc.get("consent_form_template"),
		"rendered_html": doc.get("rendered_html"),
		"status": doc.get("status"),
		"signed_by": doc.get("signed_by"),
		"signed_on": doc.get("signed_on"),
	}


@frappe.whitelist()
def get_derma_print_html(kind: str, name: str, body: str | None = None) -> dict[str, str]:
	"""A whole printable page on the practitioner's Letter Head: {"title", "html"}."""
	_ensure_clinical_access()
	if not name:
		frappe.throw(_("Choose what to print."), frappe.ValidationError)
	if kind == "consent":
		return pages.get_consent_page(get_consent_doc(name))
	if kind == "blank_consent":
		return pages.get_blank_consent_page(name, body)
	if kind == "annotation":
		return pages.get_annotation_page(name)
	frappe.throw(_("Unknown printable: {0}").format(kind), frappe.ValidationError)
```

- [ ] **Step 5: Run, expect PASS** (Step 2 command: `Ran 9 tests` … `OK`). Then re-run `do_derma.tests.test_consent` to confirm the extracted lookup kept `get_derma_consent_html` working.

- [ ] **Step 6: Lint and commit**

```bash
pipx run ruff check do_derma/printing/pages.py do_derma/tests/test_print_pages.py
git add do_derma/printing/pages.py do_derma/api.py do_derma/tests/test_print_pages.py
git commit -m "feat(printing): consents and drawings print as server-built Letter Head pages"
```

---

### Task 6: The chart prints through the server

**Files:**
- Modify: `do_derma/public/js/shared/print_window.js` (whole file)
- Modify: `do_derma/public/js/chart/DermaChart.vue` (line 264 `@print-blank`; line 595 import; `printAnnotationReview` near 1605; consent dialog near 2288; `printConsent` near 2313)

**Interfaces:**
- Consumes: `do_derma.api.get_derma_print_html(kind, name, body)`.
- Produces: `printPage(loadPage: () => Promise<{title, html}>)` exported from `print_window.js`.

- [ ] **Step 1: Replace `print_window.js`**

```js
const __ = window.__ || ((text) => text)

/**
 * Prints a whole page the server built on the practitioner's Letter Head
 * (do_derma/printing/pages.py). The window opens inside the click, before the
 * request, so pop-up blockers let it through.
 */
export async function printPage(loadPage) {
  const printWindow = window.open("", "_blank")
  if (!printWindow) {
    frappe.show_alert({ message: __("Allow pop-ups to print."), indicator: "orange" })
    return
  }
  try {
    const { title, html } = await loadPage()
    printWindow.document.write(`<!doctype html>
      <html><head><title>${frappe.utils.escape_html(title || "")}</title></head>
      <body style="font-family:sans-serif;margin:0;">${html}</body></html>`)
    printWindow.document.close()
    printWindow.focus()
    setTimeout(() => printWindow.print(), 350)
  } catch (error) {
    printWindow.close()
    throw error
  }
}
```

- [ ] **Step 2: Update `DermaChart.vue`**

- Import: `import { printPage } from "../shared/print_window.js"`.
- Add, next to `printAnnotationReview`:

```js
/** One printable built by the server on the visit practitioner's Letter Head. */
async function printDermaPage(kind, name, body = undefined) {
  try {
    await printPage(async () => {
      const response = await frappe.call({ method: "do_derma.api.get_derma_print_html", args: { kind, name, body } })
      return response.message
    })
  } catch (error) {
    frappe.show_alert({ message: serverErrorText(error, __("Unable to print.")), indicator: "red" })
  }
}
```

- `printAnnotationReview(annotation)` body becomes `printDermaPage("annotation", annotation.name)`. Then `grep -n "annotationIdentityLine\|annotationTemplateLabel\|annotationPreview" do_derma/public/js/chart/DermaChart.vue` and delete any of those helpers left with no caller.
- In the signed-consent dialog, `primary_action() { if (printable) printDermaPage("consent", name) }`.
- Template line 264: `@print-blank="(html) => printDermaPage('blank_consent', encounter.name, html)"`.
- Delete `function printConsent(...)` and its docstring.
- Confirm nothing is left: `grep -n "printHtml\|printConsent\|letterhead_logo" do_derma/public/js` must print nothing.

- [ ] **Step 3: Build and restart the web server**

```bash
cd /Users/hameed/Developer/bench-v16 && bench build --app do_derma
```

Then restart the port-8002 web server (after `bench build`, `/assets/do_derma/...` 404s until it restarts).

- [ ] **Step 4: Browser check** — `bench --site dermaone.localhost browse --user Administrator`, open a derma chart on an encounter whose practitioner has a stamp/signature:
  - Consents → open a signed consent → Print: page shows the Letter Head header, consent body, mark, footer at the foot.
  - Consents → new consent → Print blank: same shell, blank signature lines.
  - Drawings → review → Print: image, legend, mark.
  - No pop-up blocker warning on any of them.

- [ ] **Step 5: Commit**

```bash
git add do_derma/public/js/shared/print_window.js do_derma/public/js/chart/DermaChart.vue
git commit -m "feat(chart): consents and drawings print the server's Letter Head page"
```

---

### Task 7: Delete the hardcoded letterhead

**Files:**
- Modify: `do_derma/printing/letterhead.py`, `do_derma/hooks.py`, `do_derma/api.py` (payload near line 2469; import near line 27)
- Delete: `do_derma/public/images/derma-one-logo.png`, `do_derma/public/images/dr-sadiq-abdulla-logo.png`
- Modify: `do_derma/tests/test_printing.py` (delete `test_logo_file_matches_the_doctor_name_loosely`)

**Interfaces:**
- Consumes: nothing new. After this task `letterhead.py` exposes only `FOOTER_ROOM`, `STYLE`, `MARKS`, and the Task 2 functions.

- [ ] **Step 1: Delete `test_logo_file_matches_the_doctor_name_loosely`** from `tests/test_printing.py`, and any `patch` import it leaves unused.

- [ ] **Step 2: Strip `letterhead.py`** — delete `IMAGES`, `LOGO_FILE`, `PRACTITIONER_LOGO_FILES`, `_data_uri`, `LOGO_SRC`, `PRACTITIONER_LOGO_SRCS`, `get_logo_file`, `get_logo_url`, `derma_letterhead_logo`, `FOOTER_LINES`, `FOOTER`, `HEADER`, `SIGNATURE`, `OPEN`, `CLOSE`, and the imports only they used (`base64`, `re`, `Path`, `cstr`). Replace the module docstring with:

```python
"""Every Derma Chart print on the practitioner's Letter Head, else the site default.

wkhtmltopdf lifts `#footer-html` into its per-page footer and reads page margins from
`.print-format`; the browser print dialog uses the `@media print` table, whose empty tfoot
repeats on each sheet to reserve the fixed footer's room.
"""
```

- [ ] **Step 3: Remove the rest**
  - `hooks.py`: drop `"do_derma.printing.letterhead.derma_letterhead_logo",`.
  - `api.py`: drop the `"letterhead_logo": letterhead.get_logo_url(...)` entry from the chart payload, and `from do_derma.printing import letterhead` if nothing else uses it.
  - `git rm do_derma/public/images/derma-one-logo.png do_derma/public/images/dr-sadiq-abdulla-logo.png`
  - Verify: `grep -rn "LOGO_SRC\|get_logo\|derma_letterhead_logo\|letterhead_logo\|letterhead.OPEN\|letterhead.SIGNATURE\|letterhead.CLOSE\|derma-one-logo\|dr-sadiq-abdulla-logo" do_derma --include='*.py' --include='*.js' --include='*.vue' --include='*.html'` prints nothing.

- [ ] **Step 4: Run the printing modules, expect PASS** apart from the baseline:

```bash
cd /Users/hameed/Developer/bench-v16
for m in test_letterhead test_printing test_documents test_print_pages test_consent test_schema; do
  echo "== $m"; bench --site dermaone.localhost run-tests --module do_derma.tests.$m 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"
done
```

- [ ] **Step 5: Lint and commit**

```bash
pipx run ruff check do_derma/printing/letterhead.py do_derma/tests/test_printing.py
git add -A do_derma/printing/letterhead.py do_derma/hooks.py do_derma/api.py do_derma/tests/test_printing.py do_derma/public/images
git commit -m "refactor(printing): drop the hardcoded Derma One logo and footer"
```

---

### Task 8: Whole-branch verification

- [ ] **Step 1:** `bench --site dermaone.localhost migrate`, then run the full do_derma suite and save the failing names:

```bash
cd /Users/hameed/Developer/bench-v16
bench --site dermaone.localhost run-tests --app do_derma 2>&1 | grep -E "^\s*(FAIL|ERROR):" | sort > /Users/hameed/.claude/jobs/d8126c10/tmp/branch-failures.txt
```

Compare against the baseline list in Global Constraints. Any name not on that list is a regression this branch must fix.

- [ ] **Step 2: Browser pass** (port 8002, `bench --site dermaone.localhost browse --user Administrator`):
  - Set Dr Sadiq Salman's **Letter Head** to "DermaOne Letter Head (Dr Sadiq)" in Desk. Print his assessment note (H&P, SOAP, Structured), one AI letter PDF, a consent and a drawing: each shows his header, his signature, and the footer on every sheet.
  - Clear the field: the same prints use the site default.
  - Set his Official Document Mark to Stamp with no stamp uploaded: the ink line returns.
  - Reset his practitioner record to how it was.

- [ ] **Step 3:** Report the results. Remind the user of the deployment prerequisite (create the neutral clinic Letter Head as the default, then set Dr Nedhal's and Dr Sadiq's own).
