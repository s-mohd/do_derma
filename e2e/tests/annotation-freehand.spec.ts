import { expect, Page, test } from "@playwright/test";
import { ChartContext, cleanupEncounter, freshEncounter, getSeedPatient, listMarks, SEED } from "../helpers/derma";
import { callMethod } from "../helpers/frappe";
import { ChartPage } from "../pages";

/**
 * A procedure whose marker behaviour is `freehand` turns the pen its own colour, and the stroke
 * the practitioner draws becomes one Derma Chart Mark at its centroid.
 *
 * The mark is the point of it. Derma Chart Mark is the sole input to inventory readiness,
 * follow-up intelligence, create_procedure_from_mark and the Procedures-tab counts, so a stroke
 * that only carried its variables in the scene JSON would be clinically invisible.
 */
test.describe("Semantic freehand strokes", () => {
	let context: ChartContext;

	test.beforeEach(async ({ request }) => {
		const patient = await getSeedPatient(request);
		const encounter = await freshEncounter(request, patient);
		context = { patient, encounter: encounter.name };
	});

	test.afterEach(async ({ request }) => {
		if (context.encounter) await cleanupEncounter(request, context.encounter);
	});

	async function openStudioWithFreehand(page: Page): Promise<void> {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("assessment");
		await chart.root.locator('[data-test="annotate-consultation"]').click();
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();
		await page.waitForTimeout(6000);

		await page.getByRole("button", { name: "Procedures", exact: true }).click();
		await page.getByRole("button", { name: SEED.freehandTemplate }).click();
		await page.getByRole("button", { name: "Procedures", exact: true }).click();
		await page.waitForTimeout(500);
	}

	/**
	 * Straight and horizontal, returning a point known to be on it so a later click can select
	 * it. Excalidraw hit-tests a freedraw stroke within a few pixels of the line itself.
	 */
	async function drawStroke(page: Page): Promise<{ x: number; y: number }> {
		const canvas = page.locator(".derma-annotation-canvas canvas").first();
		const box = (await canvas.boundingBox())!;
		const y = box.y + box.height * 0.4;
		await page.mouse.move(box.x + box.width * 0.4, y);
		await page.mouse.down();
		for (const step of [0.45, 0.5, 0.55, 0.6]) {
			await page.mouse.move(box.x + box.width * step, y, { steps: 4 });
		}
		await page.mouse.up();
		await page.waitForTimeout(2500);
		return { x: box.x + box.width * 0.5, y };
	}

	test("announces that the procedure is drawn rather than clicked", async ({ page }) => {
		await openStudioWithFreehand(page);

		await expect(page.locator('[data-test="annotation-tagging-mode"]')).toContainText("draw over the affected skin");
	});

	test("turns one stroke into one Derma Chart Mark", async ({ page, request }) => {
		test.setTimeout(240000);
		await openStudioWithFreehand(page);

		await drawStroke(page);

		const marks = await listMarks(request, { encounter: context.encounter });
		expect(marks, "the stroke did not become a mark").toHaveLength(1);
		expect(marks[0].procedure_template).toBe(SEED.freehandTemplate);
		// The centroid must land on the template, not at a default.
		expect(Number(marks[0].x_percent)).toBeGreaterThan(0);
		expect(Number(marks[0].y_percent)).toBeGreaterThan(0);
		// The idempotency key the annotation fan-out matches elements to marks by.
		expect(JSON.parse(marks[0].annotation_json || "{}").shape).toBe("freehand");
	});

	test("keeps the stroke's own shape across a save and resume", async ({ page, request }) => {
		test.setTimeout(240000);
		await openStudioWithFreehand(page);
		await drawStroke(page);

		await page.getByRole("button", { name: "Save Annotation" }).click();
		await expect(page.locator(".derma-annotation-modal")).toHaveCount(0, { timeout: 60000 });
		await page.waitForTimeout(3000);

		const saved = await callMethod<{ encounter_annotations: Array<{ json: string }> }>(
			request,
			"do_derma.api.get_derma_annotations",
			{ encounter: context.encounter, patient: context.patient },
		);
		const elements = JSON.parse(saved.encounter_annotations[0].json).elements as Array<{
			type: string;
			points?: number[][];
			customData?: { kind?: string; shape?: string };
		}>;
		const stroke = elements.find((element) => element.type === "freedraw" && element.customData?.kind === "derma_mark");

		expect(stroke, "the tagged stroke is not in the saved scene").toBeTruthy();
		expect(stroke!.customData?.shape).toBe("freehand");
		// renderChartMarks must not have swapped it for a generated stamp.
		expect(stroke!.points!.length, "the stroke lost its geometry").toBeGreaterThan(2);
	});

	test("reopens a stroke's variables when it is clicked", async ({ page }) => {
		test.setTimeout(240000);
		await openStudioWithFreehand(page);
		await page.getByRole("textbox").first().fill("Graft A");
		await page.waitForTimeout(400);
		const onStroke = await drawStroke(page);

		// Leave tagging mode, then click the stroke to pick it back up.
		await page.getByRole("button", { name: "Stop Tagging" }).click();
		await page.waitForTimeout(500);

		await page.mouse.click(onStroke.x, onStroke.y);
		await page.waitForTimeout(1500);

		const editor = page.locator('[data-test="annotation-variable-editor"]');
		await expect(editor).toBeVisible();
		await expect(editor, "the editor is not bound to the clicked mark").not.toHaveAttribute("data-editing-mark", "");
		await expect(page.getByRole("textbox").first()).toHaveValue("Graft A");
	});
});
