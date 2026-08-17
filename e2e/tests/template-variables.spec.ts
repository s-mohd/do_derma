import { APIRequestContext, expect, Page, test } from "@playwright/test";
import {
	ChartContext,
	SEED,
	cleanupClinicalProcedure,
	cleanupEncounter,
	freshClinicalProcedure,
	freshEncounter,
	getSeedPatient,
} from "../helpers/derma";
import { getList, updateDoc } from "../helpers/frappe";
import { ChartPage } from "../pages";

/**
 * Required variables used to be invisible until Clinical Procedure creation threw. The studio now
 * shows them while charting - and, deliberately, still lets the mark be placed without them.
 *
 * `plane` is the variable under test because it is one of the mark's own fieldnames, so filling it
 * is what the creation gate reads too. The seeded template requires nothing (40 specs assert
 * against that fixture set), so this spec owns the required list for its own run and puts it back.
 */
test.describe("Template variables in the studio", () => {
	let context: ChartContext;
	let procedure: string;

	let seededVariables: string;

	async function setRequiredVariables(request: APIRequestContext, fieldnames: string[]): Promise<void> {
		await updateDoc(request, "Clinical Procedure Template", SEED.pointTemplate, {
			custom_derma_required_fields: JSON.stringify(fieldnames),
		});
	}

	/** The seeded list is asserted by 40 other specs, so it is restored in `afterEach`. */
	async function setTemplateVariables(request: APIRequestContext, json: string): Promise<void> {
		await updateDoc(request, "Clinical Procedure Template", SEED.pointTemplate, {
			custom_derma_variables_json: json,
		});
	}

	test.beforeEach(async ({ request }) => {
		const [template] = await getList<{ custom_derma_variables_json?: string }>(
			request,
			"Clinical Procedure Template",
			{ fields: ["custom_derma_variables_json"], filters: { name: SEED.pointTemplate }, limit: 1 }
		);
		seededVariables = template?.custom_derma_variables_json ?? "";
		await setRequiredVariables(request, ["plane"]);
		const patient = await getSeedPatient(request);
		const encounter = await freshEncounter(request, patient);
		context = { patient, encounter: encounter.name };
		procedure = (await freshClinicalProcedure(request, patient, encounter.name)).name;
	});

	test.afterEach(async ({ request }) => {
		if (context.encounter) await cleanupEncounter(request, context.encounter);
		if (procedure) await cleanupClinicalProcedure(request, procedure);
		await setRequiredVariables(request, []);
		await setTemplateVariables(request, seededVariables);
	});

	async function openStudioWithProcedure(page: Page): Promise<void> {
		const chart = new ChartPage(page);
		await chart.open(context);
		await chart.setSection("procedures");
		await chart.root.locator('[data-test="procedure-annotate"]').first().click();
		await expect(page.locator(".derma-annotation-canvas canvas").first()).toBeVisible();
		await page.waitForTimeout(6000);

		const studio = page.locator(".derma-annotation-modal");
		await studio.getByRole("button", { name: "Procedures", exact: true }).click();
		await studio.getByRole("button", { name: SEED.pointTemplate }).click();
		await studio.getByRole("button", { name: "Procedures", exact: true }).click();
		await expect(page.locator('[data-test="annotation-variable-editor"]')).toBeVisible();
	}

	const requiredNote = (page: Page) => page.locator('[data-test="annotation-variable-required-note"]');

	test("marks the required variable and counts what is still missing", async ({ page }) => {
		await openStudioWithProcedure(page);

		const editor = page.locator('[data-test="annotation-variable-editor"]');
		const planeRow = editor.locator('[data-test="annotation-variable-row"][data-fieldname="plane"]');
		await expect(planeRow.locator('[data-test="annotation-variable-required"]')).toBeVisible();

		// Product is configured but not required, so it carries no asterisk.
		const productRow = editor.locator('[data-test="annotation-variable-row"][data-fieldname="product"]');
		await expect(productRow).toHaveAttribute("data-required", "0");
		await expect(productRow.locator('[data-test="annotation-variable-required"]')).toHaveCount(0);

		await expect(requiredNote(page)).toHaveAttribute("data-missing-count", "1");
		await expect(requiredNote(page)).toContainText("Plane");

		await planeRow.locator("select").selectOption("Subdermal");
		await expect(requiredNote(page), "a filled required variable still counted as missing").toHaveCount(0);
	});

	test("places and saves a mark whether or not the required variable is filled", async ({
		page,
		request,
	}) => {
		await openStudioWithProcedure(page);
		const canvas = page.locator(".derma-annotation-canvas canvas").first();
		const box = (await canvas.boundingBox())!;

		// Blank: the note is up, and the mark must be placed anyway.
		await expect(requiredNote(page)).toHaveAttribute("data-missing-count", "1");
		await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.4);
		await page.waitForTimeout(2500);

		const editor = page.locator('[data-test="annotation-variable-editor"]');
		await editor
			.locator('[data-test="annotation-variable-row"][data-fieldname="plane"] select')
			.selectOption("Subdermal");
		await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.55);
		await page.waitForTimeout(2500);

		const marks = await getList<{ name: string; plane?: string }>(request, "Derma Chart Mark", {
			fields: ["name", "plane"],
			filters: { encounter: context.encounter },
			orderBy: "creation asc",
			limit: 10,
		});

		expect(marks.map((mark) => mark.plane ?? ""), "a blank required variable blocked the mark").toEqual([
			"",
			"Subdermal",
		]);
	});

	test("writes a saved mark one edit at a time, so no save collides with its predecessor", async ({
		page,
		request,
	}) => {
		test.setTimeout(240000);
		// `lot_no` is a mark fieldname, so what the studio writes can be read back off the mark.
		await setTemplateVariables(
			request,
			JSON.stringify([
				...JSON.parse(seededVariables || "[]"),
				{ variable_name: "Lot No", fieldname: "lot_no", label: "Lot No", type: "Data" },
			])
		);
		await openStudioWithProcedure(page);
		const canvas = page.locator(".derma-annotation-canvas canvas").first();
		const box = (await canvas.boundingBox())!;
		const mark = { x: box.x + box.width * 0.5, y: box.y + box.height * 0.4 };
		await page.mouse.click(mark.x, mark.y);
		await page.waitForTimeout(2500);

		// Leave placement mode, then pick the mark back up - editing it is what writes as you type.
		await page.getByRole("button", { name: "Stop Tagging" }).click();
		await page.mouse.click(mark.x, mark.y);
		await page.waitForTimeout(1500);
		const editor = page.locator('[data-test="annotation-variable-editor"]');
		await expect(editor, "the editor is not bound to the clicked mark").not.toHaveAttribute(
			"data-editing-mark",
			""
		);

		// Each keystroke writes the mark. Two writes in flight together race on the mark's
		// timestamp and the loser comes back 417, so they have to queue. The delay widens the
		// window a fast local site would otherwise close before the next keystroke lands.
		let inFlight = 0;
		let mostInFlight = 0;
		await page.route("**/do_derma.api.save_chart_mark", async (route) => {
			inFlight += 1;
			mostInFlight = Math.max(mostInFlight, inFlight);
			await new Promise((resolve) => setTimeout(resolve, 400));
			await route.continue();
			inFlight -= 1;
		});

		await editor
			.locator('[data-test="annotation-variable-row"][data-fieldname="lot_no"] input')
			.pressSequentially("LOT-24-0917", { delay: 25 });
		await page.waitForTimeout(8000);

		expect(mostInFlight, "two writes of one mark were in flight together").toBe(1);
		await expect(
			page.locator(".modal-title", { hasText: "Unable to update mark" }),
			"a mark write was refused"
		).toHaveCount(0);

		const marks = await getList<{ name: string; lot_no?: string }>(request, "Derma Chart Mark", {
			fields: ["name", "lot_no"],
			filters: { encounter: context.encounter },
			limit: 10,
		});
		expect(marks.map((row) => row.lot_no ?? ""), "the last keystroke never reached the mark").toEqual([
			"LOT-24-0917",
		]);
	});
});
