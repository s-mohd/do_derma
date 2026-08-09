import { expect, Page, test } from "@playwright/test";
import { ensureChartContext, getSeedPatient, ChartContext } from "../helpers/derma";
import { ChartPage, SectionKey } from "../pages";

const ALL_SECTIONS: SectionKey[] = [
	"assessment",
	"procedures",
	"photos",
	"prescriptions",
	"consent",
	"review",
];

/** Seed the section preference the way the chart itself writes it, then reboot. */
async function seedStoredSection(page: Page, section: string): Promise<void> {
	await page.evaluate(async (value) => {
		window.localStorage.setItem("do_derma_chart_last_section", value);
		await window.frappe?.model?.user_settings?.save?.("Derma Chart", "last_section", value);
	}, section);
}

/**
 * The revamped tab spine: six tabs in visit order, no right rail, and no control
 * that appears in two places. These assertions are the decluttering contract -
 * a duplicate creeping back in fails here rather than in review.
 */
test.describe("Derma Chart tab spine", () => {
	let context: ChartContext;

	test.beforeAll(async ({ request }) => {
		context = await ensureChartContext(request, await getSeedPatient(request));
	});

	test("shows the six visit-order tabs and no right rail", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);

		// Each tab renders <span>label</span><small>hint</small>; only the label is asserted.
		const labels = await chart.sectionBar.locator("button > span").allTextContents();
		expect(labels.map((text) => text.trim())).toEqual([
			"Assessment",
			"Procedures",
			"Photos",
			"Prescription",
			"Consent",
			"Review",
		]);

		await expect(page.locator(".derma-console-side")).toHaveCount(0);
		await expect(page.locator(".derma-quick-panel")).toHaveCount(0);
	});

	// Scoped to the chart root: the surrounding desk chrome and the do_health
	// sidebar own their own Refresh controls, which this app does not touch.
	test("has no Refresh button on any tab", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);

		for (const section of ALL_SECTIONS) {
			await chart.setSection(section);
			await expect(
				chart.root.getByRole("button", { name: "Refresh", exact: true }),
				`Refresh button still rendered on the ${section} tab`,
			).toHaveCount(0);
		}
	});

	test("offers exactly one Complete and one annotation entry point", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);

		for (const section of ALL_SECTIONS) {
			await chart.setSection(section);
			await expect(chart.root.locator('[data-test="complete-session"]')).toHaveCount(1);
			await expect(chart.root.getByRole("button", { name: "Complete Session" })).toHaveCount(0);
		}

		await chart.setSection("assessment");
		await expect(chart.root.locator('[data-test="annotate-consultation"]')).toHaveCount(1);

		await chart.setSection("photos");
		await expect(chart.root.locator('[data-test="annotate-consultation"]')).toHaveCount(0);
	});

	test("offers one photo upload entry point, on the Photos tab", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);

		for (const section of ALL_SECTIONS) {
			await chart.setSection(section);
			await expect(
				chart.root.getByRole("button", { name: /Upload/ }),
				`unexpected upload control count on the ${section} tab`,
			).toHaveCount(section === "photos" ? 2 : 0);
		}

		// On Photos the two are distinct jobs: save a new photo, and pull today's
		// photo into the Before/After comparison.
		await chart.setSection("photos");
		await expect(chart.root.locator('[data-test="photos-upload"]')).toHaveCount(1);
		await expect(chart.root.getByRole("button", { name: "Upload Today" })).toHaveCount(1);
	});

	/**
	 * The server degrades a broken section to its fallback and names it in
	 * context_errors (api.py _safe_derma_context). Only the label crosses the
	 * boundary, so the label is what the browser is given to inject here.
	 */
	test("degrades a failed section to a retry notice and reloads on Retry", async ({ page }) => {
		const chart = new ChartPage(page);
		let chartCalls = 0;

		await page.route("**/api/method/do_derma.api.get_patient_derma_chart*", async (route) => {
			chartCalls += 1;
			const response = await route.fetch();
			const body = await response.json();
			body.message.context_errors = ["procedures"];
			await route.fulfill({ response, json: body });
		});

		await chart.open(context);
		await chart.setSection("procedures");

		const notice = chart.root.locator('[data-test="degraded-section"]');
		await expect(notice).toBeVisible();
		await expect(notice).toContainText("Couldn't load");

		// Every other section still renders - one broken query is not a broken page.
		await expect(chart.root.locator('[data-test="procedure-panel"]')).toBeVisible();

		const before = chartCalls;
		await notice.locator('[data-test="degraded-section-retry"]').click();
		await expect.poll(() => chartCalls).toBeGreaterThan(before);

		await chart.setSection("consent");
		await expect(chart.root.locator('[data-test="degraded-section"]')).toHaveCount(0);

		// Retry leaves a chart call in flight; drop the handler before teardown.
		await page.unrouteAll({ behavior: "ignoreErrors" });
	});

	test("lands a stored five-tab preference on Assessment", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);

		await seedStoredSection(page, "clinical");
		await chart.open(context);

		await expect(chart.sectionTab("assessment")).toHaveAttribute("data-active", "true");
	});

	test("lands an unrecognised stored preference on Assessment", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);

		await seedStoredSection(page, "atlantis");
		await chart.open(context);

		await expect(chart.sectionTab("assessment")).toHaveAttribute("data-active", "true");
	});
});
