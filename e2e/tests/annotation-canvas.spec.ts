import { expect, Page, test } from "@playwright/test";
import { APIRequestContext } from "@playwright/test";
import { ChartContext, cleanupEncounter, freshEncounter, getSeedPatient, listMarks } from "../helpers/derma";
import { ChartPage } from "../pages";

/**
 * The canvas is stock Excalidraw again. It used to be caged from two directions at once:
 * `enforceLockedViewport` snapped scroll and zoom back on every drift, capture-phase listeners
 * swallowed the wheel, right-click and the +/-/0/space/arrow keys, and a 28-selector CSS block
 * hid every zoom button along with the hand tool and the whole library.
 *
 * None of it was load-bearing: mark geometry is scene-space throughout (getTemplateBounds reads
 * the template element's own x/y/width/height), so zoom and pan cannot move a stored percentage.
 * The last test here is what proves that claim rather than asserting it.
 */
test.describe("Annotation canvas", () => {
	let context: ChartContext;

	// A pristine draft encounter per test, not the shared seeded one. These specs click bare
	// canvas, and any drawing already there turns the click into a mark *selection* instead
	// (EmbeddedExcalidraw onPointerDown returns early on a hit element).
	test.beforeEach(async ({ request }) => {
		const patient = await getSeedPatient(request);
		const encounter = await freshEncounter(request, patient);
		context = { patient, encounter: encounter.name };
	});

	test.afterEach(async ({ request }) => {
		if (context.encounter) await cleanupEncounter(request, context.encounter);
	});

	async function openStudio(page: Page): Promise<Page> {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("assessment");
		await chart.root.locator('[data-test="annotate-consultation"]').click();
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();
		await page.waitForTimeout(6000);
		return page;
	}

	/** Excalidraw renders the current zoom as the reset-zoom button's label, e.g. "88%". */
	async function zoomLabel(page: Page): Promise<string> {
		return (await page.locator(".reset-zoom-button").first().textContent())?.trim() ?? "";
	}

	test("restores the zoom controls, hand tool, image tool and library", async ({ page }) => {
		await openStudio(page);

		await expect(page.locator('[data-testid="toolbar-hand"]')).toBeVisible();
		await expect(page.locator('[data-testid="toolbar-image"]')).toBeVisible();
		await expect(page.locator('[data-testid="toolbar-lock"]')).toBeVisible();
		await expect(page.locator(".zoom-in-button")).toBeVisible();
		await expect(page.locator(".zoom-out-button")).toBeVisible();
		// The library trigger is a <label>-based sidebar trigger, not a button.
		await expect(page.locator(".sidebar-trigger").filter({ hasText: "Library" })).toBeVisible();
	});

	test("lets the practitioner zoom and stays zoomed", async ({ page }) => {
		await openStudio(page);
		const before = await zoomLabel(page);

		const canvas = page.locator(".derma-annotation-canvas canvas").first();
		const box = (await canvas.boundingBox())!;
		await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
		await page.keyboard.down("Control");
		await page.mouse.wheel(0, -400);
		await page.keyboard.up("Control");

		// The old build snapped this straight back within ~80ms.
		await page.waitForTimeout(1500);
		expect(await zoomLabel(page), "zoom was reverted by a viewport lock").not.toBe(before);
	});

	test("Fit returns the template to view after panning away", async ({ page }) => {
		await openStudio(page);

		const canvas = page.locator(".derma-annotation-canvas canvas").first();
		const box = (await canvas.boundingBox())!;
		await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
		await page.keyboard.down("Control");
		await page.mouse.wheel(0, -500);
		await page.keyboard.up("Control");
		await page.waitForTimeout(1000);
		const zoomed = await zoomLabel(page);

		await page.locator('[data-test="annotation-fit-template"]').click();
		await page.waitForTimeout(1000);

		expect(await zoomLabel(page)).not.toBe(zoomed);
	});

	/**
	 * The claim that unlocking the viewport is safe, tested rather than asserted. Fit centres the
	 * body template in the canvas, so a stamp dropped on the canvas centre lands on the template
	 * centre. Zooming in on that same point must not change the answer: percentages come from
	 * scene coordinates (getTemplateBounds), not from screen space. Each case gets a pristine
	 * canvas because the first stamp would otherwise absorb the second click.
	 */
	for (const zoomedIn of [false, true]) {
		test(`maps a centre click to the template centre ${zoomedIn ? "while zoomed in" : "at fit"}`, async ({ page, request }) => {
			test.setTimeout(240000);
			await openStudio(page);
			await armPointProcedure(page);

			const canvas = page.locator(".derma-annotation-canvas canvas").first();
			const box = (await canvas.boundingBox())!;
			const centre = { x: box.x + box.width / 2, y: box.y + box.height / 2 };

			await page.locator('[data-test="annotation-fit-template"]').click();
			await page.waitForTimeout(1000);

			if (zoomedIn) {
				await page.mouse.move(centre.x, centre.y);
				await page.keyboard.down("Control");
				await page.mouse.wheel(0, -300);
				await page.keyboard.up("Control");
				await page.waitForTimeout(1200);
			}

			const reading = await placeStampAndRead(page, request, context, centre);

			expect(reading.x_percent, "x_percent is not on the template centre").toBeGreaterThan(40);
			expect(reading.x_percent, "x_percent is not on the template centre").toBeLessThan(60);
			expect(reading.y_percent, "y_percent is not on the template centre").toBeGreaterThan(40);
			expect(reading.y_percent, "y_percent is not on the template centre").toBeLessThan(60);
		});
	}

	/**
	 * The resume path must not reach across visits. `encounter_annotations` falls back to the
	 * patient's earlier encounters when this one has none, and treating that as "this anchor's
	 * drawing" would make the first save of a new visit overwrite the previous visit's.
	 */
	test("opens a new visit as a new drawing even when the patient has earlier ones", async ({ page }) => {
		await openStudio(page);

		await expect(page.locator(".derma-annotation-header span")).toContainText("New drawing");
	});
});

async function armPointProcedure(page: Page): Promise<void> {
	await page.getByRole("button", { name: "Procedures", exact: true }).click();
	await page.getByRole("button", { name: "E2E Filler" }).click();
	await page.getByRole("button", { name: "Procedures", exact: true }).click();
	await page.waitForTimeout(500);
}

async function placeStampAndRead(
	page: Page,
	request: APIRequestContext,
	context: ChartContext,
	target: { x: number; y: number },
): Promise<{ x_percent: number; y_percent: number }> {
	const before = await listMarks(request, { encounter: context.encounter });
	await page.mouse.click(target.x, target.y);
	await page.waitForTimeout(2500);

	const after = await listMarks(request, { encounter: context.encounter });
	const placed = after.filter((mark) => !before.some((existing) => existing.name === mark.name));
	expect(placed, "clicking the canvas placed no mark").toHaveLength(1);
	return { x_percent: Number(placed[0].x_percent), y_percent: Number(placed[0].y_percent) };
}
