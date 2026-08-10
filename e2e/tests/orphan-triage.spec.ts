import { expect, Page, test } from "@playwright/test";
import { getList } from "../helpers/frappe";
import {
	SEED,
	cleanupEncounter,
	freshEncounter,
	getSeedPatient,
	listMarks,
	saveMark,
} from "../helpers/derma";
import { ChartPage } from "../pages";

/**
 * Phase 4 of the revamp: two endpoints that had no caller at all get a real entry
 * point on the Procedures tab. Until this landed, drawing a mark was the only way
 * to create a Clinical Procedure and there was no way to reuse a previous visit's
 * marks from the chart.
 *
 * Both specs drive the frappe.ui.Dialog the button opens, because the dialog is
 * the part a refactor is most likely to break without breaking the endpoint.
 */

/** frappe.ui.Dialog renders into a Bootstrap modal appended to <body>, not into the chart root. */
function openDialog(page: Page) {
	return page.locator(".modal.show").last();
}

test.describe("Procedures tab entry points", () => {
	let patient: string;

	test.beforeAll(async ({ request }) => {
		patient = await getSeedPatient(request);
	});

	test("New Procedure creates a Clinical Procedure on this encounter", async ({ page, request }) => {
		const encounter = await freshEncounter(request, patient);
		const chart = new ChartPage(page);

		try {
			await chart.open({ patient, encounter: encounter.name });
			await chart.setSection("procedures");

			const button = chart.root.locator('[data-test="procedure-new"]');
			await expect(button).toHaveCount(1);
			await button.click();

			const dialog = openDialog(page);
			await expect(dialog).toBeVisible();
			await dialog.locator('select[data-fieldname="procedure_template"]').selectOption(SEED.pointTemplate);
			await dialog.getByRole("button", { name: "Create" }).click();
			await expect(dialog).toBeHidden();

			// The endpoint is the contract, not the toast: re-read it from the server.
			await expect
				.poll(async () => {
					const rows = await getList<{ name: string }>(request, "Clinical Procedure", {
						fields: ["name"],
						filters: { patient, custom_patient_encounter: encounter.name },
						limit: 5,
					});
					return rows.length;
				})
				.toBe(1);
		} finally {
			await cleanupEncounter(request, encounter.name);
		}
	});

	test("Copy marks from last visit copies the previous visit's marks onto this one", async ({
		page,
		request,
	}) => {
		const previous = await freshEncounter(request, patient);
		const current = await freshEncounter(request, patient);

		try {
			// The chart reads "last visit" as the most recently touched other encounter,
			// so this mark has to be planted before the chart is opened.
			await saveMark(request, { patient, encounter: previous.name, x_percent: 21, y_percent: 34 });

			const chart = new ChartPage(page);
			await chart.open({ patient, encounter: current.name });
			await chart.setSection("procedures");

			const button = chart.root.locator('[data-test="procedure-copy-marks"]');
			await expect(button).toBeEnabled();
			await button.click();

			const dialog = openDialog(page);
			await expect(dialog).toBeVisible();
			// Every mark is pre-checked, so Copy alone is enough.
			await dialog.getByRole("button", { name: "Copy" }).click();
			await expect(dialog).toBeHidden();

			await expect
				.poll(async () => (await listMarks(request, { encounter: current.name })).length)
				.toBe(1);

			const [copied] = await listMarks(request, { encounter: current.name });
			expect(copied.x_percent).toBe(21);
			expect(copied.y_percent).toBe(34);

			// The source visit keeps its own mark - this copies, it does not move.
			expect(await listMarks(request, { encounter: previous.name })).toHaveLength(1);
		} finally {
			await cleanupEncounter(request, current.name);
			await cleanupEncounter(request, previous.name);
		}
	});
});
