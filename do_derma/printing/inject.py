"""Puts the assessment block into every hand-written Patient Encounter print format.

Runs from after_migrate rather than a patch: `Encounter Print` is a standard format owned
by healthcare, so a healthcare release that edits its JSON silently reverts our DB row, and
a patch recorded as applied could never repair it.
"""

import re

import frappe

START = "<!-- do_derma:assessment:start -->"
END = "<!-- do_derma:assessment:end -->"
# Also matches the markers of the hand-injected block that predates this module.
LEGACY_PREFIX = "<!-- do_derma:assessment"

BLOCK = f"{START}\n{{{{ derma_assessment_html(doc) }}}}\n{END}"

COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)


def ensure_assessment_block_in_print_formats() -> dict[str, list[str]]:
	"""Idempotent. Returns the formats updated, left alone, and refused."""
	result: dict[str, list[str]] = {"updated": [], "unchanged": [], "skipped": []}
	for row in frappe.get_all(
		"Print Format",
		filters={
			"doc_type": "Patient Encounter",
			"disabled": 0,
			"print_format_type": "Jinja",
			"print_format_builder": 0,
		},
		fields=["name", "html"],
	):
		if not (row.html or "").strip():
			result["skipped"].append(row.name)
			continue
		outcome = _apply_to(row.name, row.html)
		result[outcome].append(row.name)
	if result["updated"]:
		frappe.clear_cache()
	return result


def _apply_to(name: str, html: str) -> str:
	stripped = strip_derma_block(html)
	if stripped is None:
		frappe.log_error(
			title="Derma print block skipped",
			message=f"{name} has content after its derma marker; left untouched.",
		)
		return "skipped"

	new_html = f"{stripped.rstrip()}\n\n{BLOCK}\n"
	if new_html == html:
		return "unchanged"

	# db.set_value, not doc.save: standard formats are owned by healthcare and this is a
	# repair of a live site, the same way this app's patches repair one.
	frappe.db.set_value("Print Format", name, "html", new_html)
	return "updated"


def strip_derma_block(html: str) -> str | None:
	"""Everything before our block, or None when the tail cannot be proven ours.

	Our own block is marker-delimited, but the hand-injected one that predates it has an
	opening marker and no closing one, so removing it means truncating to end of string.
	Only do that when nothing foreign lives in the tail.
	"""
	index = html.find(LEGACY_PREFIX)
	if index == -1:
		return html
	tail = html[index:]
	foreign = [comment for comment in COMMENT_PATTERN.findall(tail) if not comment.startswith(LEGACY_PREFIX)]
	if foreign:
		return None
	return html[:index]
