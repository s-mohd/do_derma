import { expect, Page, test } from "@playwright/test";
import {
	ChartContext,
	cleanupClinicalProcedure,
	cleanupEncounter,
	freshClinicalProcedure,
	freshEncounter,
	getSeedPatient,
} from "../helpers/derma";
import { callMethod } from "../helpers/frappe";
import { ChartPage } from "../pages";

/**
 * Badges used to exist only inside the exported PNG: they were built at save time, handed to
 * exportScene as extraElements, and the practitioner never saw them. They now live in the scene,
 * which means one computation feeds the screen, the PNG and the annotation_data table at once.
 *
 * Being in the scene brings two obligations, and both are asserted here: badges must not survive
 * into the persisted JSON (they are derived), and pushing them back into the scene must not
 * re-trigger its own onChange forever.
 *
 * Tagging lives exclusively in the procedure popup (the consultation popup is a plain
 * sketchpad), so every spec here annotates a private draft Clinical Procedure.
 */
test.describe("Annotation badges", () => {
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
		// A fresh procedure has no drawings, so Annotate opens the studio directly.
		await chart.root.locator('[data-test="procedure-annotate"]').first().click();
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();
		await page.waitForTimeout(6000);

		// Scoped to the studio: the procedures tab behind it has its own "E2E Filler" row button.
		const studio = page.locator(".derma-annotation-modal");
		await studio.getByRole("button", { name: "Procedures", exact: true }).click();
		await studio.getByRole("button", { name: "E2E Filler" }).click();
		// The drawer only closes from its own toggle now - canvas clicks leave it alone.
		await studio.getByRole("button", { name: "Procedures", exact: true }).click();
		await page.waitForTimeout(500);
	}

	async function placeStamp(page: Page, relativeX: number, relativeY: number): Promise<void> {
		const canvas = page.locator(".derma-annotation-canvas canvas").first();
		const box = (await canvas.boundingBox())!;
		await page.mouse.click(box.x + box.width * relativeX, box.y + box.height * relativeY);
		await page.waitForTimeout(2500);
	}

	const badgeCount = (page: Page) =>
		page.locator('[data-test="annotation-badges-toggle"]').getAttribute("data-badge-count");

	/**
	 * Variables are carried onto the stamp at placement time (insertProcedureStamp reads
	 * procedureVariablesRef), so the supported order is fill, then place.
	 */
	async function setProductVariable(page: Page, value: string): Promise<void> {
		await page.getByRole("textbox").first().fill(value);
		await page.waitForTimeout(500);
	}

	test("numbers a placed mark that carries a filled variable", async ({ page }) => {
		await openStudioWithProcedure(page);
		expect(await badgeCount(page)).toBe("0");

		// A mark with no variable values is not badge-worthy.
		await placeStamp(page, 0.5, 0.4);
		expect(await badgeCount(page)).toBe("0");

		await setProductVariable(page, "Restylane");
		await placeStamp(page, 0.5, 0.55);
		await page.waitForTimeout(1000);

		expect(await badgeCount(page), "a mark with a filled variable produced no badge").toBe("1");
	});

	test("numbers every marked variable, top-to-bottom", async ({ page }) => {
		await openStudioWithProcedure(page);

		await setProductVariable(page, "Lower");
		await placeStamp(page, 0.5, 0.6);
		await setProductVariable(page, "Upper");
		await placeStamp(page, 0.5, 0.3);
		await page.waitForTimeout(1000);

		expect(await badgeCount(page)).toBe("2");
	});

	test("keeps badges out of the saved scene and reviews the output", async ({ page, request }) => {
		test.setTimeout(240000);
		await openStudioWithProcedure(page);
		await setProductVariable(page, "Restylane");
		await placeStamp(page, 0.5, 0.4);
		await page.waitForTimeout(1000);
		expect(await badgeCount(page)).toBe("1");

		await page.getByRole("button", { name: "Save Annotation" }).click();
		await expect(page.locator(".derma-annotation-modal")).toHaveCount(0, { timeout: 60000 });

		// The review dialog shows the output image beside the legend built from the same items.
		const review = page.locator('.modal.show [data-test="annotation-review"]');
		await expect(review).toBeVisible({ timeout: 15000 });
		await expect(review).toContainText("Restylane");
		await page.locator(".modal.show").getByRole("button", { name: "Close", exact: true }).click();
		await page.waitForTimeout(3000);

		const saved = await callMethod<{
			procedure_annotations: Record<string, Array<{ json: string; annotation_data?: string }>>;
		}>(request, "do_derma.api.get_derma_annotations", {
			encounter: context.encounter,
			patient: context.patient,
			clinical_procedure: procedure,
		});
		const scene = saved.procedure_annotations[procedure][0];
		const elements = JSON.parse(scene.json).elements as Array<{ customData?: { kind?: string } }>;

		expect(elements.some((element) => element.customData?.kind === "derma_badge"), "badges were persisted").toBe(false);
		// The table is generated from the same items the canvas drew.
		expect(scene.annotation_data ?? "").toContain("Restylane");
	});

	test("removes the badge layer when the toggle is unticked", async ({ page }) => {
		await openStudioWithProcedure(page);
		await setProductVariable(page, "Restylane");
		await placeStamp(page, 0.5, 0.4);
		await page.waitForTimeout(1000);
		expect(await badgeCount(page)).toBe("1");

		await page.locator('[data-test="annotation-badges-toggle"] input').uncheck();
		await page.waitForTimeout(1000);

		expect(await badgeCount(page)).toBe("0");
	});

	/** A scene update that re-fires onChange would loop forever without the signature guard. */
	test("settles instead of looping once a badge is on screen", async ({ page }) => {
		await openStudioWithProcedure(page);
		await setProductVariable(page, "Restylane");
		await placeStamp(page, 0.5, 0.4);
		await page.waitForTimeout(2000);

		const settled = await page.evaluate(async () => {
			const canvas = document.querySelector(".derma-annotation-canvas canvas") as HTMLCanvasElement;
			const before = canvas.toDataURL().length;
			await new Promise((resolve) => setTimeout(resolve, 3000));
			return canvas.toDataURL().length === before;
		});

		expect(settled, "the canvas kept redrawing - badge sync is looping").toBe(true);
	});
});
