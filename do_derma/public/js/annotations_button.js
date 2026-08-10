(() => {
	if (typeof frappe !== "undefined" && frappe.provide) {
		frappe.provide("do_derma");
	} else {
		window.do_derma = window.do_derma || {};
	}

	const translate = (...args) => (typeof __ === "function" ? __(...args) : args[0]);
	const escape = (value) => frappe.utils.escape_html(String(value ?? ""));
	const PLACEHOLDER = "/assets/frappe/images/default-image.png";

	/**
	 * Toolbar button listing the drawings on this encounter or procedure. do_derma reaches its
	 * annotations through the Derma Chart, so without this they are invisible from the document
	 * they belong to.
	 */
	const BUTTON_PREFIX = "Annotations (";
	const ANNOTATION_DOCTYPES = ["Patient Encounter", "Clinical Procedure"];
	const RETRY_DELAY_MS = 400;
	const MAX_ATTEMPTS = 8;

	do_derma.setup_annotations_button = async function (frm) {
		if (!frm?.doc?.patient || frm.doc.__islocal) return;
		// The separate `annotation` app adds an identically labelled button on these same two
		// doctypes. Two of them is a support ticket, and that app was here first.
		if (frappe.boot?.versions?.annotation) return;
		// This runs from two form events, because a throwing handler in another app can abort
		// the refresh chain before reaching us. Frappe's own bookkeeping is the duplicate guard.
		if (Object.keys(frm.custom_buttons || {}).some((label) => label.startsWith(BUTTON_PREFIX))) return;

		let annotations = [];
		try {
			const { message } = await frappe.call({
				method: "do_derma.api.get_derma_annotation_summary",
				args: { doctype: frm.doctype, docname: frm.docname },
			});
			annotations = message || [];
		} catch (error) {
			// A listing failure must not break the form it is decorating.
			console.warn("[do_derma] Unable to load annotations", error);
			return;
		}

		frm.add_custom_button(
			translate("Annotations ({0})").replace("{0}", annotations.length),
			() => do_derma.show_annotations_dialog(frm, annotations)
		);
	};

	do_derma.show_annotations_dialog = function (frm, annotations) {
		const dialog = new frappe.ui.Dialog({
			title: translate("Annotations"),
			size: "large",
			primary_action_label: translate("New Annotation"),
			primary_action: () => {
				dialog.hide();
				do_derma.open_annotation_chart(frm);
			},
		});

		dialog.$body.append(renderCards(annotations));
		dialog.$body.on("click", "[data-annotation-preview]", (event) => {
			const name = $(event.currentTarget).attr("data-annotation-preview");
			const annotation = annotations.find((row) => row.name === name);
			if (annotation) do_derma.show_annotation_preview(annotation);
		});
		dialog.$body.on("click", "[data-annotation-edit]", () => {
			dialog.hide();
			do_derma.open_annotation_chart(frm);
		});
		dialog.show();
	};

	function renderCards(annotations) {
		if (!annotations.length) {
			return $(`<p class="text-muted">${escape(translate("No drawings on this document yet."))}</p>`);
		}

		const cards = annotations
			.map((annotation) => {
				const image = escape(annotation.image || PLACEHOLDER);
				const label = escape(annotation.label || translate("Drawing"));
				const date = escape(frappe.datetime.str_to_user(annotation.creation) || "");
				// annotation_data is HTML this app generated itself (the badge legend table).
				const legend = annotation.annotation_data
					? `<div class="derma-annotation-legend">${annotation.annotation_data}</div>`
					: "";
				return `
					<div class="derma-annotation-card">
						<img src="${image}" alt="${label}" data-annotation-preview="${escape(annotation.name)}" loading="lazy" />
						<div class="derma-annotation-card-body">
							<strong>${label}</strong>
							<small class="text-muted">${date}</small>
							${legend}
						</div>
						<button class="btn btn-xs btn-default" data-annotation-edit="${escape(annotation.name)}">
							${escape(translate("Edit"))}
						</button>
					</div>`;
			})
			.join("");
		return $(`<div class="derma-annotation-cards">${cards}</div>`);
	}

	do_derma.show_annotation_preview = function (annotation) {
		const image = escape(annotation.image || PLACEHOLDER);
		const legend = annotation.annotation_data
			? `<div class="derma-annotation-preview-legend">${annotation.annotation_data}</div>`
			: "";
		frappe.msgprint({
			title: annotation.label || translate("Drawing"),
			message: `<div class="derma-annotation-preview-pane">
				<img src="${image}" alt="" />
				${legend}
			</div>`,
			wide: true,
		});
	};

	/**
	 * Fallback for a form whose refresh chain never reaches our handler. Frappe runs every app's
	 * `refresh` handlers in one sequence, so one that throws silently skips every handler
	 * registered after it - which is the state of Patient Encounter on some sites. The form
	 * clears custom buttons as it refreshes, so this re-adds ours once that has settled.
	 */
	frappe.router?.on?.("change", () => {
		const route = frappe.get_route() || [];
		if (route[0] !== "Form" || !ANNOTATION_DOCTYPES.includes(route[1])) return;

		let attempts = 0;
		const retry = () => {
			attempts += 1;
			const frm = window.cur_frm;
			const onThisForm = frm?.doctype === route[1] && frm?.docname === route[2];
			const alreadyAdded = Object.keys(frm?.custom_buttons || {}).some((label) => label.startsWith(BUTTON_PREFIX));
			if (onThisForm && !alreadyAdded) do_derma.setup_annotations_button(frm);
			if (!alreadyAdded && attempts < MAX_ATTEMPTS) setTimeout(retry, RETRY_DELAY_MS);
		};
		setTimeout(retry, RETRY_DELAY_MS);
	});

	/** Drawings are created and edited in the Derma Chart, which owns the studio. */
	do_derma.open_annotation_chart = async function (frm) {
		const encounter = frm.doctype === "Patient Encounter" ? frm.docname : frm.doc.custom_patient_encounter;
		const result = await do_derma.openChart({
			patient: { patient: frm.doc.patient, appointment: frm.doc.appointment, encounter },
		});
		if (result?.route) frappe.set_route(...result.route);
	};
})();
