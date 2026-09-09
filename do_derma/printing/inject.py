"""Puts do_derma's blocks into every hand-written Patient Encounter print format.

Runs from after_migrate rather than a patch: `Encounter Print` is a standard format owned
by healthcare, so a healthcare release that edits its JSON silently reverts our DB row, and
a patch recorded as applied could never repair it.
"""

import re
from dataclasses import dataclass

import frappe

DERMA_PREFIX = "<!-- do_derma:"
COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
# The hand-injected assessment block that predates this module: an opening marker with no
# closing one. Our own markers are excluded so a second run does not read them as legacy.
LEGACY_PATTERN = re.compile(r"<!--\s*do_derma:assessment(?!:start|:end)[^>]*-->")


@dataclass(frozen=True)
class PrintBlock:
	"""One marker-delimited call this app owns inside a print format."""

	key: str
	method: str

	@property
	def start(self) -> str:
		return f"<!-- do_derma:{self.key}:start -->"

	@property
	def end(self) -> str:
		return f"<!-- do_derma:{self.key}:end -->"

	@property
	def html(self) -> str:
		return f"{self.start}\n{{{{ {self.method}(doc) }}}}\n{self.end}"


ASSESSMENT = PrintBlock("assessment", "derma_assessment_html")
CONSUMABLES = PrintBlock("consumables", "derma_consumables_html")
PROCEDURE_VARIABLES = PrintBlock("procedure_variables", "derma_procedure_variables_html")
BLOCKS = [ASSESSMENT, CONSUMABLES, PROCEDURE_VARIABLES]


def ensure_derma_blocks_in_print_formats() -> dict[str, list[str]]:
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
	stripped = strip_legacy_block(html)
	if stripped is None:
		frappe.log_error(
			title="Derma print block skipped",
			message=f"{name} has content after its derma marker; left untouched.",
		)
		return "skipped"

	new_html = stripped
	for block in BLOCKS:
		new_html = place_block(new_html, block)
	if new_html == html:
		return "unchanged"

	# db.set_value, not doc.save: standard formats are owned by healthcare and this is a
	# repair of a live site, the same way this app's patches repair one.
	frappe.db.set_value("Print Format", name, "html", new_html)
	return "updated"


def place_block(html: str, block: PrintBlock) -> str:
	"""The block written over its own markers, or appended when it is not there yet."""
	start = html.find(block.start)
	end = html.find(block.end)
	if start != -1 and end > start:
		return html[:start] + block.html + html[end + len(block.end) :]
	return f"{html.rstrip()}\n\n{block.html}\n"


def strip_legacy_block(html: str) -> str | None:
	"""Everything before the hand-injected block, or None when the tail cannot be proven ours.

	The legacy block has no closing marker, so removing it means truncating to end of
	string. Only do that when nothing foreign lives in the tail.
	"""
	match = LEGACY_PATTERN.search(html)
	if not match:
		return html
	tail = html[match.start() :]
	foreign = [comment for comment in COMMENT_PATTERN.findall(tail) if not comment.startswith(DERMA_PREFIX)]
	if foreign:
		return None
	return html[: match.start()]
