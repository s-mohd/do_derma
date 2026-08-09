import { expect, test } from "@playwright/test";
import {
	ChartContext,
	cleanupEncounter,
	freshEncounter,
	getSeedPatient,
} from "../helpers/derma";
import { ChartPage } from "../pages";

/**
 * Assessment Modes (spec 2026-08-09-derma_chart_revamp, Phase 1).
 *
 * This tab previously rendered "No fields found in Patient Encounter tab
 * custom_assessment" on any site lacking that Tab Break - which is every site.
 * The load-bearing property here is that a stamped mode survives a reload, so a
 * note always reopens in the format it was written in.
 *
 * Each spec takes a private draft encounter: these write and stamp, so sharing
 * the seeded one would poison whichever spec ran next.
 */
test.describe("Assessment modes", () => {
	let patient: string;
	let context: ChartContext;

	test.beforeEach(async ({ request }) => {
		patient = await getSeedPatient(request);
		const encounter = await freshEncounter(request, patient);
		context = { patient, encounter: encounter.name };
	});

	test.afterEach(async ({ request }) => {
		if (context?.encounter) await cleanupEncounter(request, context.encounter);
	});

	async function openAssessment(page: import("@playwright/test").Page) {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("clinical");
		await expect(page.locator('[data-test="assessment-panel"]')).toBeVisible();
		return chart;
	}

	test("renders configured fields instead of the missing-tab message", async ({ page }) => {
		await openAssessment(page);

		const panel = page.locator('[data-test="assessment-panel"]');
		await expect(panel).not.toContainText("No fields found");
		await expect(page.locator('[data-test="assessment-mode-banner"]')).toBeVisible();
		await expect(page.locator('[data-test="assessment-mode"]')).toHaveText(
			/SOAP Note|Structured Assessment/,
		);
	});

	test("a SOAP note reopens as SOAP after a reload", async ({ page }) => {
		await openAssessment(page);

		// A fresh encounter opens unstamped in the practitioner default.
		if ((await page.locator('[data-test="assessment-mode"]').textContent()) !== "SOAP Note") {
			await page.locator('[data-test="assessment-change-mode"]').click();
			await page.locator(".modal.show .btn-primary:visible").first().click();
		}
		await expect(page.locator('[data-test="assessment-mode"]')).toHaveText("SOAP Note");

		const subjective = page.locator('[data-test="soap-custom_derma_soap_subjective"]');
		await subjective.fill("Itching on both cheeks for three weeks.");

		const save = page.locator('[data-test="assessment-save"]');
		await expect(save).toBeEnabled();
		await save.click();
		await expect(page.locator('[data-test="assessment-mode-banner"]')).toContainText("Written as");

		await openAssessment(page);

		await expect(page.locator('[data-test="assessment-mode"]')).toHaveText("SOAP Note");
		await expect(page.locator('[data-test="soap-note-fields"]')).toContainText(
			"Itching on both cheeks for three weeks.",
		);
	});

	test("switching format keeps what the other format holds", async ({ page }) => {
		await openAssessment(page);

		if ((await page.locator('[data-test="assessment-mode"]').textContent()) !== "SOAP Note") {
			await page.locator('[data-test="assessment-change-mode"]').click();
			await page.locator(".modal.show .btn-primary:visible").first().click();
		}
		await page
			.locator('[data-test="soap-custom_derma_soap_plan"]')
			.fill("Topical steroid, review in two weeks.");
		await page.locator('[data-test="assessment-save"]').click();
		await expect(page.locator('[data-test="assessment-mode-banner"]')).toContainText("Written as");

		await page.locator('[data-test="assessment-change-mode"]').click();
		await page.locator(".modal.show .btn-primary:visible").first().click();
		await expect(page.locator('[data-test="assessment-mode"]')).toHaveText("Structured Assessment");

		// Switching writes nothing and deletes nothing, so the SOAP content is
		// still there. A switch leaves the panel in edit mode, so the content is
		// a textarea value rather than rendered text.
		await page.locator('[data-test="assessment-change-mode"]').click();
		await page.locator(".modal.show .btn-primary:visible").first().click();
		await expect(page.locator('[data-test="soap-custom_derma_soap_plan"]')).toHaveValue(
			"Topical steroid, review in two weeks.",
		);
	});
});
