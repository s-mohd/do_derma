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
		overview_css = Path(
			frappe.get_app_path("do_health", "public", "css", "health_sidebar.css")
		).read_text()
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
		self.assertIn(
			'id="chart-section-actions"', (CHART_DIR / "components/shell/SectionCard.vue").read_text()
		)
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
		doctype = Path(
			frappe.get_app_path(
				"healthcare", "healthcare", "doctype", "clinical_procedure", "clinical_procedure.json"
			)
		)
		status = next(
			field for field in json.loads(doctype.read_text())["fields"] if field["fieldname"] == "status"
		)
		tones = re.search(
			r"const STATUS_TONES = \{([^}]*)\}", (CHART_DIR / "components/ProcedurePanel.vue").read_text()
		).group(1)
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
		self.assertRegex(procedures, r"\.note-dot \{[^}]*var\(--chart-ok\)")

	def test_tokens_reach_content_rendered_outside_the_page(self):
		css = CHART_CSS.read_text()
		start = css.index(CHART_FIRST_TOKEN)
		selector = re.sub(
			r"/\*.*?\*/", "", css[css.rfind("}", 0, start) + 1 : css.rindex("{", 0, start)], flags=re.S
		)
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
	return "#" + "".join(
		f"{round(c * share + o * (1 - share)):02x}" for c, o in zip(channels, other, strict=True)
	)


def get_contrast(first: str, second: str) -> float:
	lighter, darker = sorted((get_relative_luminance(first), get_relative_luminance(second)), reverse=True)
	return (lighter + 0.05) / (darker + 0.05)


class TestChartDarkPalette(TestCase):
	"""Under desk dark mode the chart and its dialogs take the Overview's dark palette."""

	def get_dark_tokens(self):
		return get_variables(get_rule_body(CHART_CSS.read_text(), DARK_CHART_SELECTOR))

	def test_every_overview_dark_token_has_a_chart_twin(self):
		overview_css = Path(
			frappe.get_app_path("do_health", "public", "css", "health_sidebar.css")
		).read_text()
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
			self.assertGreaterEqual(
				get_contrast(mix(accent, 0.7, (255, 255, 255)), dark["--chart-surface"]), 4.5, accent
			)

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
		self.assertNotRegex(
			CHART_CSS.read_text(), r"background(-color)?:\s*var\(--(chart-text|derma-text|derma-navy)"
		)

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
				offenders += [
					path.name for style in STYLE_BLOCK.findall(path.read_text()) if white.search(style)
				]
		self.assertEqual(offenders, [])

	def test_danger_buttons_carry_the_shared_button_class(self):
		for path in CHART_DIR.rglob("*.vue"):
			for classes in re.findall(
				r'<button[^>]*\sclass="((?:[^"]*\s)?danger(?:\s[^"]*)?)"', path.read_text()
			):
				self.assertRegex(classes, r"\b(ghost|icon-btn)\b", f"{path.name}: {classes}")


def get_top_level_rules(css: str) -> list[tuple[int, str, str, str | None]]:
	"""(index, selector, body, enclosing @media or None) for every rule, in order."""
	css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
	rules, index, media, depth, start = [], 0, None, 0, 0
	for position, char in enumerate(css):
		if char == "{":
			prelude = css[start:position].strip()
			if depth == 0 and prelude.startswith("@media"):
				media = prelude
			elif not prelude.startswith("@") and depth == (1 if media else 0):
				rules.append([index, prelude, position, media])
				index += 1
			depth += 1
			start = position + 1
		elif char == "}":
			depth -= 1
			if rules and len(rules[-1]) == 4 and depth == (1 if media else 0):
				rules[-1].append(css[rules[-1][2] + 1 : position])
			if depth == 0:
				media = None
			start = position + 1
	return [(rule[0], rule[1], rule[4] if len(rule) > 4 else "", rule[3]) for rule in rules]


DECLARATION = re.compile(r"([\w-]+)\s*:\s*([^;]+);")


def get_shadowed_declarations(css: str) -> list[str]:
	"""Top-level declarations a later top-level rule overrides for every selector they apply to."""
	rules = [rule for rule in get_top_level_rules(css) if not rule[3]]
	shadowed = []
	for position, (_index, selector, body, _media) in enumerate(rules):
		parts = {part.strip() for part in selector.split(",")}
		later = [
			rule for rule in rules[position + 1 :] if parts <= {part.strip() for part in rule[1].split(",")}
		]
		overridden = {name for rule in later for name, _value in DECLARATION.findall(rule[2])}
		shadowed += [
			f"{selector.strip()[:50]} {{ {name} }}"
			for name, value in DECLARATION.findall(body)
			if name in overridden and "!important" not in value
		]
	return shadowed


class TestChartStylesheetStructure(TestCase):
	"""The early-closing @media trap: a later unconditional rule with the same selector silently
	overrides an earlier declaration, so editing the earlier one changes nothing."""

	def test_no_declaration_is_shadowed_by_a_later_rule_with_the_same_selector(self):
		self.assertEqual(get_shadowed_declarations(CHART_CSS.read_text()), [])


class TestChartHasNoBodyMap(TestCase):
	"""The chart page has no body map: no overlay that claims to draw on one, and no hidden
	body template that labels photos."""

	DEAD = (
		"selectedBodyTemplate",
		"ensureSelectedBodyTemplate",
		"loadBodyTemplate",
		"visibleMarks",
		"chartOverlayMode",
		"overlayTimelineVisit",
		"clearTimelineOverlay",
		"body map above",
		"Overlay Marks",
		"Clear Overlay",
	)

	def test_no_body_map_code_remains(self):
		chart = (CHART_DIR / "DermaChart.vue").read_text()
		self.assertEqual([name for name in self.DEAD if name in chart], [])

	def test_a_photo_takes_its_body_view_from_its_mark_only(self):
		chart = (CHART_DIR / "DermaChart.vue").read_text()
		for line in re.findall(r"(?:body_view|view|body_region):\s*[^\n]+", chart):
			if "selectedMark" in line:
				self.assertNotIn(
					"||", line.split("selectedMark", 1)[1].split('|| ""', 1)[0].replace("?.", ""), line
				)


PROCEDURE_PANEL = CHART_DIR / "components" / "ProcedurePanel.vue"


def get_component_parts(path: Path) -> tuple[str, str, str]:
	"""Template, script and scoped style of a single-file component."""
	template, rest = path.read_text().split("<script setup>", 1)
	script, _, style = rest.partition("<style scoped>")
	return template, script, style


def get_panel_parts() -> tuple[str, str, str]:
	"""Template, script and scoped style of the procedure panel."""
	return get_component_parts(PROCEDURE_PANEL)


def get_element(markup: str, opening: str) -> str:
	"""Markup from `opening` through its matching closing tag."""
	start = markup.index(opening)
	tag = re.match(r"<([\w-]+)", opening).group(1)
	depth = 0
	for match in re.finditer(rf"<(/?){tag}\b[^>]*?(/?)>", markup[start:]):
		if match.group(2):
			continue
		depth += -1 if match.group(1) else 1
		if depth == 0:
			return markup[start : start + match.end()]
	raise AssertionError(f"{opening} is never closed")


class TestProcedurePanelRestyle(TestCase):
	"""The Procedures tab wears the chart's shared vocabulary (spec 2026-10-03)."""

	def test_attention_filters_reuse_the_counted_predicates(self):
		template, script, _ = get_panel_parts()
		self.assertIn('if (billingFilter.value === "review") return rowNeedsBillingReview(row)', script)
		self.assertIn('if (labFilter.value === "follow_up") return rowNeedsLabFollowUp(row)', script)
		self.assertIn("if (rowNeedsBillingReview(row)) stats.billingReview += 1", script)
		self.assertIn('<option value="review">', template)
		self.assertIn('<option value="follow_up">', template)

	def test_counter_tiles_give_way_to_pill_counts_and_attention_chips(self):
		template, script, style = get_panel_parts()
		self.assertNotIn("summary-tile", template + style)
		self.assertIn("statusCounts[pill.key]", template)
		self.assertIn('v-for="chip in attentionChips"', template)
		for key, filter_name, value in (
			("note", "noteFilter", "missing_note"),
			("billing", "billingFilter", "review"),
			("lab", "labFilter", "follow_up"),
		):
			self.assertRegex(script, rf'{key}: \{{ filter: {filter_name}, value: "{value}"')
		self.assertIn("chip.count > 0 || isAttentionActive(chip.key)", script)

	def test_batch_size_lives_in_the_footer(self):
		template, _, _ = get_panel_parts()
		footer = get_element(template, '<div class="procedure-load-more-row"')
		self.assertIn('v-model.number="rowBatchSize"', footer)
		self.assertEqual(template.count('v-model.number="rowBatchSize"'), 1)

	def test_notes_live_in_the_actions_cluster(self):
		template, _, style = get_panel_parts()
		self.assertNotIn("note-presence-indicator", template + style)
		self.assertNotRegex(template, r"<th>[^<]*Notes")
		actions = get_element(template, '<td class="row-actions"')
		self.assertIn('data-test="procedure-note"', actions)

	def test_delete_turns_red_only_on_hover(self):
		_, _, style = get_panel_parts()
		self.assertNotRegex(style, r"\.icon-btn\.danger \{")
		self.assertRegex(
			style, r"\.icon-btn\.danger:hover:not\(:disabled\)[^{]*\{[^}]*var\(--chart-danger-text\)"
		)

	def test_price_edits_open_from_the_price_cell(self):
		template, _, _ = get_panel_parts()
		price = get_element(template, '<td class="price-cell"')
		details = get_element(template, '<div class="details-cell"')
		picker = get_element(
			price, '<div v-if="isEditable(row) && !rowIsInsurance(row)" class="override-picker"'
		)
		popover = get_element(
			picker,
			'<div v-if="overrideListOpenRow === row.name" :id="`price-editor-${row.name}`" class="override-popover"',
		)
		self.assertLess(picker.index('data-test="procedure-price"'), picker.index("override-popover"))
		for part in ('class="inline-input"', "no-charge-btn", "override-option"):
			self.assertIn(part, popover)
			self.assertNotIn(part, details)
		self.assertIn('data-test="procedure-row-saving"', price)
		self.assertNotIn("override-label", details)
		self.assertNotIn("no-charge-label", details)
		self.assertEqual(price.count("formatCurrency(displayPrice(row))"), 2)
		self.assertNotIn("computedPrice", price)

	def test_table_has_six_labelled_columns(self):
		template, _, _ = get_panel_parts()
		self.assertEqual(template.count("<col "), 6)
		headers = re.findall(r"<th>(.*?)</th>", template)
		self.assertEqual(len(headers), 6)
		for header in headers:
			self.assertRegex(header, r'^\{\{ __\("[\w ]+"\) \}\}$')
		self.assertEqual(template.count('colspan="6"'), 2)

	def test_row_chips_are_chart_pills(self):
		template, script, style = get_panel_parts()
		self.assertNotIn('class="detail-chip', template)
		self.assertNotIn('class="consent-badge', template)
		self.assertNotIn(".consent-badge", style)
		self.assertNotIn("labCaseStatusClass", template + script)
		status = get_element(template, '<td class="status-cell"')
		self.assertIn('data-tone="ok"', status)
		self.assertIn('data-tone="danger"', status)

	def test_every_scoped_class_has_a_user(self):
		markup, style = PROCEDURE_PANEL.read_text().split("<style scoped>", 1)
		style = re.sub(r"/\*.*?\*/", "", style, flags=re.S)
		rendered_by_desk = {
			"dental-chart-page",
			"modal-dialog",
			"modal-content",
			"modal-header",
			"modal-footer",
			"frappe-control",
			"ql-editor",
		}
		classes = set(re.findall(r"\.([a-zA-Z][\w-]*)", style)) - rendered_by_desk
		unused = {name for name in classes if not re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", markup)}
		self.assertEqual(unused, set())

	def test_stacked_cell_pills_wrap_inside_their_column(self):
		_, _, style = get_panel_parts()
		self.assertRegex(style, r"\.cell-stack \.chart-pill \{[^}]*white-space: normal;[^}]*max-width: 100%;")

	def test_committing_a_typed_price_keeps_the_editor_for_the_next_click(self):
		template, _, _ = get_panel_parts()
		start = template.index('class="inline-input"')
		price_input = template[start : template.index("/>", start)]
		self.assertIn('@change="updatePriceManual(row, $event.target.value)"', price_input)
		self.assertIn('@keydown.enter.prevent="closeOverrideList(); $event.target.blur()"', price_input)
		self.assertNotIn("$event.target.value); closeOverrideList()", template)

	def test_closing_the_price_editor_returns_focus_to_its_amount(self):
		template, script, _ = get_panel_parts()
		self.assertIn(
			':data-row="row.name"',
			get_element(
				template,
				'<button\n                      type="button"\n                      class="price-trigger"',
			),
		)
		close = script[script.index("function closeOverrideList() {") :]
		close = close[: close.index("\n}\n")]
		self.assertIn('document.activeElement?.closest?.(".override-popover")', close)
		self.assertIn(".price-trigger[data-row=", close)
		self.assertIn('class="override-picker" @keydown.escape.stop="closeOverrideList"', template)

	def test_long_detail_text_ends_in_an_ellipsis(self):
		_, _, style = get_panel_parts()
		self.assertRegex(style, r"\.detail-text span \{[^}]*min-width: 0;[^}]*text-overflow: ellipsis;")

	def test_scoped_rules_never_repeat_a_selector(self):
		_, _, style = get_panel_parts()
		style = re.sub(r"/\*.*?\*/", "", style, flags=re.S).split("@media", 1)[0]
		selectors = [selector.strip() for selector in re.findall(r"(?:^|\})\s*([^{}@]+?)\s*\{", style)]
		repeated = {selector for selector in selectors if selectors.count(selector) > 1}
		self.assertEqual(repeated, set())

	def test_narrow_rules_only_place_grid_children(self):
		_, _, style = get_panel_parts()
		narrow = style[style.index("@media (max-width: 768px)") :]
		self.assertNotIn(".history-search", narrow)
		self.assertNotIn(".clear-filters-btn", narrow)

	def test_price_editor_reads_the_chart_shadow_and_focus_tokens(self):
		template, _, style = get_panel_parts()
		self.assertRegex(style, r"\.override-popover \{[^}]*box-shadow: var\(--chart-shadow\);")
		self.assertNotIn("rgba(", style)
		self.assertRegex(style, r"\.price-trigger:focus-visible \{[^}]*box-shadow: var\(--chart-focus\);")
		trigger = get_element(
			template,
			'<button\n                      type="button"\n                      class="price-trigger"',
		)
		self.assertIn(':aria-controls="`price-editor-${row.name}`"', trigger)
		self.assertIn(':id="`price-editor-${row.name}`"', template)

	def test_history_stats_carry_only_what_the_chips_read(self):
		_, script, _ = get_panel_parts()
		self.assertNotIn("drafts", script)

	def test_a_chip_hides_while_its_select_holds_another_value(self):
		_, script, _ = get_panel_parts()
		self.assertIn('config.filter.value === "all" || isAttentionActive(key)', script)

	def test_three_action_buttons_fit_the_narrowest_table(self):
		_, _, style = get_panel_parts()
		width = int(re.search(r"\.procedure-table \{[^}]*min-width: (\d+)px;", style).group(1))
		share = int(re.search(r"\.col-actions \{\s*width: (\d+)%;", style).group(1))
		button = int(re.search(r"\.procedure-table \.icon-btn \{[^}]*width: (\d+)px;", style).group(1))
		padding = sum(
			map(
				int,
				re.search(
					r"td\.row-actions \{[^}]*padding-left: (\d+)px;\s*padding-right: (\d+)px;", style
				).groups(),
			)
		)
		self.assertGreaterEqual(width * share / 100, 3 * button + padding)

	def test_a_procedure_without_a_price_list_shows_no_placeholder_line(self):
		template, _, _ = get_panel_parts()
		self.assertIn('<span v-if="displayPriceList(row)" class="price-meta">', template)

	def test_hovering_the_note_icon_previews_the_note(self):
		template, script, style = get_panel_parts()
		start = template.index('data-test="procedure-note"')
		button = template[template.rindex("<button", 0, start) : template.index("</button>", start)]
		for handler in (
			'@mouseenter="showNotePreview(row, $event)"',
			'@focus="showNotePreview(row, $event)"',
			'@mouseleave="hideNotePreview"',
			'@blur="hideNotePreview"',
			'@keydown.escape="hideNotePreview"',
		):
			self.assertIn(handler, button)
		self.assertIn(
			":aria-describedby=\"notePreview?.row === row.name ? 'procedure-note-preview' : undefined\"",
			button,
		)
		self.assertIn(':title="getRowNoteRawValue(row) ? undefined : noteLabel(row)"', button)
		card = get_element(template, '<div\n      v-if="notePreview"')
		self.assertIn('id="procedure-note-preview"', card)
		self.assertIn('role="tooltip"', card)
		self.assertIn("{{ notePreview.text }}", card)
		show = script[script.index("function showNotePreview(") :]
		show = show[: show.index("\n}\n")]
		self.assertIn("const text = getRowNoteValue(row)", show)
		self.assertIn("if (!text) return", show)
		self.assertRegex(style, r"\.note-preview \{[^}]*position: fixed;")


ASSESSMENT_DIR = CHART_DIR / "components" / "assessment"


ASSESSMENT_HOOKS = (
	"assessment-mode-toggle",
	"assessment-section",
	"assessment-start",
	"assessment-panel",
	"assessment-error",
	"assessment-other-format",
	"assessment-advice",
	"assessment-advice-toggle",
	"assessment-advice-language",
	"assessment-print",
	"assessment-edit",
	"assessment-save",
	"annotate-consultation",
	"annotation-resume",
	"annotation-delete",
	"previous-visits",
	"previous-visit",
	"previous-visit-summary",
	"previous-visit-show-all",
	"previous-visits-more",
	"previous-visits-collapse",
	"voice-scribe",
	"voice-start",
	"voice-stop",
	"voice-pause",
	"voice-mic",
	"voice-silence",
	"voice-meter",
	"voice-refine",
	"voice-result",
	"voice-waveform",
)


def get_assessment_block() -> str:
	"""The Assessment tab's markup inside DermaChart.vue."""
	chart = (CHART_DIR / "DermaChart.vue").read_text()
	return chart.split("<template v-if=\"activeSection === 'assessment'\">", 1)[1].split(
		"<template v-else-if=\"activeSection === 'procedures'\">", 1
	)[0]


def get_assessment_sources() -> str:
	return get_assessment_block() + "".join(path.read_text() for path in ASSESSMENT_DIR.glob("*.vue"))


class TestAssessmentRestyle(TestCase):
	"""The Assessment tab wears the chart's shared vocabulary (spec 2026-10-03)."""

	def test_previous_visit_header_shows_format_and_procedures(self):
		template, script, _ = get_component_parts(ASSESSMENT_DIR / "PreviousVisitsPanel.vue")
		header = get_element(template, '<article v-for="visit in visits"')
		self.assertIn('data-test="previous-visit-mode"', header)
		self.assertIn("visit.procedures.slice(0, PROCEDURE_PILLS)", header)
		self.assertRegex(header, r':key="`\$\{visit\.encounter\}-procedure-\$\{index\}`"')
		self.assertIn("visit.procedures.length - PROCEDURE_PILLS", header)
		self.assertIn("const PROCEDURE_PILLS = 3", script)
		self.assertIn('<dt class="chart-label">', template)
		self.assertIn('class="chart-annotation-history chart-inner-card previous-visits"', template)

	def test_every_hook_survives(self):
		sources = get_assessment_sources() + (CHART_DIR / "DermaChart.vue").read_text()
		for hook in ASSESSMENT_HOOKS:
			self.assertIn(f'data-test="{hook}"', sources)

	def test_edit_save_and_print_live_in_the_card_header(self):
		template, script, style = get_component_parts(ASSESSMENT_DIR / "AssessmentPanel.vue")
		teleport = get_element(template, '<Teleport defer to="#chart-section-actions"')
		self.assertIn('<template v-if="hasEncounter && !loading">', teleport)
		for hook in ("assessment-print", "assessment-edit", "assessment-save", "assessment-status"):
			self.assertIn(f'data-test="{hook}"', teleport)
		self.assertNotIn("assessment-footer", template + style)
		self.assertNotIn("Read-only. Choose Edit to continue documenting.", script)
		self.assertNotIn('__("No changes")', script)
		self.assertIn('__("Unsaved changes")', script)

	def test_advice_print_choice_sits_with_the_advice(self):
		template, _, _ = get_component_parts(ASSESSMENT_DIR / "AssessmentPanel.vue")
		advice = get_element(template, '<section v-if="hasAdvice" class="advice-block"')
		self.assertIn('data-test="assessment-advice-toggle"', advice)
		self.assertIn('data-test="assessment-advice-language"', advice)

	def test_the_assessment_panel_is_not_a_card_in_a_card(self):
		_, _, style = get_component_parts(ASSESSMENT_DIR / "AssessmentPanel.vue")
		self.assertNotRegex(get_rule_body(style, ".assessment-panel {"), r"border:|background:")

	def test_other_format_pills_switch_through_the_confirm_prompt(self):
		template, script, _ = get_component_parts(ASSESSMENT_DIR / "AssessmentPanel.vue")
		row = get_element(
			template, '<div v-if="!editMode && otherModesWithContent.length" class="other-formats"'
		)
		self.assertIn('data-test="assessment-other-format"', row)
		self.assertIn('<span v-if="isModeInert(otherMode)" class="chart-pill" data-tone="caution"', row)
		self.assertIn("@click=\"emit('switch-mode', otherMode)\"", row)
		self.assertIn("return !props.availableModes.includes(mode)", script)
		self.assertIn('"switch-mode"', script)
		self.assertNotIn("otherFormatNote", script)
		block = get_assessment_block()
		self.assertIn(':mode-locked="assessmentModeLocked"', block)
		self.assertIn('@switch-mode="requestAssessmentModeChange"', block)

	def test_note_fields_use_labels_plain_text_and_chart_inputs(self):
		soap, _, soap_style = get_component_parts(ASSESSMENT_DIR / "SoapNoteFields.vue")
		self.assertIn('class="soap-label chart-label"', soap)
		self.assertNotRegex(get_rule_body(soap_style, ".soap-readonly {"), r"background|border")
		self.assertIn("background: var(--chart-surface);", get_rule_body(soap_style, ".soap-input {"))

		structured, _, structured_style = get_component_parts(
			ASSESSMENT_DIR / "StructuredAssessmentFields.vue"
		)
		self.assertIn('class="fields-section-title chart-label"', structured)
		self.assertIn(
			"text-transform: uppercase;",
			get_rule_body(structured_style, ".field-control-host:deep(.control-label) {"),
		)
		self.assertIn(
			"background: transparent;",
			get_rule_body(structured_style, ".field-control-host:deep(.like-disabled-input) {"),
		)
		self.assertNotIn("--control-bg", soap_style + structured_style)

	def test_dictation_result_is_pills_and_toggles(self):
		template, script, _ = get_component_parts(ASSESSMENT_DIR / "VoiceScribe.vue")
		result = get_element(
			template,
			"<div v-if=\"summary && ['idle', 'ready', 'failed'].includes(state)\" class=\"voice-result\"",
		)
		self.assertNotIn("<details", result)
		self.assertNotIn("<code", result)
		self.assertIn('data-test="voice-icd10"', result)
		self.assertIn(":aria-expanded=", result)
		self.assertRegex(template, r'class="ghost small"\s+data-test="voice-start"')
		self.assertRegex(script, r'watch\(summary, \(\) => \{\s+openExtra\.value = ""')
		css = CHART_CSS.read_text()
		self.assertIn("white-space: normal;", get_rule_body(css, ".voice-result-head .chart-pill {"))
		self.assertNotIn(".voice-result-head code", css)
		self.assertNotRegex(get_rule_body(css, ".voice-scribe {"), r"border:|background:")

	def test_one_filled_button_in_the_tab(self):
		block = get_assessment_block()
		self.assertNotIn('class="primary', block)
		for name in (
			"VoiceScribe.vue",
			"PreviousVisitsPanel.vue",
			"SoapNoteFields.vue",
			"StructuredAssessmentFields.vue",
		):
			self.assertNotIn('class="primary', (ASSESSMENT_DIR / name).read_text(), name)
		panel, _, _ = get_component_parts(ASSESSMENT_DIR / "AssessmentPanel.vue")
		primaries = re.findall(r'class="primary[^"]*"\s+data-test="([\w-]+)"', panel)
		self.assertCountEqual(primaries, ["assessment-start", "assessment-edit", "assessment-save"])

	def test_reference_blocks_sit_in_inner_cards_under_block_titles(self):
		block = get_assessment_block()
		self.assertIn(
			'<section class="chart-annotation-history chart-inner-card encounter-annotation-history">', block
		)
		self.assertIn('<i v-else class="fa-regular fa-pen-to-square" aria-hidden="true"></i>', block)
		self.assertRegex(
			block, r'<h3 class="assessment-block-title" data-tone="\w+">\s*<span class="block-icon"'
		)
		css = CHART_CSS.read_text()
		title = get_rule_body(css, ".clinical-soap-stack .assessment-block-title {")
		self.assertIn("font-weight: 600;", title)
		self.assertIn("color: var(--chart-text);", title)
		self.assertIn("gap: 24px;", get_rule_body(css, ".clinical-soap-stack {"))
		self.assertNotIn(".clinical-soap-stack > * + * {", css)
		self.assertNotIn(".encounter-annotation-history {", css)

	def test_read_mode_lists_labels_beside_values(self):
		soap, _, soap_style = get_component_parts(ASSESSMENT_DIR / "SoapNoteFields.vue")
		self.assertIn(":class=\"{ 'is-reading': !editMode }\"", soap)
		self.assertIn(
			"grid-template-columns: 180px minmax(0, 1fr);",
			get_rule_body(soap_style, ".soap-fields.is-reading .soap-field {"),
		)
		structured, _, structured_style = get_component_parts(
			ASSESSMENT_DIR / "StructuredAssessmentFields.vue"
		)
		self.assertIn(":class=\"{ 'is-reading': !editMode }\"", structured)
		self.assertIn(
			"grid-template-columns: 180px minmax(0, 1fr);",
			get_rule_body(
				structured_style, ".structured-fields.is-reading .field-control-host:deep(.form-group) {"
			),
		)
		for style in (soap_style, structured_style):
			self.assertIn("@media (max-width: 1100px)", style)

	def test_edit_fields_start_compact_and_grow(self):
		_, _, soap_style = get_component_parts(ASSESSMENT_DIR / "SoapNoteFields.vue")
		_, _, structured_style = get_component_parts(ASSESSMENT_DIR / "StructuredAssessmentFields.vue")
		for body in (
			get_rule_body(soap_style, ".soap-input {"),
			get_rule_body(structured_style, ".field-control-host:deep(textarea.form-control) {"),
		):
			self.assertIn("field-sizing: content;", body)
			self.assertIn("min-height: 72px;", body)
		_, structured_script, _ = get_component_parts(ASSESSMENT_DIR / "StructuredAssessmentFields.vue")
		self.assertIn(
			'if (control.$input?.is("textarea")) control.$input.css("height", "")', structured_script
		)

	def test_multiselect_reads_as_one_input(self):
		_, script, style = get_component_parts(ASSESSMENT_DIR / "StructuredAssessmentFields.vue")
		box = re.search(
			r"\n\n\.field-control-host:deep\(\.table-multiselect\.form-control\) \{([^}]*)\}", style
		).group(1)
		self.assertIn("min-height: 34px;", box)
		self.assertIn("flex-wrap: wrap;", box)
		self.assertIn(
			"flex: 1 1 120px;",
			get_rule_body(style, ".field-control-host:deep(.table-multiselect .link-field) {"),
		)
		chip = get_rule_body(style, ".field-control-host:deep(.table-multiselect .tb-selected-value) {")
		self.assertIn("border-radius: 999px;", chip)
		self.assertIn("font-size: 11.5px;", chip)
		self.assertIn('__("Add...")', script)

	def test_dictation_sits_on_one_row(self):
		template, _, _ = get_component_parts(ASSESSMENT_DIR / "VoiceScribe.vue")
		row = get_element(template, '<div class="voice-scribe-row">')
		self.assertIn('data-test="voice-refine"', row)
		self.assertIn("state === 'idle' && !hasNote", row)

	def test_format_switch_leads_the_header_and_drawings_align(self):
		css = CHART_CSS.read_text()
		self.assertIn("order: -1;", get_rule_body(css, ".tab-mode-toggle {"))
		self.assertIn("padding: 0;", get_rule_body(css, ".clinical-soap-stack .chart-annotation-list {"))

	def test_multiselect_inner_input_drops_desk_grey(self):
		_, _, style = get_component_parts(ASSESSMENT_DIR / "StructuredAssessmentFields.vue")
		self.assertIn(
			"background: transparent;",
			get_rule_body(style, ".field-control-host:deep(.table-multiselect input) {"),
		)


PRESCRIPTION_DIR = CHART_DIR / "components" / "prescription"
PRESCRIPTION_PANEL = PRESCRIPTION_DIR / "PrescriptionPanel.vue"
PRESCRIPTION_ROW = PRESCRIPTION_DIR / "PrescriptionRow.vue"


class TestPrescriptionRow(TestCase):
	"""One editable prescription line in the chart vocabulary (spec 2026-10-03)."""

	def test_link_cells_mount_desk_link_controls(self):
		_, script, _ = get_component_parts(PRESCRIPTION_ROW)
		self.assertIn("frappe.ui.form.make_control", script)
		self.assertIn('fieldtype: "Link"', script)
		self.assertIn("only_select: 1", script)
		self.assertNotIn('"Table"', script)

	def test_pickers_keep_escape_from_desk(self):
		template, _, _ = get_component_parts(PRESCRIPTION_ROW)
		hosts = re.findall(r'<div[^>]*class="picker-host"[^>]*>', template)
		self.assertEqual(len(hosts), 3)
		for host in hosts:
			self.assertIn("@keydown.escape.stop", host)

	def test_a_picker_starts_from_the_cell_value_so_clearing_counts(self):
		"""Desk's Link blur compares against `last_value`; an unseeded control never reports a clear."""
		_, script, _ = get_component_parts(PRESCRIPTION_ROW)
		self.assertIn("control.set_input(current)", script)
		self.assertIn("control.last_value = current", script)
		self.assertNotIn("$input?.val(", script)

	def test_read_only_rows_name_older_drugs_in_text_colour(self):
		"""Most stored rows predate the Medication link and carry only a drug name or item code."""
		template, script, style = get_component_parts(PRESCRIPTION_ROW)
		self.assertIn("{{ medicationLabel }}", template)
		self.assertIn("props.row.original.drug_name || drugCode", script)
		self.assertRegex(style, r"\.cell-input:disabled \{[^}]*color: var\(--chart-text\)")
		self.assertRegex(style, r"\.cell-input:disabled \{[^}]*opacity: 1;")

	def test_drug_code_sits_under_the_medication(self):
		template, _, _ = get_component_parts(PRESCRIPTION_ROW)
		medication = get_element(template, '<td class="medication-cell"')
		self.assertIn('data-test="prescription-choose-item"', medication)
		self.assertIn("row.linkedItems.length > 1", medication)
		self.assertIn('class="chart-spinner"', medication)

	def test_comment_and_delete_live_in_the_actions_cluster(self):
		template, _, _ = get_component_parts(PRESCRIPTION_ROW)
		actions = get_element(template, '<td class="row-actions"')
		for hook in ("prescription-comment", "prescription-delete"):
			self.assertIn(f'data-test="{hook}"', actions)
		self.assertIn('class="comment-preview"', actions)
		self.assertIn('data-test="prescription-comment-input"', template)

	def test_delete_turns_red_only_on_hover(self):
		_, _, style = get_component_parts(PRESCRIPTION_ROW)
		self.assertNotRegex(style, r"\.icon-btn\.danger \{")
		self.assertRegex(
			style, r"\.icon-btn\.danger:hover:not\(:disabled\)[^{]*\{[^}]*var\(--chart-danger-text\)"
		)


PRESCRIPTION_HOOKS = (
	"prescription-panel",
	"prescription-save",
	"prescription-row",
	"prescription-ordered-row",
	"prescription-comment",
	"prescription-error",
)


class TestPrescriptionPanelRestyle(TestCase):
	"""The Prescription tab is a native table in the chart vocabulary (spec 2026-10-03)."""

	def test_the_panel_lives_in_its_folder(self):
		self.assertTrue(PRESCRIPTION_PANEL.exists())
		self.assertFalse((CHART_DIR / "components" / "PrescriptionPanel.vue").exists())
		self.assertIn(
			'import PrescriptionPanel from "./components/prescription/PrescriptionPanel.vue"',
			(CHART_DIR / "DermaChart.vue").read_text(),
		)

	def test_no_desk_grid(self):
		template, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		self.assertNotIn("make_control", script)
		self.assertNotIn('"Table"', script)
		self.assertRegex(template, r'<table[^>]* class="prescription-table"')
		self.assertIn("<PrescriptionRow", template)

	def test_save_is_the_only_header_button(self):
		template, _, _ = get_component_parts(PRESCRIPTION_PANEL)
		header = get_element(template, '<Teleport defer to="#chart-section-actions">')
		self.assertRegex(header, r'class="primary small"\s+data-test="prescription-save"')
		self.assertEqual(header.count("<button"), 1)
		self.assertNotIn("Add medication", template)
		self.assertEqual(template.count("primary"), 1)

	def test_status_is_a_header_pill(self):
		template, script, style = get_component_parts(PRESCRIPTION_PANEL)
		for label in ("Finalized", "Saving...", "Unsaved changes"):
			self.assertIn(f'__("{label}")', script)
		self.assertNotIn("status-note", template + style)
		self.assertNotIn("Prescriptions are read-only", template + script)

	def test_ordered_rows_share_the_table(self):
		template, _, _ = get_component_parts(PRESCRIPTION_PANEL)
		ordered = get_element(template, '<tr v-for="row in orderedRows"')
		self.assertIn('data-tone="ok"', ordered)
		self.assertIn('__("Ordered")', ordered)
		self.assertNotIn('data-test="prescription-ordered"', template)

	def test_every_hook_exists(self):
		markup = PRESCRIPTION_PANEL.read_text() + PRESCRIPTION_ROW.read_text()
		for hook in PRESCRIPTION_HOOKS:
			self.assertIn(f'data-test="{hook}"', markup)

	def test_a_stale_medication_lookup_is_ignored(self):
		_, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		self.assertIn("const token = ++draft.lookup", script)
		self.assertIn("if (token !== draft.lookup) return", script)

	def test_save_keeps_fields_the_table_does_not_show(self):
		_, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		self.assertIn("({ ...draft.original, ...draft.values })", script)

	def test_save_names_the_first_gap_and_drops_blank_rows(self):
		_, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		self.assertIn('__("Row {0}: {1} is required.")', script)
		self.assertIn("drafts.value.filter((draft) => !isBlank(draft))", script)
		self.assertIn("if (validationError.value) return", script)

	def test_save_waits_for_a_change(self):
		template, _, _ = get_component_parts(PRESCRIPTION_PANEL)
		start = template.index('data-test="prescription-save"')
		save = template[start : template.index(">", start)]
		self.assertIn("saving", save)
		self.assertIn("!isDirty", save)

	def test_save_commits_a_typed_picker_value_first(self):
		"""Desk validates a typed link on blur, after Save's click would have sent the rows."""
		template, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		start = template.index('data-test="prescription-save"')
		save = template[start : template.index(">", start)]
		self.assertIn("@mousedown.prevent", save)
		self.assertLess(script.index(".commitPicker()"), script.index('emit("save"'))
		_, row_script, _ = get_component_parts(PRESCRIPTION_ROW)
		self.assertIn("defineExpose({ commitPicker })", row_script)

	def test_the_count_skips_rows_the_save_would_drop(self):
		_, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		self.assertIn("orderedRows.value.length + getPayload().length", script)

	def test_a_server_error_clears_once_the_rows_change(self):
		_, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		self.assertIn(
			"watch(() => props.error, () => (errorPayload.value = JSON.stringify(getPayload())), { immediate: true })",
			script,
		)
		self.assertIn("JSON.stringify(getPayload()) === errorPayload.value", script)
		self.assertNotIn("validationError.value || props.error", script)

	def test_a_blank_row_always_waits_at_the_bottom(self):
		_, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		self.assertIn("watch([() => props.rows, canEdit], resetDrafts, { immediate: true })", script)
		self.assertIn("function ensureTrailingDraft()", script)
		self.assertRegex(script, r"function resetDrafts\(\) \{[^}]*ensureTrailingDraft\(\)")
		self.assertNotIn("function addRow", script)
		apply = script.split("async function applyMedication", 1)[1].split("draft.filling = true", 1)[0]
		self.assertIn("ensureTrailingDraft()", apply)

	def test_the_trailing_row_is_muted_without_actions(self):
		template, script, style = get_component_parts(PRESCRIPTION_ROW)
		self.assertIn("isNext: { type: Boolean, default: false }", script)
		self.assertIn(":class=\"{ 'is-next': isNext }\"", template)
		self.assertIn('v-if="!isNext && (!readOnly || row.values.comment)"', template)
		self.assertIn('v-if="!readOnly && !isNext"', template)
		self.assertIn(".prescription-row.is-next", style)
		panel, _, _ = get_component_parts(PRESCRIPTION_PANEL)
		self.assertIn(':is-next="isTrailing(draft)"', panel)

	def test_a_repeated_medication_names_its_first_row(self):
		template, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		self.assertIn('v-for="(draft, index) in drafts"', template)
		self.assertIn(':duplicate-of="duplicateOf[orderedRows.length + index]"', template)
		self.assertIn("...orderedRows.value.map((row) => row.medication)", script)
		row_template, row_script, row_style = get_component_parts(PRESCRIPTION_ROW)
		self.assertIn("duplicateOf: { type: Number, default: 0 }", row_script)
		note = get_element(row_template, '<small v-if="duplicateOf"')
		self.assertIn('data-test="prescription-duplicate"', note)
		self.assertIn('__("Also prescribed in row {0}")', note)
		self.assertIn("var(--chart-caution-text)", row_style)

	def test_a_duplicate_never_blocks_save(self):
		_, script, _ = get_component_parts(PRESCRIPTION_PANEL)
		validation = script.split("const validationError", 1)[1].split("})", 1)[0]
		self.assertNotIn("duplicate", validation)


ASSESSMENT_BLOCK_TONES = {
	"Dictation": "info",
	"Clinical note": "accent",
	"Patient advice": "ok",
	"Drawings": "neutral",
	"Previous Visits": "neutral",
}
BLOCK_TITLE = re.compile(
	r'<h3 class="assessment-block-title" data-tone="(\w+)">\s*'
	r'<span class="block-icon" aria-hidden="true"><i class="fa-[\w -]+"></i></span>\s*'
	r'\{\{ __\("([^"]+)"\) \}\}'
)


class TestAssessmentColour(TestCase):
	"""Assessment colour marks meaning: AI blue, the note in the clinic accent, advice green."""

	def get_block_titles(self):
		paths = [*ASSESSMENT_DIR.glob("*.vue"), CHART_DIR / "DermaChart.vue"]
		markup = "".join(path.read_text() for path in paths)
		self.assertNotRegex(markup, r'class="assessment-block-title">')
		return {title: tone for tone, title in BLOCK_TITLE.findall(markup)}

	def test_every_block_title_carries_its_tone_and_icon(self):
		self.assertEqual(self.get_block_titles(), ASSESSMENT_BLOCK_TONES)

	def test_tones_read_chart_tokens(self):
		css = CHART_CSS.read_text()
		for tone in ("info", "accent", "ok"):
			body = get_rule_body(
				css, f'.dental-chart-page .assessment-block-title[data-tone="{tone}"] .block-icon'
			)
			self.assertIn(f"var(--chart-{tone}-soft)", body)
			self.assertIn(f"var(--chart-{tone}-text)", body)

	def test_the_dictation_result_reads_as_ai(self):
		template, _, _ = get_component_parts(ASSESSMENT_DIR / "VoiceScribe.vue")
		for hook in ("voice-diagnosis", "voice-icd10"):
			start = template.index(f'data-test="{hook}"')
			opening = template[template.rindex("<", 0, start) : template.index(">", start)]
			self.assertIn('data-tone="info"', opening)
		self.assertIn("var(--chart-info-soft)", get_rule_body(CHART_CSS.read_text(), ".voice-result {"))
		pill = get_rule_body(CHART_CSS.read_text(), '.voice-result .chart-pill[data-tone="info"] {')
		self.assertIn("var(--chart-surface)", pill)

	def test_patient_advice_sits_on_green(self):
		_, _, style = get_component_parts(ASSESSMENT_DIR / "AssessmentPanel.vue")
		self.assertIn("var(--chart-ok-soft)", get_rule_body(style, ".advice-block pre {"))

	def test_the_active_format_wears_the_accent(self):
		body = get_rule_body(
			CHART_CSS.read_text(), '.dental-chart-page .tab-mode-toggle button[data-active="true"]'
		)
		self.assertIn("var(--chart-accent-soft)", body)
		self.assertIn("var(--chart-accent-text)", body)

	def test_accent_text_on_accent_soft_is_readable(self):
		css = CHART_CSS.read_text()
		light = get_token_block(css, CHART_FIRST_TOKEN)
		dark = get_variables(get_rule_body(css, DARK_CHART_SELECTOR))
		themes = (
			(light["--chart-accent-strong"], (0, 0, 0), light["--chart-accent-soft"], "#ffffff"),
			(
				dark["--chart-accent-text"],
				(255, 255, 255),
				dark["--chart-accent-soft"],
				dark["--chart-surface"],
			),
		)
		for text_token, text_other, soft_token, surface in themes:
			text_share = int(re.search(r"(\d+)%", text_token).group(1)) / 100
			soft_share = int(re.search(r"(\d+)%", soft_token).group(1)) / 100
			surface_rgb = tuple(int(surface[i : i + 2], 16) for i in (1, 3, 5))
			for accent in ("#16a34a", "#EC864B"):
				text = mix(accent, text_share, text_other)
				soft = mix(accent, soft_share, surface_rgb)
				self.assertGreaterEqual(get_contrast(text, soft), 4.5, (accent, soft_token))

	def test_neutral_chips_stand_out_on_inner_cards(self):
		body = get_rule_body(
			CHART_CSS.read_text(),
			'.dental-chart-page .chart-inner-card .assessment-block-title[data-tone="neutral"] .block-icon',
		)
		self.assertIn("var(--chart-surface)", body)
		self.assertIn("border: 1px solid var(--chart-border-strong)", body)


CONSUMABLES_EDITOR = CHART_DIR / "components" / "consumables" / "ConsumablesEditor.vue"
CONSUMABLE_HOOKS = (
	"mark-consumables",
	"consumables-error",
	"consumable-line",
	"consumable-qty",
	"consumable-uom",
	"consumable-batch-facts",
	"consumable-batch-stock",
	"consumable-batch-expiry",
	"consumable-batch",
	"consumable-remove",
	"consumable-notice",
	"consumables-removed",
	"consumable-add",
	"consumable-reset",
	"consumable-add-row",
	"consumable-new-uom",
	"consumable-new-batch",
)


class TestConsumablesEditorRestyle(TestCase):
	"""The Materials editor wears the chart vocabulary of the table around it (2026-10-04)."""

	def test_head_and_columns_are_chart_labels(self):
		template, _, _ = get_component_parts(CONSUMABLES_EDITOR)
		head = get_element(template, '<div class="mark-consumables-head"')
		self.assertIn('<span class="chart-label">{{ label }}</span>', head)
		self.assertIn('data-test="consumables-count"', head)
		self.assertNotIn("<strong>", head)
		headers = re.findall(r"<th\b[^>]*>", template)
		self.assertTrue(headers)
		for header in headers:
			self.assertIn('class="chart-label"', header)

	def test_flags_are_chart_pills(self):
		template, _, style = get_component_parts(CONSUMABLES_EDITOR)
		self.assertNotIn("consumable-flag", template + style)
		self.assertRegex(template, r'class="chart-pill"[^>]*>\s*\{\{ __\("Changed"\) \}\}')
		self.assertRegex(
			template, r'class="chart-pill" data-tone="danger"[^>]*>\s*\{\{ __\("No conversion"\) \}\}'
		)
		self.assertNotRegex(style, r"tr\.overridden \{[^}]*background")

	def test_remove_is_an_icon_that_reddens_on_hover(self):
		template, _, style = get_component_parts(CONSUMABLES_EDITOR)
		start = template.index('data-test="consumable-remove"')
		button = template[template.rindex("<button", 0, start) : template.index("</button>", start)]
		self.assertIn('class="icon-btn danger"', button)
		self.assertIn("fa-trash-can", button)
		self.assertNotRegex(style, r"\.icon-btn\.danger \{")
		self.assertRegex(
			style, r"\.icon-btn\.danger:hover:not\(:disabled\)[^{]*\{[^}]*var\(--chart-danger-text\)"
		)

	def test_the_lot_shows_once(self):
		template, _, _ = get_component_parts(CONSUMABLES_EDITOR)
		self.assertIn('<b v-if="readOnly && row.batch.name">', template)
		self.assertNotIn('row.batch_no || "-"', template)

	def test_the_item_picker_keeps_escape_from_desk(self):
		template, _, _ = get_component_parts(CONSUMABLES_EDITOR)
		host = re.search(r'<div[^>]*class="consumable-link-host"[^>]*>', template).group(0)
		self.assertIn('@keydown.escape.stop="cancelItemPicker"', host)
		self.assertIn('ref="itemButton"', template)
		_, script, _ = get_component_parts(CONSUMABLES_EDITOR)
		self.assertIn("nextTick(() => itemButton.value?.focus())", script)
		self.assertNotIn('class="link-cell"', template)
		self.assertIn('class="cell-input"', template)

	def test_every_hook_survives(self):
		markup = CONSUMABLES_EDITOR.read_text()
		for hook in CONSUMABLE_HOOKS:
			self.assertIn(f'data-test="{hook}"', markup)

	def test_lot_pills_sit_beside_the_select(self):
		template, _, style = get_component_parts(CONSUMABLES_EDITOR)
		cell = get_element(template, '<div class="batch-cell"')
		self.assertIn('data-test="consumable-batch-facts"', cell)
		self.assertIn('data-test="consumable-batch"', cell)
		self.assertRegex(style, r"\.batch-cell \{[^}]*display: flex;")
		self.assertRegex(style, r"\.batch-cell \.consumable-select \{[^}]*order: -1;")


class TestAssessmentViewFormat(TestCase):
	"""A submitted visit's format switch changes only what is on screen (2026-10-04)."""

	def test_the_toggle_stays_usable_after_submission(self):
		chart = (CHART_DIR / "DermaChart.vue").read_text()
		toggle = get_element(chart, '<div\n                class="tab-mode-toggle"')
		self.assertNotIn(":disabled=", toggle)
		self.assertNotIn("locked after submission", chart)
		self.assertIn(":data-active=\"shownAssessmentMode === toggleMode ? 'true' : 'false'\"", toggle)

	def test_a_locked_switch_only_changes_the_view(self):
		chart = (CHART_DIR / "DermaChart.vue").read_text()
		start = chart.index("function requestAssessmentModeChange(target) {")
		body = chart[start : chart.index("\n}\n", start)]
		self.assertIn("if (assessmentModeLocked.value) return viewAssessmentMode(target)", body)
		start = chart.index("function viewAssessmentMode(target) {")
		view = chart[start : chart.index("\n}\n", start)]
		self.assertNotIn("frappe.call", view)
		self.assertIn("assessmentPanel.editing = false", view)
		self.assertIn(
			'assessmentViewMode.value = ""',
			chart.split("function applyAssessmentResponse(message) {", 1)[1].split("\n}\n", 1)[0],
		)

	def test_the_panel_shows_the_viewed_format_against_the_documented_one(self):
		block = get_assessment_block()
		self.assertIn(':mode="shownAssessmentMode"', block)
		self.assertIn(':documented-mode="assessmentPanel.mode"', block)
		template, script, _ = get_component_parts(ASSESSMENT_DIR / "AssessmentPanel.vue")
		self.assertIn('data-test="assessment-viewing"', template)
		self.assertIn("props.documentedMode && props.mode !== props.documentedMode", script)
		self.assertIn("if (isViewingOtherFormat.value) return false", script)
