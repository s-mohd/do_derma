import { expect, Locator, Page } from "@playwright/test";
import { ChartContext } from "../helpers/derma";

export type SectionKey = "clinical" | "photos" | "prescriptions" | "consent" | "review";

/**
 * The Derma Chart desk page (/app/derma-chart).
 *
 * Two things about this page are easy to get wrong and are handled here once:
 *
 * 1. The Vue bundle is loaded lazily by `frappe.require` inside `on_page_show`
 *    (derma_chart.js), so the page must be waited on by a do_derma-owned
 *    element. `networkidle` never settles - the desk holds long-poll sockets open.
 * 2. The active section is persisted to localStorage under
 *    `do_derma_chart_last_section` (DermaChart.vue), so the chart does not
 *    reliably open on "clinical". Always set the section explicitly.
 */
export class ChartPage {
	readonly page: Page;
	readonly root: Locator;
	readonly sectionBar: Locator;
	readonly emptyState: Locator;
	readonly patientName: Locator;

	constructor(page: Page) {
		this.page = page;
		this.root = page.locator('[data-test="derma-chart-root"]');
		this.sectionBar = page.locator('[data-test="derma-section-bar"]');
		this.emptyState = page.locator('[data-test="chart-empty-state"]');
		this.patientName = page.locator('[data-test="header-patient-name"]');
	}

	/**
	 * Deep-link into the chart. Query params land in `frappe.route_options`
	 * (frappe/public/js/frappe/router.js:531), which is exactly what App.vue reads,
	 * and route options take precedence over the do_health sidebar.
	 */
	async open(context: ChartContext): Promise<void> {
		const params = new URLSearchParams();
		for (const [key, value] of Object.entries(context)) {
			if (value) params.set(key, String(value));
		}

		await this.page.goto(`/app/derma-chart?${params.toString()}`);
		await expect(this.root).toBeVisible();
		await expect(this.sectionBar).toBeVisible();
	}

	/** Open the chart with no context at all, to assert the empty state. */
	async openWithoutContext(): Promise<void> {
		await this.page.goto("/app/derma-chart");
		await expect(this.root).toBeVisible();
	}

	sectionTab(key: SectionKey): Locator {
		return this.page.locator(`[data-test="section-tab-${key}"]`);
	}

	async setSection(key: SectionKey): Promise<void> {
		await this.sectionTab(key).click();
		await expect(this.sectionTab(key)).toHaveAttribute("data-active", "true");
	}

	async activeSection(): Promise<string | null> {
		return this.page.locator('[data-test^="section-tab-"][data-active="true"]').getAttribute("data-test");
	}
}
