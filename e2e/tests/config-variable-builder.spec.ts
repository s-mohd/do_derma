import { APIRequestContext, Page, expect, test } from "@playwright/test";
import { SEED } from "../helpers/derma";
import { getDoc, updateDoc } from "../helpers/frappe";

/**
 * The variable builder in the configuration workspace (/app/derma-config). A variable set used
 * to be hand-typed JSON in a Code field with no validation until the chart rendered it.
 *
 * The spec borrows the seeded `E2E Filler` template and puts its variables back afterwards -
 * `workers: 1` is what makes that safe, and re-running the seeder repairs a killed run.
 */
const SEEDED_VARIABLES = [
	{ variable_name: "Product", fieldname: "product", label: "Product", type: "Data" },
	{
		variable_name: "Plane",
		fieldname: "plane",
		label: "Plane",
		type: "Select",
		options: "Subdermal\nSupraperiosteal",
	},
];

test.describe("Procedure variable builder", () => {
	test.afterEach(async ({ request }) => {
		await restoreTemplate(request);
	});

	async function restoreTemplate(request: APIRequestContext): Promise<void> {
		await updateDoc(request, "Clinical Procedure Template", SEED.pointTemplate, {
			custom_derma_variables_json: JSON.stringify(SEEDED_VARIABLES),
			custom_derma_required_fields: JSON.stringify([]),
			custom_derma_product_tracking_required: 0,
		});
	}

	async function openBuilder(page: Page): Promise<void> {
		await page.goto("/app/derma-config");
		await expect(page.locator('[data-test="derma-config-root"]')).toBeVisible();
		await page.locator('[data-test="config-rail-item-procedure-templates"]').click();

		await page
			.locator(`[data-test="config-procedure-template-row"][data-template="${SEED.pointTemplate}"]`)
			.locator('[data-test="config-edit-variables"]')
			.click();
		await expect(page.locator('[data-test="config-variable-builder"]')).toBeVisible();
		await expect(page.locator('[data-test="config-variable-row"]').first()).toBeVisible();
	}

	test("adds a required variable without typing JSON", async ({ page, request }) => {
		await openBuilder(page);
		await expect(page.locator('[data-test="config-variable-row"]')).toHaveCount(2);

		await page.locator('[data-test="config-add-variable"]').click();
		const added = page.locator('[data-test="config-variable-row"]').last();
		await added.locator('[data-test="config-variable-label"]').fill("Needle Gauge");
		await expect(added.locator('[data-test="config-variable-fieldname"]')).toHaveText("needle_gauge");
		await added.locator('[data-test="config-variable-required"]').check();
		const [saved] = await Promise.all([
			page.waitForResponse("**/api/method/do_derma.api.save_derma_template_variables"),
			page.locator('[data-test="config-save-variables"]').click(),
		]);
		expect(saved.status()).toBe(200);

		await expect(page.locator('[data-test="config-variable-error"]')).toHaveCount(0);
		await expect(
			page.locator('[data-test="config-variable-row"][data-fieldname="needle_gauge"]'),
		).toBeVisible();

		const template = await getDoc<{
			custom_derma_variables_json: string;
			custom_derma_required_fields: string;
		}>(request, "Clinical Procedure Template", SEED.pointTemplate);
		const stored = JSON.parse(template.custom_derma_variables_json);
		expect(stored.map((variable: { fieldname: string }) => variable.fieldname)).toEqual([
			"product",
			"plane",
			"needle_gauge",
		]);
		expect(JSON.parse(template.custom_derma_required_fields)).toEqual(["needle_gauge"]);
	});

	test("names two labels that would become one fieldname, and refuses to save", async ({ page }) => {
		await openBuilder(page);

		await page.locator('[data-test="config-add-variable"]').click();
		await page
			.locator('[data-test="config-variable-row"]')
			.last()
			.locator('[data-test="config-variable-label"]')
			.fill("Product.");

		const collision = page.locator('[data-test="config-variable-collision"]');
		await expect(collision).toContainText("Product");
		await expect(collision).toContainText("product");
		await expect(page.locator('[data-test="config-save-variables"]')).toBeDisabled();
	});

	test("keeps a relabelled variable under the fieldname the chart already stores", async ({
		page,
		request,
	}) => {
		await openBuilder(page);

		const row = page.locator('[data-test="config-variable-row"][data-fieldname="plane"]');
		await row.locator('[data-test="config-variable-label"]').fill("Injection Plane");
		await expect(row.locator('[data-test="config-variable-fieldname"]')).toHaveText("plane");
		await Promise.all([
			page.waitForResponse("**/api/method/do_derma.api.save_derma_template_variables"),
			page.locator('[data-test="config-save-variables"]').click(),
		]);

		const template = await getDoc<{ custom_derma_variables_json: string }>(
			request,
			"Clinical Procedure Template",
			SEED.pointTemplate,
		);
		const stored = JSON.parse(template.custom_derma_variables_json);
		expect(stored[1]).toMatchObject({ fieldname: "plane", label: "Injection Plane" });
	});

	test("locks a variable a safety flag owns", async ({ page, request }) => {
		await updateDoc(request, "Clinical Procedure Template", SEED.pointTemplate, {
			custom_derma_product_tracking_required: 1,
		});

		await openBuilder(page);

		const locked = page.locator('[data-test="config-variable-row"][data-fieldname="lot_no"]');
		await expect(locked).toHaveAttribute("data-locked", "1");
		await expect(locked.locator('[data-test="config-variable-locked"]')).toContainText(
			"Product tracking",
		);
		await expect(locked.locator('[data-test="config-variable-required"]')).toBeDisabled();
		await expect(locked.locator('[data-test="config-remove-variable"]')).toHaveCount(0);
	});
});
