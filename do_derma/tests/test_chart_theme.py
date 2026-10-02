from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import TestCase

import frappe

CHART_CSS = Path(__file__).parents[1] / "public" / "js" / "chart" / "derma_chart.bundle.css"
DARK_SCOPE = '[data-theme="dark"] .derma-annotation-modal {'
CONTROL_VARIABLES = (
	"--text-color",
	"--heading-color",
	"--text-muted",
	"--control-bg",
	"--border-color",
	"--fg-color",
)


class TestChartStudioLight(TestCase):
	"""Desk dark mode must not leak dark text or control colours into the light annotation studio."""

	def get_dark_scope_variables(self):
		css = CHART_CSS.read_text()
		self.assertIn(DARK_SCOPE, css)
		block = css.split(DARK_SCOPE, 1)[1].split("}", 1)[0]
		return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block))

	def test_studio_stays_light(self):
		variables = self.get_dark_scope_variables()
		for name in CONTROL_VARIABLES:
			self.assertIn(name, variables)
		self.assertNotEqual(variables["--text-color"].lower(), "#f8f8f8")
		self.assertNotEqual(variables["--control-bg"].lower(), "#232323")
		self.assertIn("color-scheme: light", CHART_CSS.read_text().split(DARK_SCOPE, 1)[1].split("}", 1)[0])


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

CHART_DIR = CHART_CSS.parent
STYLE_BLOCK = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b")


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
	"""Component styles read --chart-* tokens, never hex."""

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

	def test_component_styles_carry_no_hex(self):
		self.assertEqual(self.get_files_with_hex(), set())

	def test_teleports_target_the_section_card(self):
		self.assertIn('id="chart-section-actions"', (CHART_DIR / "components/shell/SectionCard.vue").read_text())
		for path in CHART_DIR.rglob("*.vue"):
			for tag in re.findall(r"<Teleport[^>]*>", path.read_text()):
				self.assertIn('to="#chart-section-actions"', tag, path.name)
				self.assertIn("defer", tag, path.name)


def get_relative_luminance(hex_colour: str) -> float:
	channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
	linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
	return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


class TestChartReviewFindings(TestCase):
	"""Regressions the phase 2b review caught."""

	def test_filled_buttons_keep_white_text_readable(self):
		strong = get_token_block(CHART_CSS.read_text(), CHART_FIRST_TOKEN)["--chart-accent-strong"]
		share = int(re.search(r"var\(--chart-accent\) (\d+)%, black", strong).group(1)) / 100
		for accent in ("#16a34a", "#EC864B"):
			darkened = "#" + "".join(f"{round(int(accent[i : i + 2], 16) * share):02x}" for i in (1, 3, 5))
			contrast = 1.05 / (get_relative_luminance(darkened) + 0.05)
			self.assertGreaterEqual(contrast, 4.5, accent)

	def test_every_procedure_status_has_a_tone(self):
		doctype = Path(frappe.get_app_path("healthcare", "healthcare", "doctype", "clinical_procedure", "clinical_procedure.json"))
		status = next(field for field in json.loads(doctype.read_text())["fields"] if field["fieldname"] == "status")
		tones = re.search(r"const STATUS_TONES = \{([^}]*)\}", (CHART_DIR / "components/ProcedurePanel.vue").read_text()).group(1)
		for option in status["options"].split("\n"):
			self.assertRegex(tones, rf'(^|[\s{{,])"?{re.escape(option)}"?:', option)

	def test_procedure_pills_carry_no_legacy_badge_class(self):
		self.assertNotRegex((CHART_DIR / "components/ProcedurePanel.vue").read_text(), r'class="badge\b')
		self.assertNotIn(".dental-chart-page .badge", CHART_CSS.read_text())

	def test_accent_and_ok_green_stay_apart(self):
		tabs = (CHART_DIR / "components/shell/SectionTabs.vue").read_text()
		hero = (CHART_DIR / "components/shell/ChartHero.vue").read_text()
		procedures = (CHART_DIR / "components/ProcedurePanel.vue").read_text()
		self.assertRegex(tabs, r'\[data-active="true"\] \{[^}]*var\(--chart-accent-soft\)')
		self.assertRegex(hero, r"\.chart-hero-avatar \{[^}]*var\(--chart-accent-soft\)")
		self.assertRegex(hero, r'\.chart-hero-status\[data-tone="ok"\] \{[^}]*var\(--chart-ok-text\)')
		self.assertRegex(hero, r'\.chart-hero-readiness\[data-tone="ok"\] \{[^}]*var\(--chart-ok-text\)')
		self.assertRegex(procedures, r'Completed: "ok"')
		self.assertRegex(procedures, r"\.note-presence-indicator\.present i \{[^}]*var\(--chart-ok\)")

	def test_tokens_reach_content_rendered_outside_the_page(self):
		css = CHART_CSS.read_text()
		start = css.index(CHART_FIRST_TOKEN)
		selector = re.sub(r"/\*.*?\*/", "", css[css.rfind("}", 0, start) + 1 : css.rindex("{", 0, start)], flags=re.S)
		hosts = [part.strip() for part in selector.split(",")]
		for host in (".dental-chart-page.derma-chart-page", ".derma-annotation-modal", ".modal"):
			self.assertIn(host, hosts)


DARK_CHART_SELECTOR = '[data-theme="dark"] .dental-chart-page.derma-chart-page'
OVERVIEW_DARK_SELECTOR = '[data-theme="dark"] .do-health-drawer--overview'


def get_rule_body(css: str, selector_start: str) -> str:
	"""Body of the first rule whose selector list starts with `selector_start`."""
	css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
	start = css.index(selector_start)
	return css[css.index("{", start) + 1 : css.index("}", start)]


def get_variables(body: str) -> dict[str, str]:
	return {name: value.strip() for name, value in re.findall(r"(--[\w-]+):\s*([^;]+);", body)}


def mix(hex_colour: str, share: float, other: tuple[int, int, int]) -> str:
	channels = [int(hex_colour[i : i + 2], 16) for i in (1, 3, 5)]
	return "#" + "".join(f"{round(c * share + o * (1 - share)):02x}" for c, o in zip(channels, other, strict=True))


def get_contrast(first: str, second: str) -> float:
	lighter, darker = sorted((get_relative_luminance(first), get_relative_luminance(second)), reverse=True)
	return (lighter + 0.05) / (darker + 0.05)


class TestChartDarkPalette(TestCase):
	"""Under desk dark mode the chart and its dialogs take the Overview's dark palette."""

	def get_dark_tokens(self):
		return get_variables(get_rule_body(CHART_CSS.read_text(), DARK_CHART_SELECTOR))

	def test_every_overview_dark_token_has_a_chart_twin(self):
		overview_css = Path(frappe.get_app_path("do_health", "public", "css", "health_sidebar.css")).read_text()
		overview = get_variables(get_rule_body(overview_css, OVERVIEW_DARK_SELECTOR))
		dark = self.get_dark_tokens()
		for name, value in overview.items():
			self.assertEqual(dark.get(name.replace("--ov-", "--chart-", 1)), value, name)

	def test_dark_block_covers_page_and_dialogs_but_not_the_studio(self):
		css = re.sub(r"/\*.*?\*/", "", CHART_CSS.read_text(), flags=re.S)
		start = css.index(DARK_CHART_SELECTOR)
		selectors = [part.strip() for part in css[start : css.index("{", start)].split(",")]
		self.assertIn('[data-theme="dark"] .modal', selectors)
		self.assertFalse(any("derma-annotation-modal" in part for part in selectors))
		self.assertIn("color-scheme: dark", get_rule_body(CHART_CSS.read_text(), DARK_CHART_SELECTOR + " {"))

	def test_accent_text_reads_on_dark(self):
		dark = self.get_dark_tokens()
		self.assertEqual(dark["--chart-accent-text"], "color-mix(in srgb, var(--chart-accent) 70%, white)")
		for accent in ("#16a34a", "#EC864B"):
			self.assertGreaterEqual(get_contrast(mix(accent, 0.7, (255, 255, 255)), dark["--chart-surface"]), 4.5, accent)

	def test_light_accent_text_matches_filled_buttons(self):
		light = get_token_block(CHART_CSS.read_text(), CHART_FIRST_TOKEN)
		self.assertEqual(light["--chart-accent-text"], "var(--chart-accent-strong)")

	def test_modal_selector_only_in_token_blocks(self):
		css = re.sub(r"/\*.*?\*/", "", CHART_CSS.read_text(), flags=re.S)
		for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
			if not re.search(r"\.modal(?![\w-])", selector) or "body.derma-annotation-open" in selector:
				continue
			real = [line for line in body.split(";") if line.strip() and not line.strip().startswith("--")]
			self.assertEqual(real, [], selector.strip())


TOKEN_BLOCK_STARTS = (".dental-chart-page.derma-chart-page,", DARK_CHART_SELECTOR, DARK_SCOPE.rstrip(" {"))


class TestChartStylesheetColours(TestCase):
	"""Outside the token blocks the stylesheet reads tokens, so both themes reach every rule."""

	def test_no_hex_outside_token_blocks(self):
		css = re.sub(r"/\*.*?\*/", "", CHART_CSS.read_text(), flags=re.S)
		offenders = []
		for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
			if selector.strip().startswith(TOKEN_BLOCK_STARTS):
				continue
			offenders += [f"{selector.strip()[:60]}: {value}" for value in HEX_COLOUR.findall(body)]
		self.assertEqual(offenders, [])

	def test_text_on_fills_is_never_the_surface_token(self):
		self.assertNotRegex(CHART_CSS.read_text(), r"(?<![\w-])color:\s*var\(--derma-white\)")

	def test_fills_never_use_a_text_token(self):
		self.assertNotRegex(CHART_CSS.read_text(), r"background(-color)?:\s*var\(--(chart-text|derma-text|derma-navy)")

	def test_no_translucent_white_outside_token_blocks(self):
		white = re.compile(r"rgba?\(\s*255\s*,\s*255\s*,\s*255")
		css = re.sub(r"/\*.*?\*/", "", CHART_CSS.read_text(), flags=re.S)
		offenders = [
			selector.strip()[:60]
			for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)
			if not selector.strip().startswith(TOKEN_BLOCK_STARTS) and white.search(body)
		]
		for path in CHART_DIR.rglob("*.vue"):
			if not path.relative_to(CHART_DIR).as_posix().startswith("annotation/"):
				offenders += [path.name for style in STYLE_BLOCK.findall(path.read_text()) if white.search(style)]
		self.assertEqual(offenders, [])

	def test_danger_buttons_carry_the_shared_button_class(self):
		for path in CHART_DIR.rglob("*.vue"):
			for classes in re.findall(r'<button[^>]*\sclass="((?:[^"]*\s)?danger(?:\s[^"]*)?)"', path.read_text()):
				self.assertRegex(classes, r"\b(ghost|icon-btn)\b", f"{path.name}: {classes}")
