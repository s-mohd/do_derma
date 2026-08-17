import { expect, test } from "@playwright/test";
import { getDoc } from "../helpers/frappe";
import {
	cleanupEncounter,
	freshEncounter,
	getSeedPatient,
	saveMark,
	setBlockerEnforcement,
} from "../helpers/derma";
import { ChartPage } from "../pages";

/**
 * Readiness has one owner and it is the server. The Review tab renders what
 * `get_patient_derma_chart` computed, and Complete Session asks the clinician
 * about the blockers the server reported rather than deciding for itself.
 *
 * A `Worse` mark is the cheapest blocker there is: the follow-up engine raises a
 * blocking status item for it with no template configuration at all.
 *
 * The server's own refusal is covered by `TestCompleteDermaSessionBlockers`; what these
 * specs prove is that the chart renders that decision and asks before it overrides it.
 * Both mutate the site-wide `Derma Settings` singleton, which is safe only because
 * `playwright.config.ts` runs one worker with `fullyParallel: false`.
 */
test.describe("Session readiness", () => {
	let patient: string;

	test.beforeAll(async ({ request }) => {
		patient = await getSeedPatient(request);
	});

	test.afterAll(async ({ request }) => {
		await setBlockerEnforcement(request, "Warn");
	});

	test("the Review tab lists the server's blockers and the mode it will apply", async ({
		page,
		request,
	}) => {
		await setBlockerEnforcement(request, "Warn");
		const encounter = await freshEncounter(request, patient);

		try {
			await saveMark(request, { patient, encounter: encounter.name, status: "Worse" });

			const chart = new ChartPage(page);
			await chart.open({ patient, encounter: encounter.name });
			await chart.setSection("review");

			const readiness = chart.root.locator('[data-test="review-readiness"]');
			await expect(readiness).toBeVisible();
			await expect(readiness.locator('[data-test="review-readiness-mode"]')).toHaveAttribute(
				"data-mode",
				"Warn",
			);
			// One mark, one blocker: the list is the server's, not a truncation of it.
			await expect(readiness.locator('[data-test="review-readiness-blockers"] li')).toHaveCount(1);
			await expect(
				readiness.locator('[data-test="review-readiness-blockers"] li[data-source="followup"]'),
			).toHaveCount(1);
		} finally {
			await cleanupEncounter(request, encounter.name);
		}
	});

	test("in Block mode completing asks for a reason and cancelling leaves the encounter draft", async ({
		page,
		request,
	}) => {
		await setBlockerEnforcement(request, "Block");
		const encounter = await freshEncounter(request, patient);

		try {
			await saveMark(request, { patient, encounter: encounter.name, status: "Worse" });

			const chart = new ChartPage(page);
			await chart.open({ patient, encounter: encounter.name });
			await chart.setSection("review");
			await expect(
				chart.root.locator('[data-test="review-readiness-mode"][data-mode="Block"]'),
			).toBeVisible();

			await page.locator('[data-test="complete-session"]').click();

			const dialog = page.locator('[data-test="readiness-override-dialog"] .modal-dialog');
			await expect(dialog).toBeVisible();
			await expect(dialog.locator("li")).not.toHaveCount(0);

			await dialog.locator(".btn-modal-close").click();
			await expect(dialog).toBeHidden();

			const saved = await getDoc<{ docstatus: number }>(request, "Patient Encounter", encounter.name);
			expect(saved.docstatus).toBe(0);
		} finally {
			await cleanupEncounter(request, encounter.name);
		}
	});
});
