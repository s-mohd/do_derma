import { APIRequestContext, expect, test } from "@playwright/test";
import { SEED } from "../helpers/derma";
import { createDoc, deleteDoc } from "../helpers/frappe";

/**
 * The configuration workspace (/app/derma-config). Its fixture is a disabled body template
 * created by the spec itself: the seeded maps are shared, and the point of this list is that
 * it shows the rows the chart hides.
 */
test.describe("Derma configuration workspace", () => {
	let template = "";
	let title = "";

	test.beforeEach(async ({ request }) => {
		const stamp = Date.now();
		title = `E2E Config Map ${stamp}`;
		template = await plantDisabledTemplate(request, title, stamp);
	});

	test.afterEach(async ({ request }) => {
		if (!template) return;
		await deleteDoc(request, "Derma Body Template", template);
		template = "";
	});

	async function plantDisabledTemplate(
		request: APIRequestContext,
		templateTitle: string,
		stamp: number,
	): Promise<string> {
		const created = await createDoc<{ name: string }>(request, "Derma Body Template", {
			title: templateTitle,
			template_type: "Face",
			gender: "Female",
			view_key: `e2e_config_map_${stamp}`,
			sequence: 99,
			disabled: 1,
		});
		return created.name;
	}

	test("lists a disabled body template the chart would hide", async ({ page }) => {
		await page.goto("/app/derma-config");
		await expect(page.locator('[data-test="derma-config-root"]')).toBeVisible();

		const row = page.locator(`[data-test="config-body-template-row"][data-template="${template}"]`);
		await expect(row).toContainText(title);
		await expect(row.locator('[data-test="config-body-template-disabled"]')).toBeVisible();
		await expect(row.locator('[data-test="config-area-count"]')).toHaveText("0");
	});

	test("opens the designer on that template in one click", async ({ page }) => {
		await page.goto("/app/derma-config");
		await expect(page.locator('[data-test="derma-config-root"]')).toBeVisible();

		await page
			.locator(`[data-test="config-body-template-row"][data-template="${template}"]`)
			.locator('[data-test="config-design-areas"]')
			.click();

		await expect(page.locator('[data-test="body-map-designer"]')).toBeVisible();
		expect(new URL(page.url()).searchParams.get("template")).toBe(template);
	});

	test("every rail item leads somewhere, and the annotation link leads out", async ({ page }) => {
		await page.goto("/app/derma-config");
		await expect(page.locator('[data-test="derma-config-root"]')).toBeVisible();
		await expect(page.locator('[data-test="config-body-templates"]')).toBeVisible();

		const panels: Record<string, string> = {
			"procedure-templates": "config-procedure-templates",
			categories: "config-categories",
			readiness: "config-readiness",
		};
		for (const [tool, panel] of Object.entries(panels)) {
			await page.locator(`[data-test="config-rail-item-${tool}"]`).click();
			await expect(page.locator(`[data-test="${panel}"]`)).toBeVisible();
			await expect(page.locator('[data-test="config-body-templates"]')).toBeHidden();
		}

		await page.locator('[data-test="config-rail-item-body-templates"]').click();
		await expect(page.locator('[data-test="config-body-templates"]')).toBeVisible();
		await expect(page.locator('[data-test="config-rail-item-annotation-templates"]')).toHaveAttribute(
			"href",
			"/app/annotation-template",
		);
	});
});

/**
 * The procedure template and category lists. Their fixtures are created by the spec: the
 * required-field owners only differ on a template configured to disagree with itself, and
 * the seeded templates deliberately require nothing.
 */
test.describe("Derma configuration lists", () => {
	let category = "";
	let template = "";
	let itemCode = "";

	test.beforeEach(async ({ request }) => {
		const stamp = Date.now();
		category = await plantCategory(request, `E2E Config Category ${stamp}`);
		itemCode = `E2EConfig${stamp}`;
		template = await plantProcedureTemplate(request, itemCode, category);
	});

	test.afterEach(async ({ request }) => {
		if (template) await deleteDoc(request, "Clinical Procedure Template", template);
		if (itemCode) await deleteDoc(request, "Item", itemCode);
		if (category) await deleteDoc(request, "Derma Procedure Category", category);
		template = itemCode = category = "";
	});

	async function plantCategory(request: APIRequestContext, title: string): Promise<string> {
		const created = await createDoc<{ name: string }>(request, "Derma Procedure Category", {
			title,
			workflow: "Aesthetic",
			marker_behavior: "numbered_dot",
			required_fields: JSON.stringify(["dose"]),
		});
		return created.name;
	}

	async function plantProcedureTemplate(
		request: APIRequestContext,
		code: string,
		procedureCategory: string,
	): Promise<string> {
		// healthcare's after_insert builds an Item from item_code, so both it and the
		// item group have to be supplied here.
		const created = await createDoc<{ name: string }>(request, "Clinical Procedure Template", {
			template: code,
			item_code: code,
			item_group: SEED.itemGroup,
			description: `${code} - fixture for the do_derma config workspace spec.`,
			is_billable: 0,
			custom_derma_category: procedureCategory,
			custom_derma_required_fields: JSON.stringify(["dose", "invented_field"]),
			custom_derma_product_tracking_required: 1,
			custom_derma_variables_json: "{not json",
		});
		return created.name;
	}

	async function openTool(page: import("@playwright/test").Page, tool: string) {
		await page.goto("/app/derma-config");
		await expect(page.locator('[data-test="derma-config-root"]')).toBeVisible();
		await page.locator(`[data-test="config-rail-item-${tool}"]`).click();
	}

	test("names the owner of every required field", async ({ page }) => {
		await openTool(page, "procedure-templates");

		const row = page.locator(
			`[data-test="config-procedure-template-row"][data-template="${template}"]`,
		);
		await expect(
			row.locator('[data-test="config-required-field"][data-source="template"]'),
		).toHaveCount(2);
		await expect(
			row.locator('[data-test="config-required-field"][data-source="product_tracking"]'),
		).toHaveCount(3);
	});

	test("marks a required field the chart cannot enforce", async ({ page }) => {
		await openTool(page, "procedure-templates");

		const row = page.locator(
			`[data-test="config-procedure-template-row"][data-template="${template}"]`,
		);
		await expect(row.locator('[data-test="config-required-field"][data-enforced="0"]')).toHaveText(
			/invented_field/,
		);
		await expect(
			row.locator('[data-test="config-template-warning"][data-warning="unenforced_required_fields"]'),
		).toBeVisible();
	});

	test("warns that the variables JSON cannot be read", async ({ page }) => {
		await openTool(page, "procedure-templates");

		const row = page.locator(
			`[data-test="config-procedure-template-row"][data-template="${template}"]`,
		);
		await expect(
			row.locator('[data-test="config-template-warning"][data-warning="unreadable_variables"]'),
		).toBeVisible();
		// dose plus the three product-tracking fields still reach the chart as defaults.
		await expect(row.locator('[data-test="config-variable-count"]')).toHaveText("4");
		await expect(page.locator('[data-test="config-template-warning-count"]')).toBeVisible();
	});

	test("shows a seeded template that requires nothing", async ({ page }) => {
		await openTool(page, "procedure-templates");

		const row = page.locator(
			`[data-test="config-procedure-template-row"][data-template="${SEED.pointTemplate}"]`,
		);
		await expect(
			row.locator('[data-test="config-template-warning"][data-warning="no_required_fields"]'),
		).toBeVisible();
	});

	test("flags the category fields no code reads, and counts its templates", async ({ page }) => {
		await openTool(page, "categories");

		const row = page.locator(`[data-test="config-category-row"][data-category="${category}"]`);
		await expect(
			row.locator('[data-test="config-category-unread-field"][data-field="required_fields"]'),
		).toBeVisible();
		await expect(row.locator('[data-test="config-category-template-count"]')).toHaveText("1");
	});
});

/**
 * The readiness panel. It needs no fixture: it reports the site's own Derma Settings,
 * which on a site without the enforcement field is Warn plus the client-side-gate warning.
 */
test.describe("Derma configuration readiness", () => {
	test("reports the enforcement mode and every feature toggle", async ({ page }) => {
		await page.goto("/app/derma-config");
		await expect(page.locator('[data-test="derma-config-root"]')).toBeVisible();
		await page.locator('[data-test="config-rail-item-readiness"]').click();

		const panel = page.locator('[data-test="config-readiness"]');
		await expect(panel.locator('[data-test="config-readiness-enforcement"]')).toHaveAttribute(
			"data-mode",
			/Warn|Block/,
		);
		await expect(panel.locator('[data-test="config-readiness-todo-downgrade"]')).toBeVisible();
		await expect(panel.locator('[data-test="config-feature-toggle"]')).toHaveCount(3);
	});

	test("says the completion gate lives in the browser", async ({ page }) => {
		await page.goto("/app/derma-config");
		await expect(page.locator('[data-test="derma-config-root"]')).toBeVisible();
		await page.locator('[data-test="config-rail-item-readiness"]').click();

		await expect(
			page.locator(
				'[data-test="config-readiness-warning"][data-warning="completion_gate_is_client_side"]',
			),
		).toBeVisible();
	});
});
