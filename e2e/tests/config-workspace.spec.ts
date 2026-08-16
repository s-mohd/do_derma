import { APIRequestContext, expect, test } from "@playwright/test";
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

		for (const tool of ["procedure-templates", "categories", "readiness"]) {
			await page.locator(`[data-test="config-rail-item-${tool}"]`).click();
			await expect(page.locator('[data-test="config-placeholder"]')).toBeVisible();
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
