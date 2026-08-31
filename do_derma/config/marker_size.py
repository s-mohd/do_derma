"""The multiplier a mark is stamped at, read from the client module that owns it."""

from __future__ import annotations

import re
from pathlib import Path

import frappe
from frappe import _

SIZE_MODULE = Path(__file__).resolve().parent.parent / "public" / "js" / "shared" / "marker_size.js"

MARKER_SIZE_FIELD = "custom_derma_marker_size"
MARK_SIZE_FIELD = "marker_size"

_CONSTANT = re.compile(r"export const (MARKER_SIZE_\w+) = ([\d.]+)")


def _js_constants() -> dict[str, float]:
	constants = {name: float(value) for name, value in _CONSTANT.findall(SIZE_MODULE.read_text())}
	missing = {"MARKER_SIZE_MIN", "MARKER_SIZE_MAX", "MARKER_SIZE_STEP"} - constants.keys()
	if missing:
		raise ValueError(f"{sorted(missing)} not found in {SIZE_MODULE}")
	return constants


_CONSTANTS = _js_constants()
MARKER_SIZE_MIN = _CONSTANTS["MARKER_SIZE_MIN"]
MARKER_SIZE_MAX = _CONSTANTS["MARKER_SIZE_MAX"]
MARKER_SIZE_STEP = _CONSTANTS["MARKER_SIZE_STEP"]


def validated_marker_size(value: object) -> float:
	"""Nothing means unset, which is stored as 0. Anything else has to be a number the
	sliders could have produced - a clamp here would hide the caller that sent junk."""
	if value in (None, ""):
		return 0.0
	try:
		size = float(value)
	except (TypeError, ValueError):
		frappe.throw(_("Marker size must be a number."))
	if size and not MARKER_SIZE_MIN <= size <= MARKER_SIZE_MAX:
		frappe.throw(_("Marker size must be between {0} and {1}.").format(MARKER_SIZE_MIN, MARKER_SIZE_MAX))
	return size
