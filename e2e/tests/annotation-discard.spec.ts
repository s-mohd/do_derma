import { expect, Page, test } from "@playwright/test";
import {
	ChartContext,
	cleanupClinicalProcedure,
	cleanupEncounter,
	freshClinicalProcedure,
	freshEncounter,
	getSeedPatient,
	listMarks,
	saveMark,
	SEED,
} from "../helpers/derma";
import { ChartPage } from "../pages";

/**
 * Marks reach the server the instant they are drawn (onMarkPlaced -> save_chart_mark), long
 * before Save Annotation. Discarding used to drop the drawing and keep those marks, so the
 * chart carried a record the practitioner believed they had thrown away.
 */
test.describe("Annotation discard", () => {
	let context: ChartContext;
	let procedure: string;

	test.beforeEach(async ({ request }) => {
		const patient = await getSeedPatient(request);
		const encounter = await freshEncounter(request, patient);
		context = { patient, encounter: encounter.name };
		procedure = (await freshClinicalProcedure(request, patient, encounter.name)).name;
	});

	test.afterEach(async ({ request }) => {
		if (context.encounter) await cleanupEncounter(request, context.encounter);
		if (procedure) await cleanupClinicalProcedure(request, procedure);
	});

	async function openStudioWithProcedure(page: Page): Promise<void> {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("procedures");
		await chart.root.locator('[data-test="procedure-annotate"]').first().click();
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();
		await page.waitForTimeout(6000);

		const studio = page.locator(".derma-annotation-modal");
		await studio.getByRole("button", { name: "Procedures", exact: true }).click();
		await studio.getByRole("button", { name: SEED.pointTemplate }).click();
		await studio.getByRole("button", { name: "Procedures", exact: true }).click();
		await page.waitForTimeout(500);
	}

	async function placeStamp(page: Page, relativeX: number, relativeY: number): Promise<void> {
		const canvas = page.locator(".derma-annotation-canvas canvas").first();
		const box = (await canvas.boundingBox())!;
		await page.mouse.click(box.x + box.width * relativeX, box.y + box.height * relativeY);
		await page.waitForTimeout(2500);
	}

	test("removes the marks it placed when the drawing is discarded", async ({ page, request }) => {
		await openStudioWithProcedure(page);
		await placeStamp(page, 0.5, 0.4);
		await placeStamp(page, 0.5, 0.55);

		// Real-time saving is deliberate: the fan-out re-links these rows rather than recreating them.
		expect(await listMarks(request, { clinical_procedure: procedure })).toHaveLength(2);

		await page.locator('[data-test="annotation-cancel"]').click();
		const confirm = page.locator(".modal.show");
		await expect(confirm).toBeVisible();
		// The dialog has to name what it is about to throw away.
		await expect(confirm).toContainText("2 mark(s)");

		await confirm.getByRole("button", { name: "Yes" }).click();
		await expect(page.locator(".derma-annotation-modal")).toHaveCount(0, { timeout: 30000 });
		await page.waitForTimeout(3000);

		expect(
			await listMarks(request, { clinical_procedure: procedure }),
			"discarding the drawing left its marks on the chart",
		).toHaveLength(0);
	});

	test("keeps the marks it did not place", async ({ page, request }) => {
		const planted = await saveMark(request, {
			patient: context.patient!,
			encounter: context.encounter,
			clinical_procedure: procedure,
			procedure_template: SEED.pointTemplate,
		});

		await openStudioWithProcedure(page);
		await placeStamp(page, 0.5, 0.4);

		await page.locator('[data-test="annotation-cancel"]').click();
		const confirm = page.locator(".modal.show");
		await expect(confirm).toBeVisible();
		await expect(confirm).toContainText("1 mark(s)");
		await confirm.getByRole("button", { name: "Yes" }).click();
		await expect(page.locator(".derma-annotation-modal")).toHaveCount(0, { timeout: 30000 });
		await page.waitForTimeout(3000);

		const remaining = await listMarks(request, { clinical_procedure: procedure });
		expect(remaining.map((mark) => mark.name)).toEqual([planted.name]);
	});

	/** Nothing placed and nothing drawn is still an unguarded close. */
	test("closes without a prompt when no mark was placed", async ({ page }) => {
		await openStudioWithProcedure(page);

		await page.locator('[data-test="annotation-cancel"]').click();

		await expect(page.locator(".derma-annotation-modal")).toHaveCount(0);
		await expect(page.locator(".modal.show")).toHaveCount(0);
	});
});
