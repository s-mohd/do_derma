from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma.config.marker_preview import marker_preview_behaviors
from do_derma.patches.ensure_derma_body_template_editor_page import (
	execute as ensure_body_template_editor_page,
)
from do_derma.patches.ensure_derma_config_page import execute as ensure_config_page
from do_derma.patches.seed_derma_config_sidebar_item import execute as seed_config_sidebar_item
from do_derma.settings import FEATURE_TOGGLES
from do_derma.tests.test_api import DermaTestHelpers


class TestConfigOverview(DermaTestHelpers, IntegrationTestCase):
	"""The config workspace lists what an administrator has to fix, so it shows
	disabled rows the chart deliberately hides."""

	def _template_row(self, overview, template):
		return next(row for row in overview["body_templates"] if row["name"] == template)

	def test_lists_a_disabled_body_template(self):
		template = self._make_body_template(disabled=1)

		overview = api.get_derma_config_overview()

		self.assertEqual(self._template_row(overview, template)["disabled"], 1)

	def test_counts_active_and_retired_areas_separately(self):
		template = self._make_body_template()
		self._make_body_template_part(template, "Left Cheek")
		self._make_body_template_part(template, "Right Cheek")
		self._make_body_template_part(template, "Chin", disabled=1)

		row = self._template_row(api.get_derma_config_overview(), template)

		self.assertEqual(row["area_count"], 2)
		self.assertEqual(row["retired_area_count"], 1)

	def test_a_template_with_no_areas_counts_zero(self):
		template = self._make_body_template()

		row = self._template_row(api.get_derma_config_overview(), template)

		self.assertEqual((row["area_count"], row["retired_area_count"]), (0, 0))

	def test_a_broken_sub_query_degrades_to_an_empty_list(self):
		with patch.object(api, "get_config_body_templates", side_effect=Exception("boom")):
			overview = api.get_derma_config_overview()

		self.assertEqual(overview["body_templates"], [])
		self.assertIn("body templates", overview["errors"])

	def test_one_broken_section_leaves_the_others_readable(self):
		template = self._make_body_template()

		with patch.object(api, "get_config_procedure_templates", side_effect=Exception("boom")):
			overview = api.get_derma_config_overview()

		self.assertEqual(overview["procedure_templates"], [])
		self.assertIn("procedure templates", overview["errors"])
		self.assertTrue(self._template_row(overview, template))
		self.assertIsInstance(overview["categories"], list)

	def test_reports_that_this_session_may_write_templates(self):
		self.assertTrue(api.get_derma_config_overview()["can_write"])

	def test_a_session_without_write_permission_gets_a_read_only_payload(self):
		"""The panel hides its edit affordances from this, rather than offering edits the
		save would refuse."""
		with patch.object(frappe, "has_permission", return_value=False):
			overview = api.get_derma_config_overview()

		self.assertFalse(overview["can_write"])


class ConfigTemplateHelpers:
	def _make_derma_template(self, **custom):
		"""A Clinical Procedure Template carrying whichever custom_derma_* fields the
		test cares about, skipping the ones this site has not created."""
		token = frappe.generate_hash(length=8)
		doc = frappe.get_doc(
			{
				"doctype": "Clinical Procedure Template",
				"template": f"Derma{token}",
				"item_code": f"Derma{token}",
				"description": f"Derma{token} - config fixture.",
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
			}
		)
		doc.set("is_billable", 0)
		for fieldname, value in custom.items():
			if api._has_field("Clinical Procedure Template", fieldname):
				doc.set(fieldname, value)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _make_category(self, title, **extra):
		if frappe.db.exists("Derma Procedure Category", title):
			return title
		return (
			frappe.get_doc(
				{
					"doctype": "Derma Procedure Category",
					"title": title,
					"workflow": "Aesthetic",
					"marker_behavior": "numbered_dot",
					**extra,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _procedure_row(self, overview, template):
		return next(row for row in overview["procedure_templates"] if row["name"] == template)

	def _category_row(self, overview, category):
		return next(row for row in overview["categories"] if row["name"] == category)


class TestConfigProcedureTemplates(ConfigTemplateHelpers, IntegrationTestCase):
	"""The template owns its required fields, with the two safety flags appending theirs.
	The config list names the owner of every field so a misconfiguration is visible
	without opening the desk form."""

	def test_lists_a_disabled_template(self):
		template = self._make_derma_template(custom_derma_required_fields=json.dumps(["dose"]), disabled=1)

		self.assertEqual(self._procedure_row(api.get_derma_config_overview(), template)["disabled"], 1)

	def test_names_the_owner_of_every_required_field(self):
		template = self._make_derma_template(
			custom_derma_required_fields=json.dumps(["dose"]),
			custom_derma_product_tracking_required=1,
			custom_derma_device_settings_required=1,
		)

		row = self._procedure_row(api.get_derma_config_overview(), template)

		self.assertEqual(
			{field["fieldname"]: field["source"] for field in row["required_fields"]},
			{
				"dose": "template",
				"product_name": "product_tracking",
				"lot_no": "product_tracking",
				"expiry_date": "product_tracking",
				"device": "device_settings",
				"settings": "device_settings",
			},
		)

	def test_the_first_owner_of_a_field_wins(self):
		template = self._make_derma_template(
			custom_derma_required_fields=json.dumps(["lot_no"]),
			custom_derma_product_tracking_required=1,
		)

		row = self._procedure_row(api.get_derma_config_overview(), template)
		sources = [field["source"] for field in row["required_fields"] if field["fieldname"] == "lot_no"]

		self.assertEqual(sources, ["template"])

	def test_a_clinic_named_category_grants_no_requirements(self):
		"""The category name owned a hard-coded set until the template became the sole
		owner. A template in a category called Botox now requires exactly what it says."""
		category = self._make_category("Botox")
		template = self._make_derma_template(custom_derma_category=category)

		row = self._procedure_row(api.get_derma_config_overview(), template)

		self.assertEqual(row["required_fields"], [])
		self.assertIn("no_required_fields", row["warnings"])

	def test_reports_a_required_field_the_chart_cannot_enforce(self):
		template = self._make_derma_template(
			custom_derma_required_fields=json.dumps(["invented_field"]),
		)

		row = self._procedure_row(api.get_derma_config_overview(), template)

		self.assertEqual(
			[(field["fieldname"], field["enforced"]) for field in row["required_fields"]],
			[("invented_field", False)],
		)
		self.assertIn("unenforced_required_fields", row["warnings"])

	def test_reports_a_field_the_template_lists_and_its_own_json_opts_out_of(self):
		"""One document disagreeing with itself: the required list names `dose`, the
		variables row calls it optional. The row wins in the chart, so the list entry is
		enforced nowhere - which is what the warning has always meant."""
		template = self._make_derma_template(
			custom_derma_required_fields=json.dumps(["dose"]),
			custom_derma_variables_json=json.dumps([{"label": "Dose", "required": False}]),
		)

		row = self._procedure_row(api.get_derma_config_overview(), template)

		self.assertEqual(
			[(field["fieldname"], field["enforced"]) for field in row["required_fields"]],
			[("dose", False)],
		)
		self.assertIn("unenforced_required_fields", row["warnings"])

	def test_reports_a_field_the_variables_json_marks_required(self):
		template = self._make_derma_template(
			custom_derma_marker_behavior="numbered_dot",
			custom_derma_variables_json=json.dumps([{"label": "Dose", "required": True}]),
		)

		row = self._procedure_row(api.get_derma_config_overview(), template)

		self.assertEqual(
			row["required_fields"], [{"fieldname": "dose", "source": "variables_json", "enforced": True}]
		)
		self.assertNotIn("no_required_fields", row["warnings"])

	def test_warns_when_a_template_requires_nothing(self):
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")

		row = self._procedure_row(api.get_derma_config_overview(), template)

		self.assertEqual(row["required_fields"], [])
		self.assertIn("no_required_fields", row["warnings"])

	def test_warns_when_the_variables_json_cannot_be_read(self):
		template = self._make_derma_template(
			custom_derma_marker_behavior="numbered_dot",
			custom_derma_variables_json="{not json",
		)

		row = self._procedure_row(api.get_derma_config_overview(), template)

		self.assertIn("unreadable_variables", row["warnings"])
		self.assertEqual(row["variable_count"], 0)

	def test_counts_the_variables_the_chart_renders(self):
		"""A required field with no row of its own still reaches the clinician, so the
		count is the chart's list rather than the JSON's length."""
		template = self._make_derma_template(
			custom_derma_variables_json=json.dumps([{"label": "Plane"}]),
			custom_derma_device_settings_required=1,
		)

		row = self._procedure_row(api.get_derma_config_overview(), template)

		self.assertEqual(row["variable_count"], 3)

	def test_counts_the_variables_a_readable_template_declares(self):
		template = self._make_derma_template(
			custom_derma_marker_behavior="numbered_dot",
			custom_derma_variables_json=json.dumps(
				[{"label": "Dose", "fieldtype": "Float"}, {"label": "Plane"}]
			),
		)

		row = self._procedure_row(api.get_derma_config_overview(), template)

		self.assertEqual(row["variable_count"], 2)
		self.assertNotIn("unreadable_variables", row["warnings"])

	def test_draws_the_category_marker_when_the_template_has_none(self):
		"""The card shows what the chart will stamp, and the chart falls back to the
		category, so a template with no marker of its own is not drawn blank."""
		category = self._make_category("Editor Inherits", marker_behavior="hatch", marker_color="#b91c1c")
		# Explicitly empty: Frappe fills a Select with its first option when the field is
		# left out entirely, which is what "inherit" has to survive.
		template = self._make_derma_template(custom_derma_category=category, custom_derma_marker_behavior="")

		marker = self._procedure_row(api.get_derma_config_overview(), template)["effective_marker"]

		self.assertEqual(marker, {"behavior": "hatch", "color": "#b91c1c", "inherited": True})

	def test_a_template_with_its_own_marker_inherits_nothing(self):
		category = self._make_category("Editor Owns", marker_behavior="hatch")
		template = self._make_derma_template(
			custom_derma_category=category, custom_derma_marker_behavior="x_mark"
		)

		marker = self._procedure_row(api.get_derma_config_overview(), template)["effective_marker"]

		self.assertEqual(marker["behavior"], "x_mark")
		self.assertFalse(marker["inherited"])

	def test_reports_a_marker_preset_that_overrides_the_shape(self):
		template = self._make_derma_template(
			custom_derma_marker_behavior="numbered_dot",
			custom_derma_marker_preset_json=json.dumps([{"type": "ellipse"}]),
		)

		self.assertTrue(self._procedure_row(api.get_derma_config_overview(), template)["has_marker_preset"])


class TestProcedureTemplateEditor(ConfigTemplateHelpers, IntegrationTestCase):
	"""One read and one save behind the config panel's detail view. The doctype's own
	permissions and timestamp check run on top of the role gate - the panel never
	elevates and never merges."""

	def _stored(self, template, fieldname):
		return frappe.db.get_value("Clinical Procedure Template", template, fieldname)

	def test_reads_the_fields_the_panel_edits(self):
		category = self._make_category("Editor Reads")
		template = self._make_derma_template(
			custom_derma_category=category,
			custom_derma_marker_behavior="x_mark",
			custom_derma_marker_color="#b91c1c",
			custom_derma_allowed_body_templates="Face Front, Scalp",
			custom_derma_note_template="Lesion excised.",
			custom_derma_consent_required=1,
		)

		payload = api.get_derma_procedure_template(template)

		self.assertEqual(payload["name"], template)
		self.assertEqual(payload["category"], category)
		self.assertEqual(payload["marker_behavior"], "x_mark")
		self.assertEqual(payload["marker_color"], "#b91c1c")
		self.assertEqual(payload["allowed_body_templates"], ["Face Front", "Scalp"])
		self.assertEqual(payload["note_template"], "Lesion excised.")
		self.assertEqual(payload["consent_required"], 1)
		self.assertTrue(payload["modified"])

	def test_refuses_an_unknown_template(self):
		with self.assertRaises(frappe.ValidationError):
			api.get_derma_procedure_template("does-not-exist")

	def test_reads_an_empty_template_for_the_panel_to_create_one(self):
		"""New mode renders the same detail view, so it asks for the same payload."""
		payload = api.get_derma_procedure_template("")

		self.assertFalse(payload["name"])
		self.assertEqual(payload["variables"], [])
		self.assertTrue(payload["marker_behaviors"])

	def test_offers_the_marker_behaviours_this_site_configured(self):
		"""A behaviour added by property setter has to reach the panel without a code
		change, so the options come from meta rather than a literal list."""
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")
		field = frappe.get_meta("Clinical Procedure Template").get_field("custom_derma_marker_behavior")

		payload = api.get_derma_procedure_template(template)

		self.assertEqual(
			payload["marker_behaviors"],
			[option.strip() for option in (field.options or "").split("\n") if option.strip()],
		)

	def test_names_the_owner_of_every_required_field_it_reads(self):
		template = self._make_derma_template(
			custom_derma_variables_json=json.dumps([{"label": "Dose", "required": True}]),
			custom_derma_product_tracking_required=1,
		)

		payload = api.get_derma_procedure_template(template)

		self.assertEqual(
			{field["fieldname"]: field["source"] for field in payload["required_fields"]},
			{
				"product_name": "product_tracking",
				"lot_no": "product_tracking",
				"expiry_date": "product_tracking",
				"dose": "variables_json",
			},
		)

	def test_writes_the_core_basics(self):
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")

		api.save_derma_procedure_template(
			template, {"description": "Updated by the panel.", "rate": 250, "disabled": 1}
		)

		self.assertEqual(self._stored(template, "description"), "Updated by the panel.")
		self.assertEqual(self._stored(template, "rate"), 250)
		self.assertEqual(self._stored(template, "disabled"), 1)

	def test_writes_the_derma_fields(self):
		category = self._make_category("Editor Writes")
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")

		api.save_derma_procedure_template(
			template,
			{
				"category": category,
				"marker_behavior": "target",
				"marker_color": "#0891b2",
				"note_template": "Cryotherapy applied.",
				"consent_required": 1,
				"device_settings_required": 1,
			},
		)

		self.assertEqual(self._stored(template, "custom_derma_category"), category)
		self.assertEqual(self._stored(template, "custom_derma_marker_behavior"), "target")
		self.assertEqual(self._stored(template, "custom_derma_marker_color"), "#0891b2")
		self.assertEqual(self._stored(template, "custom_derma_note_template"), "Cryotherapy applied.")
		self.assertEqual(self._stored(template, "custom_derma_consent_required"), 1)
		self.assertEqual(self._stored(template, "custom_derma_device_settings_required"), 1)

	def test_writes_the_marker_size(self):
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")

		payload = api.save_derma_procedure_template(template, {"marker_size": 1.5})

		self.assertEqual(self._stored(template, "custom_derma_marker_size"), 1.5)
		self.assertEqual(payload["marker_size"], 1.5)

	def test_refuses_a_marker_size_outside_the_allowed_range(self):
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")

		with self.assertRaises(frappe.ValidationError):
			api.save_derma_procedure_template(template, {"marker_size": 6})

		self.assertFalse(self._stored(template, "custom_derma_marker_size"))

	def test_refuses_a_marker_size_that_is_not_a_number(self):
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")

		with self.assertRaises(frappe.ValidationError):
			api.save_derma_procedure_template(template, {"marker_size": "huge"})

	def test_the_range_it_advertises_is_the_range_it_accepts(self):
		"""The panel builds its slider from this range, so a validator that disagreed with
		it would reject a value the slider can produce."""
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")
		limits = api.get_derma_procedure_template(template)["marker_size_range"]

		api.save_derma_procedure_template(template, {"marker_size": limits["max"]})
		self.assertEqual(self._stored(template, "custom_derma_marker_size"), limits["max"])

		api.save_derma_procedure_template(template, {"marker_size": limits["min"]})
		self.assertEqual(self._stored(template, "custom_derma_marker_size"), limits["min"])

		with self.assertRaises(frappe.ValidationError):
			api.save_derma_procedure_template(template, {"marker_size": limits["max"] + limits["step"]})

	def test_an_empty_marker_size_reads_back_as_unset(self):
		"""The panel needs "never set" to look different from a deliberate 1.0, so the
		reset control has something to return to."""
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")
		api.save_derma_procedure_template(template, {"marker_size": 1.75})

		payload = api.save_derma_procedure_template(template, {"marker_size": ""})

		self.assertEqual(payload["marker_size"], 0)

	def test_an_empty_marker_hands_the_decision_back_to_the_category(self):
		category = self._make_category("Editor Clears", marker_behavior="hatch", marker_color="#b91c1c")
		template = self._make_derma_template(
			custom_derma_category=category, custom_derma_marker_behavior="x_mark"
		)

		payload = api.save_derma_procedure_template(template, {"marker_behavior": ""})

		self.assertEqual(self._stored(template, "custom_derma_marker_behavior"), "")
		self.assertEqual(
			payload["effective_marker"], {"behavior": "hatch", "color": "#b91c1c", "inherited": True}
		)

	def test_stores_allowed_body_templates_the_way_the_chart_gate_reads_them(self):
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")

		api.save_derma_procedure_template(template, {"allowed_body_templates": ["Face Front", "Scalp"]})

		self.assertEqual(self._stored(template, "custom_derma_allowed_body_templates"), "Face Front,Scalp")

	def test_allowing_no_body_template_restricts_nothing(self):
		template = self._make_derma_template(
			custom_derma_marker_behavior="numbered_dot",
			custom_derma_allowed_body_templates="Face Front",
		)

		api.save_derma_procedure_template(template, {"allowed_body_templates": []})

		self.assertEqual(self._stored(template, "custom_derma_allowed_body_templates"), "")

	def test_the_required_list_is_derived_rather_than_taken_from_the_client(self):
		"""The variables and the safety flags own it. A client that sends its own list
		cannot make the chart demand a field nothing records."""
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")

		api.save_derma_procedure_template(
			template,
			{
				"custom_derma_required_fields": json.dumps(["invented"]),
				"required_fields": ["invented"],
				"variables": [{"label": "Dose", "required": True}],
			},
		)

		self.assertEqual(json.loads(self._stored(template, "custom_derma_required_fields")), ["dose"])

	def test_refuses_a_save_that_started_from_a_stale_read(self):
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")
		stale = api.get_derma_procedure_template(template)["modified"]
		frappe.db.set_value("Clinical Procedure Template", template, "description", "Changed elsewhere.")

		with self.assertRaises(frappe.TimestampMismatchError):
			api.save_derma_procedure_template(template, {"description": "Changed here.", "modified": stale})

		self.assertEqual(self._stored(template, "description"), "Changed elsewhere.")

	def test_refuses_a_caller_who_cannot_write_the_doctype(self):
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")

		with patch.object(frappe, "has_permission", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				api.save_derma_procedure_template(template, {"description": "Not mine to change."})

	def test_creates_a_template_the_overview_then_lists(self):
		category = self._make_category("Editor Creates")
		token = frappe.generate_hash(length=8)

		payload = api.save_derma_procedure_template(
			"",
			{
				"template": f"Derma{token}",
				"item_code": f"Derma{token}",
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
				"description": "Created from the config panel.",
				"category": category,
				"is_billable": 0,
			},
		)

		self.assertEqual(payload["name"], f"Derma{token}")
		self.assertEqual(
			self._procedure_row(api.get_derma_config_overview(), payload["name"])["category"], category
		)

	def test_refuses_a_new_template_with_no_name(self):
		with self.assertRaises(frappe.ValidationError):
			api.save_derma_procedure_template("", {"description": "Nameless."})

	def test_reads_a_json_encoded_payload(self):
		"""frappe.call sends the values as a JSON string."""
		template = self._make_derma_template(custom_derma_marker_behavior="numbered_dot")

		api.save_derma_procedure_template(template, json.dumps({"description": "Encoded."}))

		self.assertEqual(self._stored(template, "description"), "Encoded.")


class TestMarkerPreviewCoverage(IntegrationTestCase):
	"""The config page draws each marker itself, in a plain Vue bundle, because the chart's
	shapes are Excalidraw element factories in the React bundle. Nothing but this test
	notices when a behaviour is added to the field and not to the preview."""

	def test_every_configured_behaviour_has_a_preview_shape(self):
		field = frappe.get_meta("Clinical Procedure Template").get_field("custom_derma_marker_behavior")
		options = {option.strip() for option in (field.options or "").split("\n") if option.strip()}

		self.assertTrue(options <= set(marker_preview_behaviors()))


class TestConfigCategories(ConfigTemplateHelpers, IntegrationTestCase):
	"""What a category is worth once its requirement fields are gone: marker behaviour,
	defaults, and how many templates would break if it were deleted."""

	def test_lists_a_disabled_category(self):
		category = self._make_category(f"Derma Cfg {frappe.generate_hash(length=6)}", disabled=1)

		self.assertEqual(self._category_row(api.get_derma_config_overview(), category)["disabled"], 1)

	def test_counts_the_templates_pointing_at_a_category(self):
		category = self._make_category(f"Derma Cfg {frappe.generate_hash(length=6)}")
		self._make_derma_template(custom_derma_category=category)
		self._make_derma_template(custom_derma_category=category)

		self.assertEqual(self._category_row(api.get_derma_config_overview(), category)["template_count"], 2)

	def test_carries_no_requirement_fields(self):
		"""The five requirement fields nothing read are gone from the doctype, so the
		payload cannot offer a place to configure into a void."""
		category = self._make_category(f"Derma Cfg {frappe.generate_hash(length=6)}")

		row = self._category_row(api.get_derma_config_overview(), category)

		self.assertEqual([key for key in row if key.endswith("_required") or key == "required_fields"], [])


class TestConfigReadiness(DermaTestHelpers, IntegrationTestCase):
	"""Session completion is gated in the browser only. The panel reports the mode the
	server would apply and says so while nothing on the server applies it."""

	def test_reports_the_enforcement_mode(self):
		readiness = api.get_derma_config_overview()["readiness"]

		self.assertIn(readiness["enforcement"], ("Warn", "Block"))
		self.assertIsInstance(readiness["todo_downgrades_blockers"], bool)

	def test_warns_while_the_gate_is_client_side(self):
		"""A site whose settings cannot express the mode has no server-side gate at all -
		which is the one thing this panel has to say."""
		unconfigurable = {
			"enforcement": "Warn",
			"todo_downgrades_blockers": True,
			"is_configurable": False,
		}
		with patch.object(api, "get_readiness_settings", return_value=unconfigurable):
			readiness = api.get_derma_config_overview()["readiness"]

		self.assertIn("completion_gate_is_client_side", readiness["warnings"])

	def test_a_configurable_site_stops_warning(self):
		configured = {
			"enforcement": "Block",
			"todo_downgrades_blockers": False,
			"is_configurable": True,
		}
		with patch.object(api, "get_readiness_settings", return_value=configured):
			readiness = api.get_derma_config_overview()["readiness"]

		self.assertEqual(readiness["enforcement"], "Block")
		self.assertFalse(readiness["todo_downgrades_blockers"])
		self.assertEqual(readiness["warnings"], [])

	def test_reports_every_feature_toggle(self):
		readiness = api.get_derma_config_overview()["readiness"]

		reported = [toggle["fieldname"] for toggle in readiness["feature_toggles"]]
		self.assertEqual(sorted(reported), sorted(FEATURE_TOGGLES))
		for toggle in readiness["feature_toggles"]:
			self.assertIsInstance(toggle["enabled"], bool)

	def test_a_broken_readiness_read_leaves_the_lists_alone(self):
		template = self._make_body_template()

		with patch.object(api, "get_config_readiness", side_effect=Exception("boom")):
			overview = api.get_derma_config_overview()

		self.assertEqual(overview["readiness"], {})
		self.assertIn("readiness", overview["errors"])
		self.assertIn(template, [row["name"] for row in overview["body_templates"]])


class TestConfigHealth(ConfigTemplateHelpers, DermaTestHelpers, IntegrationTestCase):
	"""The rail counts what each tool has to fix. Counting on the server keeps the badge
	and the panel from disagreeing on a site whose data neither of them chose."""

	def test_counts_every_tool_by_the_rule_its_panel_shows(self):
		sections = {
			"body_templates": [{"warnings": ["no_areas"]}, {"warnings": []}],
			"procedure_templates": [{"warnings": ["no_required_fields"]}, {"warnings": []}],
			"readiness": {"warnings": ["completion_gate_is_client_side"]},
		}

		self.assertEqual(
			api.get_config_health(sections),
			{"body-templates": 1, "procedure-templates": 1, "readiness": 1},
		)

	def test_a_degraded_section_counts_nothing(self):
		sections = {
			"body_templates": [],
			"procedure_templates": [],
			"readiness": {},
		}

		self.assertEqual(set(api.get_config_health(sections).values()), {0})

	def test_a_body_template_with_no_areas_needs_attention(self):
		template = self._make_body_template()

		overview = api.get_derma_config_overview()
		row = next(row for row in overview["body_templates"] if row["name"] == template)

		self.assertEqual(row["warnings"], ["no_areas"])
		self.assertGreaterEqual(overview["health"]["body-templates"], 1)

	def test_retired_areas_do_not_make_a_template_chartable(self):
		template = self._make_body_template()
		self._make_body_template_part(template, "Chin", disabled=1)

		row = next(
			row for row in api.get_derma_config_overview()["body_templates"] if row["name"] == template
		)

		self.assertEqual(row["warnings"], ["no_areas"])

	def test_a_retired_template_with_no_areas_is_not_a_problem(self):
		template = self._make_body_template(disabled=1)

		row = next(
			row for row in api.get_derma_config_overview()["body_templates"] if row["name"] == template
		)

		self.assertEqual(row["warnings"], [])

	def test_a_template_with_a_live_area_is_not_a_problem(self):
		template = self._make_body_template()
		self._make_body_template_part(template, "Left Cheek")

		row = next(
			row for row in api.get_derma_config_overview()["body_templates"] if row["name"] == template
		)

		self.assertEqual(row["warnings"], [])

	def test_the_overview_carries_one_count_per_tool_with_a_rule(self):
		"""Categories have no rule of their own, so they carry no count at all rather than
		one that can only ever be zero."""
		health = api.get_derma_config_overview()["health"]

		self.assertEqual(sorted(health), ["body-templates", "procedure-templates", "readiness"])
		for count in health.values():
			self.assertIsInstance(count, int)

	def test_a_broken_section_reports_no_false_health(self):
		with patch.object(api, "get_config_procedure_templates", side_effect=Exception("boom")):
			overview = api.get_derma_config_overview()

		self.assertEqual(overview["health"]["procedure-templates"], 0)
		self.assertIn("procedure templates", overview["errors"])


class TestConfigSidebarItem(IntegrationTestCase):
	"""The workspace had no entry point anywhere in the app. The patch plants one, and
	runs on live sites, so a re-run must leave a single row alone."""

	ITEM = "Primary Nav-Derma Configuration"

	def setUp(self):
		if not frappe.db.exists("DocType", "Health Sidebar Item"):
			self.skipTest("do_health is not installed on this site")

	def test_it_routes_to_the_config_page(self):
		seed_config_sidebar_item()

		item = frappe.get_doc("Health Sidebar Item", self.ITEM)
		self.assertEqual((item.route_type, item.route_value), ("Page", "derma-config"))
		self.assertEqual(item.context_requirement, "none")
		self.assertTrue(item.is_active)

	def test_re_running_keeps_exactly_one_row(self):
		seed_config_sidebar_item()
		seed_config_sidebar_item()

		self.assertEqual(
			frappe.db.count(
				"Health Sidebar Item", {"section": "Primary Nav", "label": "Derma Configuration"}
			),
			1,
		)


class TestPagePatches(IntegrationTestCase):
	"""Both pages are source-backed, so these patches only matter on sites without
	developer mode - where a re-run must be free."""

	def test_re_running_leaves_an_unchanged_row_alone(self):
		for patch_execute, page in (
			(ensure_config_page, "derma-config"),
			(ensure_body_template_editor_page, "derma-body-template-editor"),
		):
			with self.subTest(page=page):
				patch_execute()
				before = frappe.db.get_value("Page", page, "modified")
				patch_execute()
				self.assertEqual(frappe.db.get_value("Page", page, "modified"), before)

	def test_it_recreates_a_deleted_row(self):
		if frappe.conf.developer_mode:
			# Deleting and re-inserting a source-backed Page rewrites its JSON on disk here,
			# and the patch only exists for sites where that never happens.
			self.skipTest("developer_mode writes the Page row back to the app source")
		frappe.delete_doc("Page", "derma-config", force=True, ignore_permissions=True)

		ensure_config_page()

		self.assertEqual(frappe.db.get_value("Page", "derma-config", "title"), "Derma Configuration")
