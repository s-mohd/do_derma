import { expect, Page, test } from "@playwright/test";
import { APIRequestContext } from "@playwright/test";
import { ChartContext, getSeedClinicalProcedure, getSeedPatient, SEED } from "../helpers/derma";
import { callMethod } from "../helpers/frappe";
import { ChartPage } from "../pages";

/** do_derma.api.get_derma_annotations, narrowed to what this spec reads. */
interface AnnotationContext {
	procedure_annotations: Record<string, Array<{ name: string; json: string }>>;
}

async function procedureAnnotations(
	request: APIRequestContext,
	context: ChartContext,
	procedure: string,
): Promise<Array<{ name: string; json: string }>> {
	const result = await callMethod<AnnotationContext>(request, "do_derma.api.get_derma_annotations", {
		encounter: context.encounter,
		patient: context.patient,
		clinical_procedure: procedure,
	});
	return result.procedure_annotations?.[procedure] ?? [];
}

function shapeCount(json: string): number {
	const elements = JSON.parse(json || "{}").elements ?? [];
	return elements.filter((element: { type: string; isDeleted?: boolean }) => element.type === "rectangle" && !element.isDeleted).length;
}

interface MarkElement {
	width: number;
	height: number;
	customData?: { mark_name?: string; generated_by?: string };
}

/**
 * Scene elements linked to a Derma Chart Mark, keyed by mark. Keyed rather than counted
 * because the seeded anchor is shared and its scene accumulates across runs.
 */
function markElementsByName(json: string): Map<string, MarkElement> {
	const elements = (JSON.parse(json || "{}").elements ?? []) as MarkElement[];
	const byName = new Map<string, MarkElement>();
	for (const element of elements) {
		const name = element.customData?.mark_name;
		if (name) byName.set(name, element);
	}
	return byName;
}

/** Excalidraw is loaded dynamically after the overlay mounts, so wait on its canvas. */
async function drawRectangle(page: Page): Promise<void> {
	const canvas = page.locator(".derma-annotation-canvas canvas").first();
	await expect(canvas).toBeVisible();
	await page.waitForTimeout(6000);

	// The icon inside the tool button swallows the click, hence force.
	await page.locator('[data-testid="toolbar-rectangle"]').click({ force: true });
	const box = (await canvas.boundingBox())!;
	await page.mouse.move(box.x + box.width * 0.35, box.y + box.height * 0.35);
	await page.mouse.down();
	await page.mouse.move(box.x + box.width * 0.65, box.y + box.height * 0.65, { steps: 12 });
	await page.mouse.up();
	await page.waitForTimeout(1000);
}

/**
 * Arm the seeded drag-to-size procedure and drag a treatment area. This is the path that
 * tags the element `kind: "derma_mark"` and stamps a `mark_name` onto it.
 */
async function drawAreaMark(page: Page): Promise<void> {
	const canvas = page.locator(".derma-annotation-canvas canvas").first();
	await expect(canvas).toBeVisible();
	await page.waitForTimeout(6000);

	await page.getByRole("button", { name: "Procedures", exact: true }).click();
	await page.getByRole("button", { name: SEED.areaTemplate }).click();
	await page.getByRole("button", { name: "Procedures", exact: true }).click();

	const box = (await canvas.boundingBox())!;
	await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.3);
	await page.mouse.down();
	await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.6, { steps: 12 });
	await page.mouse.up();
	await page.waitForTimeout(2000);
}

/**
 * Annotate opens the studio directly while the procedure has no drawings; once
 * it has any, a picker dialog offers each drawing plus "New Annotation". The
 * seeded procedure is shared and accumulates across runs, so both paths are
 * tolerated. `fresh` starts a new drawing; the default resumes the newest.
 */
async function openProcedureStudio(
	page: Page,
	chart: ChartPage,
	opts: { fresh?: boolean } = {},
): Promise<void> {
	await chart.root.locator('[data-test="procedure-annotate"]').first().click();
	const picker = page.locator('.modal.show [data-test="annotation-picker"]');
	try {
		await picker.waitFor({ state: "visible", timeout: 4000 });
	} catch {
		// No picker: the studio opened directly on a fresh drawing.
	}
	if (await picker.isVisible()) {
		if (opts.fresh) {
			await page.getByRole("button", { name: "New Annotation" }).click();
		} else {
			await picker.locator('[data-test="annotation-picker-edit"]').first().click();
		}
	}
	await expect(page.locator(".derma-annotation-modal")).toBeVisible();
}

async function saveAndClose(page: Page): Promise<void> {
	await page.getByRole("button", { name: "Save Annotation" }).click();
	await expect(page.locator(".derma-annotation-modal")).toHaveCount(0, { timeout: 60000 });
	await page.waitForTimeout(3000);
}

/**
 * Two annotation anchors, each with its own entry point. The backend has always
 * branched on the anchor (api.py save_derma_annotation), but until Phase 3 the
 * studio hardcoded "Patient Encounter", so a procedure-anchored drawing could not
 * be made from the chart at all and every save created a fresh record.
 *
 * The studio header states the anchor in words, and that is what the first two
 * specs read: the anchor is otherwise invisible at save time, and a mis-anchored
 * annotation is not something a practitioner can see or undo.
 */
test.describe("Annotation anchoring", () => {
	let context: ChartContext;
	let procedure: string;

	test.beforeAll(async ({ request }) => {
		const patient = await getSeedPatient(request);
		const seeded = await getSeedClinicalProcedure(request, patient);
		procedure = seeded.name;
		context = { patient, encounter: seeded.encounter ?? undefined };
	});

	test("anchors the Assessment entry point to the consultation", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("assessment");

		await chart.root.locator('[data-test="annotate-consultation"]').click();

		const anchor = page.locator('[data-test="annotation-anchor"]');
		await expect(anchor).toBeVisible();
		await expect(anchor).toContainText("Consultation");
	});

	test("anchors a procedure row's own entry point to that procedure", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("procedures");

		await expect(
			chart.root.locator('[data-test="procedure-annotate"]').first(),
			`no Annotate button on the seeded procedure ${procedure}`,
		).toBeVisible();
		await openProcedureStudio(page, chart);

		const anchor = page.locator('[data-test="annotation-anchor"]');
		await expect(anchor).toBeVisible();
		await expect(anchor).toContainText("Procedure");
	});

	/**
	 * The Phase 3 exit criterion, end to end: a drawing made on a procedure row
	 * lands on that Clinical Procedure, and reopening resumes it rather than
	 * handing back a blank canvas. The re-save is what proves the resume - if the
	 * template loader had wiped the imported scene, the second save would write
	 * back a scene with no shapes.
	 */
	test("saves onto the procedure and resumes it in place", async ({ page, request }) => {
		test.setTimeout(240000);
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("procedures");

		await openProcedureStudio(page, chart);
		await drawRectangle(page);
		await saveAndClose(page);

		const first = await procedureAnnotations(request, context, procedure);
		expect(first, "the drawing did not land on the Clinical Procedure").toHaveLength(1);
		expect(shapeCount(first[0].json)).toBeGreaterThan(0);

		// _get_annotation_counts_for_procedures only counts rows whose parenttype is
		// Clinical Procedure, so this badge read 0 for every procedure before Phase 3.
		await chart.setSection("procedures");
		const annotate = chart.root.locator('[data-test="procedure-annotate"]').first();
		await expect(annotate.locator(".icon-badge")).toHaveText("1");

		await openProcedureStudio(page, chart);
		await expect(page.locator(".derma-annotation-header span")).toContainText("Editing the saved drawing");
		await page.waitForTimeout(8000);
		await saveAndClose(page);

		const second = await procedureAnnotations(request, context, procedure);
		expect(second, "resuming created a second Health Annotation").toHaveLength(1);
		expect(second[0].name).toBe(first[0].name);
		expect(shapeCount(second[0].json), "the resumed drawing was lost").toBe(shapeCount(first[0].json));
	});

	/**
	 * renderChartMarks rebuilds a mark's on-canvas shape from its stored centroid, and
	 * createAreaMark emits a fixed 80x56 box. When it claimed ownership of anything merely
	 * tagged as a mark, resuming replaced the practitioner's own dragged treatment area with
	 * that generic box. It must now own only the stamps it generated itself.
	 */
	test("keeps a dragged treatment area at its drawn size across resume", async ({ page, request }) => {
		test.setTimeout(240000);
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("procedures");

		await openProcedureStudio(page, chart);
		await drawAreaMark(page);
		await saveAndClose(page);

		const [saved] = await procedureAnnotations(request, context, procedure);
		const drawn = markElementsByName(saved.json);
		expect(drawn.size, "the dragged area was never linked to a mark").toBeGreaterThan(0);

		await chart.setSection("procedures");
		await openProcedureStudio(page, chart);
		await expect(page.locator(".derma-annotation-header span")).toContainText("Editing the saved drawing");
		await page.waitForTimeout(8000);
		await saveAndClose(page);

		const [resumed] = await procedureAnnotations(request, context, procedure);
		const after = markElementsByName(resumed.json);

		for (const [markName, before] of drawn) {
			const element = after.get(markName);
			expect(element, `mark ${markName} vanished from the resumed scene`).toBeDefined();
			expect(Math.round(element!.width), `mark ${markName} was replaced by a generated stamp`).toBe(Math.round(before.width));
			expect(Math.round(element!.height)).toBe(Math.round(before.height));
			expect(element!.customData?.generated_by).toBeUndefined();
		}
	});
});
