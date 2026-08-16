from __future__ import annotations

from do_derma.patches.helpers import ensure_standard_page


def execute():
	"""Ensure the standard Derma Chart desk page exists on non-developer sites.

	The page is shipped as a source-backed Page, but a live site can still lose the
	database row if it was deleted manually. Creating it in a patch avoids the need
	to enable developer mode on production.
	"""
	ensure_standard_page("derma-chart", "Derma Chart")
