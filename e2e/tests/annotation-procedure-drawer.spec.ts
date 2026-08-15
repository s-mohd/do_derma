import { expect, Page, test } from "@playwright/test";
import {
	ChartContext,
	cleanupClinicalProcedure,
	cleanupEncounter,
	freshClinicalProcedure,
	freshEncounter,
	getSeedPatient,
	SEED,
} from "../helpers/derma";
import { ChartPage } from "../pages";

/**
 * The procedures drawer used to list every Clinical Procedure Template on the site with no
 * search and no filter, while the templates drawer beside it filtered by patient sex. It now
 * filters to the anchor procedure's own category and takes a search string; the header names
 * the patient once instead of repeating it through the Clinical Procedure's own name.
 */
test.describe("Annotation procedures drawer", () => {
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

	async function openDrawer(page: Page) {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("procedures");
		await chart.root.locator('[data-test="procedure-annotate"]').first().click();
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();

		const studio = page.locator(".derma-annotation-modal");
		await studio.getByRole("button", { name: "Procedures", exact: true }).click();
		await expect(studio.locator('[data-test="annotation-procedure-search"]')).toBeVisible();
		return studio;
	}

	test("keeps the anchor category's own templates and searches within them", async ({ page }) => {
		const studio = await openDrawer(page);
		const search = studio.locator('[data-test="annotation-procedure-search"]');
		const rows = studio.locator(".derma-treatment-list button");

		// All three seeded templates share the anchor's category, so the default filter keeps them.
		await expect(studio.getByRole("button", { name: SEED.pointTemplate })).toBeVisible();
		await expect(studio.getByRole("button", { name: SEED.areaTemplate })).toBeVisible();
		await expect(studio.getByRole("button", { name: SEED.freehandTemplate })).toBeVisible();
		const filteredCount = await rows.count();

		await search.fill("Area Peel");
		await expect(studio.getByRole("button", { name: SEED.areaTemplate })).toBeVisible();
		await expect(studio.getByRole("button", { name: SEED.pointTemplate })).toHaveCount(0);

		await search.fill("nothing matches this");
		await expect(rows).toHaveCount(0);
		await expect(studio.locator('[data-test="annotation-procedure-empty"]')).toContainText(
			"No procedure template matches",
		);

		await search.fill("");
		await expect(rows).toHaveCount(filteredCount);

		// The dev site is a production clone, so other categories may or may not exist. When the
		// escape hatch is offered, it has to widen the list rather than narrow it.
		const showAll = studio.locator('[data-test="annotation-show-all-procedures"] input');
		if (await showAll.count()) {
			await showAll.check();
			expect(await rows.count()).toBeGreaterThan(filteredCount);
		}
	});

	test("names the patient once in the header", async ({ page }) => {
		const studio = await openDrawer(page);
		const anchor = studio.locator('[data-test="annotation-anchor"]');

		await expect(anchor).toContainText(`Procedure: ${SEED.pointTemplate}`);
		const heading = (await anchor.textContent()) ?? "";
		expect(heading.split(SEED.patientFirstName).length - 1).toBe(1);
	});
});
