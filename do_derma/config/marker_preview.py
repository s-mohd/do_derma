"""Which mark each behaviour draws, read from the two client modules that draw them.

The config page previews a marker in a plain Vue bundle; the chart stamps it as Excalidraw
elements in the React bundle. Neither can import the other, so the substring chain that maps a
behaviour to a shape is written twice. These helpers replay both chains in Python so a test can
hold them to each other instead of trusting the copy.
"""

from __future__ import annotations

import re
from pathlib import Path

_PUBLIC = Path(__file__).resolve().parent.parent / "public" / "js"
PREVIEW_MODULE = _PUBLIC / "shared" / "marker_preview.js"
CHART_MODULE = _PUBLIC / "chart" / "excalidraw" / "EmbeddedExcalidraw.jsx"

_BEHAVIOR_LIST = re.compile(r"export const PREVIEW_BEHAVIORS = \[(.*?)\]", re.DOTALL)
_PREVIEW_CHAIN = re.compile(r"export function markerShapeFor\(behavior\)\s*\{(.*?)\n\}", re.DOTALL)
_CHART_CHAIN = re.compile(r"function stampShapeElements\(\{[^}]*\}\)\s*\{(.*?)\n\}", re.DOTALL)
# What a branch of each chain returns. Anchoring on these skips the guards and passthroughs that
# are not behaviour-driven - `if (!key) return null`, and the preset-JSON override on the chart.
_PREVIEW_RETURN = r"SHAPES\.(?P<shape>\w+)"
_CHART_RETURN = r"(?P<shape>create\w+)\("
_FALLBACK = re.compile(r"return (?:SHAPES\.)?(\w+)\(?[^\n]*$")
_INCLUDES = re.compile(r'(?:key|behavior)\.includes\("([^"]+)"\)')
_PREDICATE_CALL = re.compile(r"\b(\w+)\((?:behavior|key)\)")


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


def _needles(condition: str, source: str) -> list[str]:
	"""The substrings a branch tests for, expanding helper predicates like `isAreaKeyword`.

	Raises on a condition this cannot model. A parser that quietly skipped an unrecognised test
	would report the chain resolving a behaviour it never reaches, which is worse than no test.
	"""
	needles = _INCLUDES.findall(condition)
	remainder = _INCLUDES.sub("", condition)
	for predicate in _PREDICATE_CALL.findall(remainder):
		body = re.search(rf"function {predicate}\((?:behavior|key)\)\s*\{{(.*?)\n\}}", source, re.DOTALL)
		if not body:
			raise ValueError(f"Cannot resolve predicate {predicate}() while replaying the shape chain")
		needles.extend(_INCLUDES.findall(body.group(1)))
		remainder = _PREDICATE_CALL.sub("", remainder, count=1)
	leftover = re.sub(r"[\s|&!()]", "", remainder)
	if leftover:
		raise ValueError(f"Unmodelled condition {condition!r} while replaying the shape chain")
	return needles


def _resolve(behavior: str, module: Path, chain_pattern: re.Pattern, return_pattern: str) -> str:
	source = module.read_text()
	chain = chain_pattern.search(source)
	if not chain:
		raise ValueError(f"Shape chain not found in {module}")

	key = (behavior or "").lower()
	body = chain.group(1)
	branch_pattern = re.compile(rf"if \((?P<tests>.*?)\)\s*return {return_pattern}")
	for branch in branch_pattern.finditer(body):
		if any(needle in key for needle in _needles(branch.group("tests"), source)):
			return branch.group("shape")

	fallback = _FALLBACK.search(body.rstrip())
	if not fallback:
		raise ValueError(f"Shape chain in {module} has no fallback return")
	return fallback.group(1)


def marker_preview_shape(behavior: str) -> str:
	"""The `SHAPES` entry `markerShapeFor` resolves a behaviour to, by replaying its chain.

	Replaying rather than reading a table is the point: the substring tests are order-sensitive,
	and the order is what goes wrong - `five_lines` contains `line`, `triangle_cluster` contains
	`triangle`.
	"""
	return _resolve(behavior, PREVIEW_MODULE, _PREVIEW_CHAIN, _PREVIEW_RETURN)


def marker_stamp_factory(behavior: str) -> str:
	"""The element factory `stampShapeElements` resolves a behaviour to, by replaying its chain."""
	return _resolve(behavior, CHART_MODULE, _CHART_CHAIN, _CHART_RETURN)
