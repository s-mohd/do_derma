from __future__ import annotations

from do_derma.patches.helpers import upsert_sidebar_item

SIDEBAR_ITEM = {
	"section": "Primary Nav",
	"label": "Derma Configuration",
	"display_group": "Clinical",
	"description": "Body maps, procedure templates, categories and how sessions are gated.",
	"icon": "fa-regular fa-sliders",
	"item_behavior": "Route",
	"route_type": "Page",
	"route_value": "derma-config",
	"context_requirement": "none",
	"requires_app": "do_derma",
	"sequence": 7,
	"is_active": 1,
}


def execute():
	"""Give the configuration workspace its only entry point in the app."""
	upsert_sidebar_item(SIDEBAR_ITEM)
