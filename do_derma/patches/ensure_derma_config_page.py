from __future__ import annotations

from do_derma.patches.helpers import ensure_standard_page


def execute():
	"""Ensure the Derma Configuration desk page exists on non-developer sites."""
	ensure_standard_page("derma-config", "Derma Configuration")
