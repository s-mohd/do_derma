from __future__ import annotations

import re
from pathlib import Path
from unittest import TestCase

import frappe

CHART_CSS = Path(__file__).parents[1] / "public" / "js" / "chart" / "derma_chart.bundle.css"
DARK_SCOPE = '[data-theme="dark"] .dental-chart-page.derma-chart-page {'
CONTROL_VARIABLES = (
	"--text-color",
	"--heading-color",
	"--text-muted",
	"--control-bg",
	"--border-color",
	"--fg-color",
)


class TestChartDarkMode(TestCase):
	"""The chart is light-only, so desk dark mode must not leak dark text or
	control colours into it."""

	def get_dark_scope_variables(self):
		css = CHART_CSS.read_text()
		self.assertIn(DARK_SCOPE, css)
		block = css.split(DARK_SCOPE, 1)[1].split("}", 1)[0]
		return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block))

	def test_control_variables_are_pinned_light(self):
		variables = self.get_dark_scope_variables()
		for name in CONTROL_VARIABLES:
			self.assertIn(name, variables)
		self.assertNotEqual(variables["--text-color"].lower(), "#f8f8f8")
		self.assertNotEqual(variables["--control-bg"].lower(), "#232323")


OVERVIEW_FIRST_TOKEN = "--ov-bg:"
CHART_FIRST_TOKEN = "--chart-bg:"


def get_token_block(css: str, first_token: str) -> dict[str, str]:
	"""Variables of the rule block holding the first occurrence of `first_token`."""
	start = css.index(first_token)
	block = css[css.rindex("{", 0, start) : css.index("}", start)]
	return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block))


class TestChartTokens(TestCase):
	"""The chart wears the Patient Overview's light tokens; drift from do_health fails here."""

	def test_every_overview_token_has_a_matching_chart_token(self):
		overview_css = Path(frappe.get_app_path("do_health", "public", "css", "health_sidebar.css")).read_text()
		overview = get_token_block(overview_css, OVERVIEW_FIRST_TOKEN)
		chart = get_token_block(CHART_CSS.read_text(), CHART_FIRST_TOKEN)
		for name, value in overview.items():
			chart_name = name.replace("--ov-", "--chart-", 1)
			self.assertIn(chart_name, chart)
			self.assertEqual(chart[chart_name].strip(), value.strip(), chart_name)

	def test_chart_tokens_are_not_overridden_in_dark_mode(self):
		css = CHART_CSS.read_text()
		self.assertNotIn("--chart-", css.split(DARK_SCOPE, 1)[1].split("}", 1)[0])
		self.assertNotRegex(css, r'\[data-theme="dark"\][^{]*\{[^}]*--chart-')
