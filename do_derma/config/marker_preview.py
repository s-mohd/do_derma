"""The marker behaviours the config page can draw, read from the client module that draws them."""

from __future__ import annotations

import re
from pathlib import Path

PREVIEW_MODULE = Path(__file__).resolve().parent.parent / "public" / "js" / "shared" / "marker_preview.js"
_BEHAVIOR_LIST = re.compile(r"export const PREVIEW_BEHAVIORS = \[(.*?)\]", re.DOTALL)


def marker_preview_behaviors() -> list[str]:
	"""Every behaviour the preview module claims a shape for.

	Parsed rather than duplicated: a second list in Python would be the drift the test
	using this exists to catch.
	"""
	source = PREVIEW_MODULE.read_text()
	match = _BEHAVIOR_LIST.search(source)
	if not match:
		raise ValueError(f"PREVIEW_BEHAVIORS not found in {PREVIEW_MODULE}")
	return re.findall(r'"([^"]+)"', match.group(1))
