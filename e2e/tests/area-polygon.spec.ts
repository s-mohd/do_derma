import { expect, test } from "@playwright/test";
import {
	CLOSE_TOLERANCE_RATIO,
	closeTolerance,
	validateAreaPolygon,
} from "../../do_derma/public/js/body-template-editor/polygon";

/**
 * Pure geometry, so this one runs in Node without a page. It is the guard that keeps an
 * open or self-crossing outline from becoming a Derma Body Template Part.
 */
test.describe("Area outline validation", () => {
	const square: Array<[number, number]> = [
		[0, 0],
		[100, 0],
		[100, 100],
		[0, 100],
		[0, 0],
	];

	test("accepts a closed square", () => {
		expect(validateAreaPolygon(square, 4)).toEqual({ isValid: true, reason: "" });
	});

	test("accepts a triangle closed within the tolerance rather than exactly", () => {
		const triangle: Array<[number, number]> = [
			[0, 0],
			[80, 0],
			[40, 60],
			[2, 1],
		];

		expect(validateAreaPolygon(triangle, 4).isValid).toBe(true);
	});

	test("rejects an outline that never returns to its start", () => {
		const open: Array<[number, number]> = [
			[0, 0],
			[100, 0],
			[100, 100],
			[0, 100],
		];

		expect(validateAreaPolygon(open, 4)).toEqual({ isValid: false, reason: "open" });
	});

	test("rejects a bow tie that crosses itself", () => {
		const bowTie: Array<[number, number]> = [
			[0, 0],
			[100, 100],
			[100, 0],
			[0, 100],
			[0, 0],
		];

		expect(validateAreaPolygon(bowTie, 4)).toEqual({ isValid: false, reason: "self_intersecting" });
	});

	test("rejects a stroke with fewer than three points", () => {
		expect(validateAreaPolygon([[0, 0]], 4)).toEqual({ isValid: false, reason: "too_few_points" });
		expect(
			validateAreaPolygon(
				[
					[0, 0],
					[50, 50],
				],
				4,
			),
		).toEqual({ isValid: false, reason: "too_few_points" });
	});

	test("rejects a there-and-back stroke that closes on two distinct points", () => {
		const doubleBack: Array<[number, number]> = [
			[0, 0],
			[50, 50],
			[0, 0],
		];

		expect(validateAreaPolygon(doubleBack, 4)).toEqual({ isValid: false, reason: "too_few_points" });
	});

	test("rejects a missing or malformed outline instead of throwing", () => {
		expect(validateAreaPolygon(undefined, 4).isValid).toBe(false);
		expect(validateAreaPolygon([[0, 0], [10], [20, 20], [0, 0]] as never, 4).isValid).toBe(false);
	});

	test("scales the closing tolerance off the template's smaller dimension", () => {
		expect(closeTolerance({ renderedWidth: 600, renderedHeight: 800 })).toBeCloseTo(600 * CLOSE_TOLERANCE_RATIO);
		expect(closeTolerance({ renderedWidth: 900, renderedHeight: 400 })).toBeCloseTo(400 * CLOSE_TOLERANCE_RATIO);
		expect(closeTolerance(null)).toBeGreaterThan(0);
	});
});
