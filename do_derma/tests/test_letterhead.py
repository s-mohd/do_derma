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
				# Disabled, so DermaTestHelpers._get_or_create_practitioner never hands it to another test.
				{"doctype": "Healthcare Practitioner", "first_name": f"Mark{frappe.generate_hash(length=8)}", "status": "Disabled"}
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
		page = str(letterhead.derma_letterhead_open(practitioner)) + "<p>Body</p>" + str(letterhead.derma_letterhead_close(practitioner))
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
