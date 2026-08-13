import { expect, test } from "@playwright/test";
import {
	ChartContext,
	cleanupEncounter,
	freshEncounter,
	getSeedPatient,
} from "../helpers/derma";
import { ChartPage } from "../pages";

/**
 * Assessment Modes (spec 2026-08-13-assessment_tab_mode_toggle).
 *
 * The format switch lives on the Assessment tab button as a segmented
 * SOAP/Structured toggle; the in-panel banner is gone. The load-bearing
 * properties: a stamped mode survives a reload, switching away from a written
 * format asks once (away from an empty one is instant), and the tab shows a
 * tick once the visit holds any saved assessment content.
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
		await chart.setSection("assessment");
		await expect(page.locator('[data-test="assessment-panel"]')).toBeVisible();
		return chart;
	}

	/** A fresh encounter is empty, so switching to SOAP never needs the confirm. */
	async function ensureSoap(page: import("@playwright/test").Page) {
		const soap = page.locator('[data-test="assessment-mode-soap"]');
		if ((await soap.getAttribute("data-active")) !== "true") {
			await soap.click();
		}
		await expect(soap).toHaveAttribute("data-active", "true");
	}

	test("renders configured fields and the tab toggle instead of the banner", async ({ page }) => {
		await openAssessment(page);

		const panel = page.locator('[data-test="assessment-panel"]');
		await expect(panel).not.toContainText("No fields found");
		await expect(page.locator('[data-test="assessment-mode-banner"]')).toHaveCount(0);

		await expect(page.locator('[data-test="assessment-mode-toggle"]')).toBeVisible();
		await expect(
			page.locator('[data-test^="assessment-mode-"][data-active="true"]'),
		).toHaveCount(1);

		// A fresh encounter holds no content, so the tab has no tick yet.
		await expect(page.locator('[data-test="assessment-tick"]')).toHaveCount(0);
	});

	test("a SOAP note reopens as SOAP after a reload and ticks the tab", async ({ page }) => {
		await openAssessment(page);
		await ensureSoap(page);

		const subjective = page.locator('[data-test="soap-custom_derma_soap_subjective"]');
		await subjective.fill("Itching on both cheeks for three weeks.");

		const save = page.locator('[data-test="assessment-save"]');
		await expect(save).toBeEnabled();
		await save.click();
		await expect(page.locator('[data-test="assessment-tick"]')).toBeVisible();

		await openAssessment(page);

		await expect(page.locator('[data-test="assessment-mode-soap"]')).toHaveAttribute(
			"data-active",
			"true",
		);
		await expect(page.locator('[data-test="assessment-tick"]')).toBeVisible();
		await expect(page.locator('[data-test="soap-note-fields"]')).toContainText(
			"Itching on both cheeks for three weeks.",
		);
	});

	test("leaving a written format confirms once and keeps its content", async ({ page }) => {
		await openAssessment(page);
		await ensureSoap(page);

		await page
			.locator('[data-test="soap-custom_derma_soap_plan"]')
			.fill("Topical steroid, review in two weeks.");
		await page.locator('[data-test="assessment-save"]').click();
		await expect(page.locator('[data-test="assessment-tick"]')).toBeVisible();

		// SOAP now holds content, so leaving it asks once.
		await page.locator('[data-test="assessment-mode-structured"]').click();
		await page.locator(".modal.show .btn-primary:visible").first().click();
		await expect(page.locator('[data-test="assessment-mode-structured"]')).toHaveAttribute(
			"data-active",
			"true",
		);

		// Structured is empty, so returning to SOAP is instant - no dialog. The
		// switch writes nothing and deletes nothing, and a switch leaves the panel
		// in edit mode, so the content is a textarea value rather than rendered text.
		await page.locator('[data-test="assessment-mode-soap"]').click();
		await expect(page.locator('[data-test="assessment-mode-soap"]')).toHaveAttribute(
			"data-active",
			"true",
		);
		await expect(page.locator(".modal.show")).toHaveCount(0);
		await expect(page.locator('[data-test="soap-custom_derma_soap_plan"]')).toHaveValue(
			"Topical steroid, review in two weeks.",
		);
	});
});
