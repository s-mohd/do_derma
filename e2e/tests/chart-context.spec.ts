import { expect, test } from "@playwright/test";
import { ensureChartContext, getChartContext, getSeedPatient, ChartContext } from "../helpers/derma";
import { ChartPage } from "../pages";

/**
 * Smoke coverage for the harness: the chart boots from a deep link with real
 * seeded context, its sections switch, and the degraded no-context path renders
 * the empty state instead of hanging.
 */
test.describe("Derma Chart context", () => {
	let patient: string;
	let context: ChartContext;

	test.beforeAll(async ({ request }) => {
		patient = await getSeedPatient(request);
		context = await ensureChartContext(request, patient);
		expect(context.patient).toBe(patient);
		expect(context.encounter, "ensure_chart_context should back-fill an encounter").toBeTruthy();
	});

	test("boots from a deep link and shows the seeded patient", async ({ page, request }) => {
		const chart = new ChartPage(page);
		await chart.open(context);

		await expect(chart.patientName).toContainText("E2E Derma Patient");

		// Never trust the DOM alone - re-read the context through the API.
		// get_chart_context resolves to *_id fields plus the full Patient dict.
		const server = await getChartContext(request, context);
		expect(server.patient_id).toBe(patient);
		expect(server.encounter_id).toBe(context.encounter);
		expect(server.patient?.patient_name).toBe("E2E Derma Patient");
	});

	test("switches between every section tab", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);

		await chart.setSection("clinical");
		await expect(page.locator('[data-test="clinical-section"]')).toBeVisible();

		await chart.setSection("photos");
		await expect(page.locator('[data-test="photos-section"]')).toBeVisible();

		await chart.setSection("prescriptions");
		await expect(page.locator('[data-test="prescription-panel"]')).toBeVisible();

		await chart.setSection("consent");
		await expect(page.locator('[data-test="consent-panel"]')).toBeVisible();

		await chart.setSection("review");
		await expect(page.locator('[data-test="review-section"]')).toBeVisible();
	});

	test("persists the chosen section as a user preference", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);

		await chart.setSection("consent");

		// persistDermaSection() writes localStorage synchronously and mirrors the
		// value into Frappe user settings asynchronously. Only the local write is
		// race-free, so that is what the harness asserts; the server round-trip is
		// only visible after a full desk boot.
		const stored = await page.evaluate(() =>
			window.localStorage.getItem("do_derma_chart_last_section"),
		);
		expect(stored).toBe("consent");
	});

	test("shows the empty state when opened without a patient", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.openWithoutContext();

		await expect(chart.emptyState).toBeVisible();
		await expect(chart.emptyState).toContainText("Select a patient");
	});
});
