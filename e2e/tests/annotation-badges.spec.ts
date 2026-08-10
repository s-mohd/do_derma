import { expect, Page, test } from "@playwright/test";
import { ChartContext, cleanupEncounter, freshEncounter, getSeedPatient } from "../helpers/derma";
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
 */
test.describe("Annotation badges", () => {
	let context: ChartContext;

	test.beforeEach(async ({ request }) => {
		const patient = await getSeedPatient(request);
		const encounter = await freshEncounter(request, patient);
		context = { patient, encounter: encounter.name };
	});

	test.afterEach(async ({ request }) => {
		if (context.encounter) await cleanupEncounter(request, context.encounter);
	});

	async function openStudioWithProcedure(page: Page): Promise<void> {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("assessment");
		await chart.root.locator('[data-test="annotate-consultation"]').click();
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();
		await page.waitForTimeout(6000);

		await page.getByRole("button", { name: "Procedures", exact: true }).click();
		await page.getByRole("button", { name: "E2E Filler" }).click();
		await page.getByRole("button", { name: "Procedures", exact: true }).click();
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

	test("keeps badges out of the saved scene", async ({ page, request }) => {
		test.setTimeout(240000);
		await openStudioWithProcedure(page);
		await setProductVariable(page, "Restylane");
		await placeStamp(page, 0.5, 0.4);
		await page.waitForTimeout(1000);
		expect(await badgeCount(page)).toBe("1");

		await page.getByRole("button", { name: "Save Annotation" }).click();
		await expect(page.locator(".derma-annotation-modal")).toHaveCount(0, { timeout: 60000 });
		await page.waitForTimeout(3000);

		const saved = await callMethod<{ encounter_annotations: Array<{ json: string; annotation_data?: string }> }>(
			request,
			"do_derma.api.get_derma_annotations",
			{ encounter: context.encounter, patient: context.patient },
		);
		const scene = saved.encounter_annotations[0];
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
