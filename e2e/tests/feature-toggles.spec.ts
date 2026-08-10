import { expect, test } from "@playwright/test";
import {
	ChartContext,
	ensureChartContext,
	getSeedPatient,
	resetFeatureToggles,
	setFeatureToggle,
} from "../helpers/derma";
import { ChartPage } from "../pages";

/**
 * The three Derma Settings toggles gate controls whose integration is not
 * finished. Off is the shipped default and the contract is "nothing visible on
 * the page is a no-op"; on restores the control without a code change.
 *
 * Every test restores the toggles, because workers: 1 means a toggle left on
 * leaks into every spec that runs after it.
 */
test.describe("Derma Settings feature toggles", () => {
	let context: ChartContext;

	test.beforeAll(async ({ request }) => {
		context = await ensureChartContext(request, await getSeedPatient(request));
	});

	test.beforeEach(async ({ request }) => {
		await resetFeatureToggles(request);
	});

	test.afterAll(async ({ request }) => {
		await resetFeatureToggles(request);
	});

	test("with every toggle off, no unfinished control renders", async ({ page }) => {
		const chart = new ChartPage(page);
		await chart.open(context);

		await chart.setSection("procedures");
		await expect(page.locator('[data-test="procedure-sync-billables"]')).toHaveCount(0);

		// The Lab filter lives inside the collapsed advanced-filter panel, so the
		// panel has to be open for its absence to mean anything.
		await page.locator('[data-test="procedure-filters-toggle"]').click();
		await expect(page.locator('[data-test="procedure-lab-filter"]')).toHaveCount(0);
		await expect(page.locator('[data-test="procedure-edit-surfaces"]')).toHaveCount(0);
		await expect(page.locator('[data-test="procedure-open-lab-case"]')).toHaveCount(0);
		await expect(page.locator('[data-test="procedure-create-lab-case"]')).toHaveCount(0);

		await chart.setSection("consent");
		await expect(page.locator('[data-test="consent-panel"]')).toBeVisible();
		await expect(page.locator('[data-test="consent-send-whatsapp"]')).toHaveCount(0);
		await expect(page.locator('[data-test="consent-remote-actions"]')).toHaveCount(0);

		// The tab is not emptied by the gate - its working control is still there.
		await expect(page.locator('[data-test="consent-create"]')).toBeVisible();
	});

	test("enable_billing_sync brings Sync Billables back", async ({ page, request }) => {
		const chart = new ChartPage(page);
		const syncButton = page.locator('[data-test="procedure-sync-billables"]');

		await chart.open(context);
		await chart.setSection("procedures");
		await expect(syncButton).toHaveCount(0);

		await setFeatureToggle(request, "enable_billing_sync", true);
		await chart.open(context);
		await chart.setSection("procedures");
		await expect(syncButton).toBeVisible();
	});

	test("enable_lab_cases brings the lab controls back", async ({ page, request }) => {
		const chart = new ChartPage(page);
		const labFilter = page.locator('[data-test="procedure-lab-filter"]');

		const openFilters = () => page.locator('[data-test="procedure-filters-toggle"]').click();

		await chart.open(context);
		await chart.setSection("procedures");
		await openFilters();
		await expect(labFilter).toHaveCount(0);

		await setFeatureToggle(request, "enable_lab_cases", true);
		await chart.open(context);
		await chart.setSection("procedures");
		await openFilters();
		await expect(labFilter).toBeVisible();
	});

	test("enable_whatsapp_consent brings the WhatsApp send back", async ({ page, request }) => {
		const chart = new ChartPage(page);
		const sendButton = page.locator('[data-test="consent-send-whatsapp"]');

		await chart.open(context);
		await chart.setSection("consent");
		await expect(sendButton).toHaveCount(0);

		await setFeatureToggle(request, "enable_whatsapp_consent", true);
		await chart.open(context);
		await chart.setSection("consent");
		await expect(sendButton).toBeVisible();
	});
});
