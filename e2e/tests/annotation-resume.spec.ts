import { APIRequestContext, expect, Page, test } from "@playwright/test";
import {
	ChartContext,
	cleanupClinicalProcedure,
	cleanupEncounter,
	freshClinicalProcedure,
	freshEncounter,
	getSeedPatient,
	SEED,
} from "../helpers/derma";
import { callMethod } from "../helpers/frappe";
import { ChartPage } from "../pages";

const ONE_PIXEL_PNG =
	"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

/**
 * A resumed procedure drawing used to open at 100% on an apparently blank canvas, with the areas
 * toggle offered over outlines nobody could see: fit and part geometry both ran against a template
 * element the scene had not measured yet. The canvas guard added earlier only covered the canvas.
 */
test.describe("Annotation resume", () => {
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

	async function openProcedureStudio(page: Page): Promise<void> {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("procedures");
		await chart.root.locator('[data-test="procedure-annotate"]').first().click();
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();
		await page.waitForTimeout(6000);
	}

	async function armPointProcedure(page: Page): Promise<void> {
		const studio = page.locator(".derma-annotation-modal");
		await studio.getByRole("button", { name: "Procedures", exact: true }).click();
		await studio.getByRole("button", { name: SEED.pointTemplate }).click();
		await studio.getByRole("button", { name: "Procedures", exact: true }).click();
		await page.waitForTimeout(500);
	}

	/** Excalidraw renders the current zoom as the reset-zoom button's label, e.g. "88%". */
	async function zoomLabel(page: Page): Promise<string> {
		return (await page.locator(".reset-zoom-button").first().textContent())?.trim() ?? "";
	}

	async function saveDrawing(page: Page): Promise<void> {
		await page.getByRole("button", { name: "Save Annotation" }).click();
		await expect(page.locator(".derma-annotation-modal")).toHaveCount(0, { timeout: 60000 });
		await page.waitForTimeout(3000);
		const review = page.locator('.modal.show [data-test="annotation-review"]');
		await review.waitFor({ state: "visible", timeout: 15000 }).catch(() => {});
		if (await review.isVisible()) {
			await page.locator(".modal.show").getByRole("button", { name: "Close", exact: true }).click();
			await expect(review).toBeHidden();
		}
	}

	async function reopenSavedDrawing(page: Page): Promise<void> {
		await page.locator('[data-test="procedure-annotate"]').first().click();
		await page.locator('.modal.show [data-test="annotation-picker-edit"]').first().click();
		await expect(page.locator(".derma-annotation-header span")).toContainText("Editing the saved drawing");
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();
		// Deliberately short: the drawing has to be fitted and its areas drawn on the frames after
		// the scene lands, not eventually, once a resize or a second render happens to repair it.
		await page.waitForTimeout(1500);
	}

	test("opens a saved drawing fitted to its template, with the areas drawn", async ({ page }) => {
		test.setTimeout(240000);
		await openProcedureStudio(page);
		await armPointProcedure(page);

		const canvas = page.locator(".derma-annotation-canvas canvas").first();
		const box = (await canvas.boundingBox())!;
		await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
		await page.waitForTimeout(2500);
		const fittedZoom = await zoomLabel(page);
		expect(fittedZoom, "the first open was not fitted either").not.toBe("100%");

		await saveDrawing(page);
		await reopenSavedDrawing(page);

		// Fit is measured against the template element, so the resumed view lands where the
		// first one did rather than at the untouched 100%.
		expect(await zoomLabel(page), "the resumed drawing opened unfitted").toBe(fittedZoom);

		// Offered only when outlines are on the canvas with real bounds - a 1px area is not drawn.
		const areas = page.locator('[data-test="annotation-hide-areas"]');
		await expect(areas, "the resumed drawing has no area outlines").toBeVisible();
		await expect(areas).toHaveText("Hide Areas");
	});

	/**
	 * A scene can carry a template element that cannot render: no fileId, and a `template` stub
	 * with no image URL - which is exactly what `demo_seed` writes and what any drawing saved
	 * before the image was stripped in place can hold. The picture is then rebuilt from the
	 * template row, and that rebuild used to replace the whole scene, taking the drawing with it.
	 */
	test("rebuilds a template that cannot render without losing the drawing", async ({ page, request }) => {
		test.setTimeout(240000);
		await seedPhantomTemplateDrawing(request, procedure, context.encounter!, context.patient!);

		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("procedures");
		await page.locator('[data-test="procedure-annotate"]').first().click();
		await page.locator('.modal.show [data-test="annotation-picker-edit"]').first().click();
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();
		// Long enough for the resize-driven template rebuild that used to wipe the scene.
		await page.waitForTimeout(8000);

		await expect(
			page.locator('[data-test="annotation-mark-count"]'),
			"rebuilding the template image threw the drawing away",
		).toHaveAttribute("data-mark-count", "1");

		const areas = page.locator('[data-test="annotation-hide-areas"]');
		await expect(areas, "the rebuilt template has no area outlines").toBeVisible();
	});
});

/** A drawing whose template image was never persisted, as `demo_seed._demo_scene` writes it. */
async function seedPhantomTemplateDrawing(
	request: APIRequestContext,
	procedure: string,
	encounter: string,
	patient: string,
): Promise<void> {
	const scene = {
		elements: [
			{
				id: "phantom-template-element",
				type: "image",
				x: 0,
				y: 0,
				width: 600,
				height: 800,
				customData: { kind: "derma_template", template: { name: SEED.bodyTemplate } },
			},
			{
				id: "phantom-mark-element",
				type: "rectangle",
				x: 260,
				y: 320,
				width: 24,
				height: 24,
				customData: {
					kind: "derma_mark",
					shape: "area",
					procedure_template: SEED.pointTemplate,
					procedure_variables: {},
				},
			},
		],
		derma_template: { name: SEED.bodyTemplate },
	};

	await callMethod(request, "do_derma.api.save_derma_annotation", {
		payload: {
			patient,
			encounter,
			clinical_procedure: procedure,
			file_data: ONE_PIXEL_PNG,
			json_text: JSON.stringify(scene),
		},
	});
}
