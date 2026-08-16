import { APIRequestContext, expect, Page, test } from "@playwright/test";
import { SEED } from "../helpers/derma";
import { callMethod, createDoc, deleteDoc, getList } from "../helpers/frappe";

/**
 * The Body Map Designer, driven through the browser. Every fixture here is private to the
 * spec that creates it: these tests retire and restore areas, which no shared fixture can
 * survive. The seeded "E2E Face Map" is read for one thing only — the image URL, because a
 * template without an image never lays out its canvas.
 */

interface SavedPart {
	name: string;
	part_name: string;
	disabled: number;
	variables: Array<{ variable_name: string }>;
}

interface PartFixture {
	part_name: string;
	disabled?: number;
	variables?: Array<{ variable_name: string; type: string; options?: string }>;
}

/** A closed rectangle in template-relative 0..1 coordinates, the only shape the chart reads. */
function rectangle(left: number, top: number, width: number, height: number): number[][] {
	const [right, bottom] = [left + width, top + height];
	return [
		[left, top],
		[right, top],
		[right, bottom],
		[left, bottom],
		[left, top],
	];
}

const LAYOUTS = [rectangle(0.1, 0.1, 0.3, 0.2), rectangle(0.5, 0.1, 0.3, 0.2), rectangle(0.1, 0.5, 0.3, 0.2)];

test.describe("Body Map Designer", () => {
	let template = "";

	test.afterEach(async ({ request }) => {
		if (!template) return;
		await cleanupTemplate(request, template);
		template = "";
	});

	async function plantTemplate(request: APIRequestContext, parts: PartFixture[]): Promise<string> {
		const [seeded] = await getList<{ name: string; image: string }>(request, "Derma Body Template", {
			fields: ["name", "image"],
			filters: { title: SEED.bodyTemplate },
			limit: 1,
		});
		if (!seeded?.image) {
			throw new Error(
				`No image on "${SEED.bodyTemplate}". Run:\n` +
					"  bench --site dermaone.localhost execute do_derma.e2e_seed.setup_e2e_data",
			);
		}

		// Disabled on purpose. The designer opens a template by name and never reads the
		// flag; the chart's _get_body_templates filters on it, so a fixture that outlives
		// its cleanup cannot leak into another spec's template list.
		const created = await createDoc<{ name: string }>(request, "Derma Body Template", {
			title: `E2E Area Map ${Date.now()}`,
			template_type: "Face",
			gender: "Female",
			view_key: `e2e_area_map_${Date.now()}`,
			image: seeded.image,
			sequence: 99,
			disabled: 1,
		});

		await savePartsFor(request, created.name, parts);
		return created.name;
	}

	async function savePartsFor(
		request: APIRequestContext,
		bodyTemplate: string,
		parts: PartFixture[],
	): Promise<SavedPart[]> {
		return callMethod<SavedPart[]>(request, "do_derma.api.save_derma_body_template_parts", {
			body_template: bodyTemplate,
			parts: JSON.stringify(
				parts.map((part, index) => ({
					part_name: part.part_name,
					shape_json: JSON.stringify(LAYOUTS[index % LAYOUTS.length]),
					color: "#4dabf7",
					opacity: 0.2,
					disabled: part.disabled ?? 0,
					variables: part.variables ?? [],
				})),
			),
		});
	}

	async function readParts(request: APIRequestContext, bodyTemplate: string): Promise<SavedPart[]> {
		return callMethod<SavedPart[]>(request, "do_derma.api.get_derma_body_template_parts", {
			body_template: bodyTemplate,
			include_disabled: 1,
		});
	}

	async function cleanupTemplate(request: APIRequestContext, bodyTemplate: string): Promise<void> {
		const parts = await getList<{ name: string }>(request, "Derma Body Template Part", {
			fields: ["name"],
			filters: { body_template: bodyTemplate },
			limit: 50,
		});
		for (const part of parts) {
			try {
				await deleteDoc(request, "Derma Body Template Part", part.name);
			} catch (error: unknown) {
				// A part a mark still points at stays behind. Say so: a silent leak here is
				// how a fixture ends up in the next spec's assertions.
				console.warn(`Left ${part.name} behind:`, error);
			}
		}
		try {
			await deleteDoc(request, "Derma Body Template", bodyTemplate);
		} catch (error: unknown) {
			console.warn(`Left ${bodyTemplate} behind (it stays disabled):`, error);
		}
	}

	/** Never waits on networkidle: the desk holds long-poll sockets open forever. */
	async function openDesigner(page: Page, bodyTemplate: string): Promise<void> {
		await page.goto(`/app/derma-body-template-editor?template=${encodeURIComponent(bodyTemplate)}`);
		await expect(page.locator('[data-test="body-map-designer"]')).toBeVisible();
		await expect(page.locator(".derma-map-editor-canvas canvas").first()).toBeVisible();
		await page.waitForTimeout(3000);
	}

	function areaRow(page: Page, name: string) {
		return page.locator(`[data-test="area-row"][data-area-name="${name}"]`);
	}

	test("restores a retired area back onto the map", async ({ page, request }) => {
		template = await plantTemplate(request, [
			{ part_name: "E2E Cheek" },
			{ part_name: "E2E Jawline", disabled: 1 },
		]);

		await openDesigner(page, template);

		// The canvas only carries live areas; the retired one is out of the way but reachable.
		await expect(page.locator('[data-test="area-row"]')).toHaveCount(1);
		const toggle = page.locator('[data-test="retired-areas-toggle"]');
		await expect(toggle).toContainText("(1)");
		await toggle.click();
		await expect(page.locator('[data-test="retired-area"]')).toHaveCount(1);

		// Restore is local until Save, like every other edit in this designer.
		await page.locator('[data-test="restore-area"]').click();
		await expect(areaRow(page, "E2E Jawline")).toBeVisible();
		await expect(page.locator('[data-test="retired-areas-toggle"]')).toBeHidden();

		await page.locator('[data-test="save-areas"]').click();

		await expect
			.poll(async () => {
				const parts = await readParts(request, template);
				return parts.filter((part) => !part.disabled).map((part) => part.part_name).sort();
			})
			.toEqual(["E2E Cheek", "E2E Jawline"]);
	});

	test("retiring one area leaves every other area its own variables", async ({ page, request }) => {
		template = await plantTemplate(request, [
			{ part_name: "E2E Alpha", variables: [{ variable_name: "Alpha Depth", type: "Data" }] },
			{ part_name: "E2E Beta", variables: [{ variable_name: "Beta Depth", type: "Data" }] },
			{ part_name: "E2E Gamma", variables: [{ variable_name: "Gamma Depth", type: "Data" }] },
		]);

		await openDesigner(page, template);
		await expect(page.locator('[data-test="area-row"]')).toHaveCount(3);

		// Retire the middle area. Before the merge keyed on part_name, the save response
		// was zipped by array index and this reassigned Gamma's row to Beta's record.
		await areaRow(page, "E2E Beta").locator("button").click();
		await page.locator('[data-test="save-areas"]').click();
		await expect(page.locator('[data-test="retired-areas-toggle"]')).toContainText("(1)");

		await areaRow(page, "E2E Gamma").click();
		await expect(areaRow(page, "E2E Gamma").locator('[data-test="area-variable-name"]')).toHaveValue(
			"Gamma Depth",
		);

		const parts = await readParts(request, template);
		const byName = Object.fromEntries(parts.map((part) => [part.part_name, part]));
		expect(byName["E2E Beta"].disabled).toBe(1);
		expect(byName["E2E Alpha"].variables.map((row) => row.variable_name)).toEqual(["Alpha Depth"]);
		expect(byName["E2E Gamma"].variables.map((row) => row.variable_name)).toEqual(["Gamma Depth"]);
	});

	test("copies one area's variables onto the ticked areas", async ({ page, request }) => {
		template = await plantTemplate(request, [
			{
				part_name: "E2E Source",
				variables: [
					{ variable_name: "Plane", type: "Select", options: "Subdermal\nIntradermal" },
					{ variable_name: "Units", type: "Float" },
				],
			},
			{ part_name: "E2E Target One" },
			{ part_name: "E2E Target Two" },
		]);

		await openDesigner(page, template);

		await areaRow(page, "E2E Target One").locator('[data-test="area-copy-target"]').check();
		await areaRow(page, "E2E Target Two").locator('[data-test="area-copy-target"]').check();
		await areaRow(page, "E2E Source").click();

		const copy = areaRow(page, "E2E Source").locator('[data-test="copy-area-variables"]');
		await expect(copy).toContainText("2");
		await copy.click();
		await page.locator('[data-test="save-areas"]').click();

		await expect
			.poll(async () => {
				const parts = await readParts(request, template);
				const target = parts.find((part) => part.part_name === "E2E Target One");
				return target?.variables.map((row) => row.variable_name) ?? [];
			})
			.toEqual(["Plane", "Units"]);

		const parts = await readParts(request, template);
		const byName = Object.fromEntries(parts.map((part) => [part.part_name, part]));
		expect(byName["E2E Target Two"].variables.map((row) => row.variable_name)).toEqual(["Plane", "Units"]);
		expect(byName["E2E Source"].variables.map((row) => row.variable_name)).toEqual(["Plane", "Units"]);
	});

	test("refuses an outline that never closes", async ({ page, request }) => {
		template = await plantTemplate(request, [{ part_name: "E2E Only Area" }]);

		await openDesigner(page, template);
		await expect(page.locator('[data-test="area-row"]')).toHaveCount(1);

		const canvas = page.locator(".derma-map-editor-canvas canvas").first();
		const box = (await canvas.boundingBox())!;
		const corner = { x: box.x + box.width * 0.62, y: box.y + box.height * 0.2 };

		// Three clicks and Escape: a stroke that stops where it stopped.
		await page.mouse.click(corner.x, corner.y);
		await page.mouse.click(corner.x + 90, corner.y);
		await page.mouse.click(corner.x + 90, corner.y + 90);
		await page.keyboard.press("Escape");

		await expect(page.locator('[data-test="area-outline-refusal"]')).toBeVisible();
		await expect(page.locator('[data-test="area-row"]')).toHaveCount(1);
	});

	test("refuses a closed outline that crosses itself", async ({ page, request }) => {
		template = await plantTemplate(request, [{ part_name: "E2E Only Area" }]);

		await openDesigner(page, template);
		await expect(page.locator('[data-test="area-row"]')).toHaveCount(1);

		const canvas = page.locator(".derma-map-editor-canvas canvas").first();
		const box = (await canvas.boundingBox())!;
		const corner = { x: box.x + box.width * 0.62, y: box.y + box.height * 0.2 };

		// A bow tie: closed, but its two edges cross. Closed is not the same as usable.
		await page.mouse.click(corner.x, corner.y);
		await page.mouse.click(corner.x + 90, corner.y + 90);
		await page.mouse.click(corner.x + 90, corner.y);
		await page.mouse.click(corner.x, corner.y + 90);
		await page.mouse.click(corner.x, corner.y);

		await expect(page.locator('[data-test="area-outline-refusal"]')).toContainText("crosses itself");
		await expect(page.locator('[data-test="area-row"]')).toHaveCount(1);
	});

	test("accepts an outline closed back on its first point", async ({ page, request }) => {
		template = await plantTemplate(request, [{ part_name: "E2E Only Area" }]);

		await openDesigner(page, template);
		await expect(page.locator('[data-test="area-row"]')).toHaveCount(1);

		const canvas = page.locator(".derma-map-editor-canvas canvas").first();
		const box = (await canvas.boundingBox())!;
		const corner = { x: box.x + box.width * 0.62, y: box.y + box.height * 0.2 };

		await page.mouse.click(corner.x, corner.y);
		await page.mouse.click(corner.x + 90, corner.y);
		await page.mouse.click(corner.x + 90, corner.y + 90);
		await page.mouse.click(corner.x, corner.y);

		await expect(page.locator('[data-test="area-row"]')).toHaveCount(2);
		await expect(page.locator('[data-test="area-outline-refusal"]')).toBeHidden();
	});
});
