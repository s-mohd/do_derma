import { expect, test } from "@playwright/test";
import { ChartContext, cleanupEncounter, freshEncounter, getSeedPatient } from "../helpers/derma";
import { ChartPage } from "../pages";

/**
 * The consultation popup is a plain sketchpad: templates, freehand drawing, Fit,
 * Save. Procedure tagging - the drawer, the variables sidebar, the badges
 * control - lives exclusively in the procedure popup, so none of those
 * affordances may appear here.
 */
test.describe("Consultation sketchpad", () => {
	let context: ChartContext;

	test.beforeEach(async ({ request }) => {
		const patient = await getSeedPatient(request);
		const encounter = await freshEncounter(request, patient);
		context = { patient, encounter: encounter.name };
	});

	test.afterEach(async ({ request }) => {
		if (context.encounter) await cleanupEncounter(request, context.encounter);
	});

	test("offers drawing tools but no tagging affordances", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("assessment");
		await chart.root.locator('[data-test="annotate-consultation"]').click();

		const modal = page.locator(".derma-annotation-modal");
		await expect(modal).toBeVisible();
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();

		await expect(modal.getByRole("button", { name: "Templates" })).toBeVisible();
		await expect(page.locator('[data-test="annotation-fit-template"]')).toBeVisible();
		await expect(modal.getByRole("button", { name: "Save Annotation" })).toBeVisible();

		await expect(modal.getByRole("button", { name: "Procedures", exact: true })).toHaveCount(0);
		await expect(page.locator('[data-test="annotation-badges-toggle"]')).toHaveCount(0);
		await expect(page.locator(".derma-annotation-right")).toHaveCount(0);
	});

	test("keeps the templates drawer open across canvas clicks", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("assessment");
		await chart.root.locator('[data-test="annotate-consultation"]').click();
		const canvas = page.locator(".derma-annotation-canvas canvas").first();
		await expect(canvas).toBeVisible();
		await page.waitForTimeout(6000);

		const modal = page.locator(".derma-annotation-modal");
		await modal.getByRole("button", { name: "Templates" }).click();
		await expect(page.locator(".derma-annotation-left")).toBeVisible();

		// The scrim used to swallow this click and close the drawer.
		const box = (await canvas.boundingBox())!;
		await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
		await page.waitForTimeout(500);

		await expect(page.locator(".derma-annotation-left")).toBeVisible();
	});
});
