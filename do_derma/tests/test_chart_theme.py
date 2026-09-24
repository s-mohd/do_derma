from __future__ import annotations

import re
from pathlib import Path
from unittest import TestCase

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
