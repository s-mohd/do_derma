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


CHART_DIR = CHART_CSS.parent
STYLE_BLOCK = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# Component styles read --chart-* tokens; hex is not allowed.
HEX_ALLOWED: set[str] = set()


class TestChartAccent(TestCase):
	"""The chart's accent follows Do Health Settings; the old palette points at the new one."""

	def get_chart_tokens(self):
		return get_token_block(CHART_CSS.read_text(), CHART_FIRST_TOKEN)

	def test_accent_reads_the_settings_colour(self):
		tokens = self.get_chart_tokens()
		self.assertEqual(tokens["--chart-accent"].strip(), "var(--do-health-header-accent, #16a34a)")
		self.assertIn("var(--chart-accent)", tokens["--chart-accent-strong"])
		self.assertIn("var(--chart-accent)", tokens["--chart-accent-soft"])

	def test_old_palette_is_aliased(self):
		tokens = self.get_chart_tokens()
		old = {name: value for name, value in tokens.items() if name.startswith("--derma-")}
		self.assertEqual(len(old), 29)
		for name, value in old.items():
			self.assertRegex(value.strip(), r"^var\(--chart-[\w-]+\)$", name)
		root = CHART_CSS.read_text().split(":root {", 1)
		self.assertTrue(len(root) == 1 or "--derma-" not in root[1].split("}", 1)[0])


class TestChartComponentColours(TestCase):
	"""Component styles read tokens, not hex; the allowlist only shrinks."""

	def get_files_with_hex(self):
		found = set()
		for path in CHART_DIR.rglob("*.vue"):
			relative = path.relative_to(CHART_DIR).as_posix()
			if relative.startswith("annotation/"):
				continue
			styles = "".join(STYLE_BLOCK.findall(path.read_text()))
			if HEX_COLOUR.search(styles):
				found.add(relative)
		return found

	def test_no_new_hex_colours(self):
		self.assertEqual(self.get_files_with_hex() - HEX_ALLOWED, set())

	def test_allowlist_has_no_cleaned_files(self):
		self.assertEqual(HEX_ALLOWED - self.get_files_with_hex(), set())

	def test_teleports_target_the_section_card(self):
		self.assertIn('id="chart-section-actions"', (CHART_DIR / "components/shell/SectionCard.vue").read_text())
		for path in CHART_DIR.rglob("*.vue"):
			for tag in re.findall(r"<Teleport[^>]*>", path.read_text()):
				self.assertIn('to="#chart-section-actions"', tag, path.name)
				self.assertIn("defer", tag, path.name)
