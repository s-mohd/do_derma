import { APIRequestContext, expect, test } from "@playwright/test";
import {
	ChartContext,
	SEED,
	cleanupClinicalProcedure,
	cleanupEncounter,
	freshClinicalProcedure,
	freshEncounter,
	getSeedPatient,
	listMarks,
} from "../helpers/derma";
import { callMethodRaw, createDoc, deleteDoc, getDoc, updateDoc } from "../helpers/frappe";
import { ChartPage } from "../pages";

/**
 * `custom_derma_allowed_body_templates` used to be a hint the chart could ignore. The mark write
 * refuses a body map outside it, so the studio opens on a map the anchor's own procedure template
 * allows - otherwise the first mark of a session is lost to a refusal.
 *
 * The seeded fixture set holds one body map and points every template at it (40 specs assert exact
 * counts against it), so this spec creates a second map of its own and deletes it again. The
 * anchor procedure is `E2E Filler`, which is why borrowing its allowed list moves the canvas.
 */
test.describe("Body map scope", () => {
	const SCOPE_MAP = "E2E Scope Map";
	let context: ChartContext;
	let procedure: string;

	async function setAllowedBodyTemplates(request: APIRequestContext, value: string): Promise<void> {
		await updateDoc(request, "Clinical Procedure Template", SEED.pointTemplate, {
			custom_derma_allowed_body_templates: value,
		});
	}

	test.beforeEach(async ({ request }) => {
		const seeded = await getDoc<{ image: string; gender: string; template_type: string }>(
			request,
			"Derma Body Template",
			SEED.bodyTemplate,
		);
		await createDoc(request, "Derma Body Template", {
			title: SCOPE_MAP,
			gender: seeded.gender,
			template_type: seeded.template_type,
			view_key: "e2e_scope_map",
			// The studio only offers maps that carry an image, so it borrows the seeded one.
			image: seeded.image,
		});
		await setAllowedBodyTemplates(request, SCOPE_MAP);

		const patient = await getSeedPatient(request);
		const encounter = await freshEncounter(request, patient);
		context = { patient, encounter: encounter.name };
		procedure = (await freshClinicalProcedure(request, patient, encounter.name)).name;
	});

	test.afterEach(async ({ request }) => {
		if (context.encounter) await cleanupEncounter(request, context.encounter);
		if (procedure) await cleanupClinicalProcedure(request, procedure);
		await setAllowedBodyTemplates(request, SEED.bodyTemplate);
		await deleteDoc(request, "Derma Body Template", SCOPE_MAP);
	});

	test("refuses a mark on a body map the procedure's template forbids", async ({ request }) => {
		const response = await callMethodRaw(request, "do_derma.api.save_chart_mark", {
			values: {
				patient: context.patient,
				encounter: context.encounter,
				procedure_template: SEED.pointTemplate,
				body_template: SEED.bodyTemplate,
				x_percent: 40,
				y_percent: 40,
			},
		});

		expect(response.ok, "a forbidden body map was accepted").toBe(false);
		expect(response.body).toContain("cannot be charted on");
	});

	test("opens the studio on a body map the procedure allows", async ({ page, request }) => {
		test.setTimeout(240000);
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
		await page.waitForTimeout(2000);

		const canvas = page.locator(".derma-annotation-canvas canvas").first();
		const box = (await canvas.boundingBox())!;
		await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.4);
		await page.waitForTimeout(2500);

		const marks = await listMarks(request, { encounter: context.encounter });
		expect(marks, "the mark was refused instead of landing on the allowed map").toHaveLength(1);
		expect(marks[0].body_template).toBe(SCOPE_MAP);
	});
});
