import { expect, Locator, Page, test } from "@playwright/test";
import { ChartContext, cleanupEncounter, freshEncounter, getSeedPatient } from "../helpers/derma";
import { ChartPage } from "../pages";

/**
 * Excalidraw's freehand tool drops a stroke that arrives in one jump, so the pointer has to be
 * moved in steps with the button held down.
 */
async function drawStroke(page: Page, canvas: Locator): Promise<void> {
	const box = (await canvas.boundingBox())!;
	const y = box.y + box.height * 0.72;
	// The studio arms the select tool on open. Excalidraw runs with handleKeyboardGlobally
	// false, so the "7" shortcut only lands once the canvas has focus - click the toolbar
	// instead, which needs neither focus nor an actionability check on the canvas.
	await page.locator('.derma-annotation-canvas .App-toolbar label[title^="Draw"]').click();
	await page.mouse.move(box.x + box.width * 0.3, y);
	await page.mouse.down();
	for (const ratio of [0.4, 0.5, 0.6, 0.7]) {
		// `steps` matters: freehand builds its path from the pointermove stream, and a single
		// jump per segment produces no stroke at all.
		await page.mouse.move(box.x + box.width * ratio, y + 12, { steps: 8 });
		await page.waitForTimeout(150);
	}
	await page.mouse.up();
	await page.waitForTimeout(700);
}

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

	test("closes without a prompt when nothing has been drawn", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("assessment");
		await chart.root.locator('[data-test="annotate-consultation"]').click();

		const modal = page.locator(".derma-annotation-modal");
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();
		await page.waitForTimeout(6000);

		await page.locator('[data-test="annotation-cancel"]').click();

		await expect(modal).toHaveCount(0);
		// Marks, badges and area outlines are re-derived on load; none of them is unsaved work.
		await expect(page.locator(".modal.show")).toHaveCount(0);
	});

	test("keeps the drawing when the backdrop is clicked, and confirms before discarding it", async ({
		page,
	}) => {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("assessment");
		await chart.root.locator('[data-test="annotate-consultation"]').click();

		const modal = page.locator(".derma-annotation-modal");
		const canvas = page.locator(".derma-annotation-canvas canvas").first();
		await expect(canvas).toBeVisible();
		await page.waitForTimeout(6000);

		await drawStroke(page, canvas);

		// The backdrop used to close the studio outright, discarding the drawing.
		await page.mouse.click(6, 6);
		await page.waitForTimeout(500);
		await expect(modal).toBeVisible();

		await page.locator('[data-test="annotation-cancel"]').click();
		const confirm = page.locator(".modal.show");
		await expect(confirm).toBeVisible();
		await expect(confirm).toContainText("Discard this drawing?");

		await confirm.getByRole("button", { name: "No" }).click();
		await expect(modal).toBeVisible();
	});

	test("renders the template's areas and lets them be hidden", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("assessment");
		await chart.root.locator('[data-test="annotate-consultation"]').click();

		const modal = page.locator(".derma-annotation-modal");
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();
		await page.waitForTimeout(6000);

		// Offered only when outlines are actually on the canvas, not merely configured.
		const areas = page.locator('[data-test="annotation-hide-areas"]');
		await expect(areas).toBeVisible();
		await expect(areas).toHaveText("Hide Areas");

		await areas.click();
		await expect(areas).toHaveText("Show Areas");
		await areas.click();
		await expect(areas).toHaveText("Hide Areas");

		await expect(modal).toBeVisible();
	});

	test("starts a new drawing rather than reopening the last one", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("assessment");

		await chart.root.locator('[data-test="annotate-consultation"]').click();
		const canvas = page.locator(".derma-annotation-canvas canvas").first();
		await expect(canvas).toBeVisible();
		await page.waitForTimeout(6000);
		await expect(page.locator('[data-test="annotation-anchor"] + span')).toContainText("New drawing");

		await drawStroke(page, canvas);
		await page.locator(".derma-annotation-modal").getByRole("button", { name: "Save Annotation" }).click();
		const review = page.locator(".modal.show");
		await expect(review).toBeVisible();
		await review.getByRole("button", { name: "Close" }).click();

		// A second click must not resume the drawing just saved.
		await chart.root.locator('[data-test="annotate-consultation"]').click();
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();
		await page.waitForTimeout(6000);
		await expect(page.locator('[data-test="annotation-anchor"] + span')).toContainText("New drawing");
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
