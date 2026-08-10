import { expect, Page, test } from "@playwright/test";
import { getSeedClinicalProcedure, getSeedPatient } from "../helpers/derma";

/**
 * Drawings used to be reachable only from the Derma Chart, so the document they belong to gave
 * no sign they existed. The toolbar button lists them on the two doctypes that can hold them.
 */
test.describe("Annotations toolbar button", () => {
	let encounter: string;
	let procedure: string;

	test.beforeAll(async ({ request }) => {
		const patient = await getSeedPatient(request);
		const seeded = await getSeedClinicalProcedure(request, patient);
		procedure = seeded.name;
		encounter = seeded.encounter!;
	});

	const annotationsButton = (page: Page) => page.getByRole("button", { name: /^Annotations \(\d+\)$/ });

	/**
	 * Desk forms load lazily and the button is added by an async call inside `refresh`, so the
	 * button appearing is itself the readiness signal. Never wait on networkidle here - the desk
	 * holds long-poll sockets open.
	 */
	async function openForm(page: Page, doctype: string, name: string): Promise<void> {
		await page.goto(`/app/${doctype}/${encodeURIComponent(name)}`);
		await expect(annotationsButton(page)).toBeVisible({ timeout: 45000 });
	}

	test("counts the drawings on a Patient Encounter", async ({ page }) => {
		await openForm(page, "patient-encounter", encounter);
	});

	test("counts the drawings on a Clinical Procedure", async ({ page }) => {
		await openForm(page, "clinical-procedure", procedure);
	});

	test("lists the drawings with a preview and a way into the chart", async ({ page }) => {
		test.setTimeout(120000);
		await openForm(page, "clinical-procedure", procedure);
		await annotationsButton(page).click();

		const dialog = page.locator(".modal.show").filter({ hasText: "Annotations" }).last();
		await expect(dialog).toBeVisible();
		await expect(dialog.locator(".derma-annotation-card").first(), "the seeded procedure has no drawing to list").toBeVisible();
		await expect(dialog.getByRole("button", { name: "New Annotation" })).toBeVisible();

		await dialog.locator(".derma-annotation-card img").first().click();
		await expect(page.locator(".derma-annotation-preview-pane")).toBeVisible();
	});
});
