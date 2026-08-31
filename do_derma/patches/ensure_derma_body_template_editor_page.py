from __future__ import annotations

from do_derma.patches.helpers import ensure_standard_page


def execute():
	"""Ensure the Body Map Designer desk page exists. The config workspace links to
	it, so a site missing the row would show a button that routes nowhere."""
	ensure_standard_page("derma-body-template-editor", "Derma Body Map Designer")
