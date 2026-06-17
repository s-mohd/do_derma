(() => {
	if (typeof frappe !== "undefined" && frappe.provide) {
		frappe.provide("do_derma");
	} else {
		window.do_derma = window.do_derma || {};
	}

	const __ = window.__ || ((text) => text);
	const escapeHtml = (value) => frappe.utils.escape_html(value == null ? "" : String(value));

	const BODY_REGIONS = [
		{ key: "Head", label: __("Head"), view: "Body Front", x: 50, y: 12 },
		{ key: "Chest", label: __("Chest"), view: "Body Front", x: 50, y: 33 },
		{ key: "Abdomen", label: __("Abdomen"), view: "Body Front", x: 50, y: 48 },
		{ key: "Arm", label: __("Arm"), view: "Body Front", x: 26, y: 40 },
		{ key: "Arm", label: __("Arm"), view: "Body Front", x: 74, y: 40 },
		{ key: "Hand", label: __("Hand"), view: "Body Front", x: 20, y: 60 },
		{ key: "Hand", label: __("Hand"), view: "Body Front", x: 80, y: 60 },
		{ key: "Groin", label: __("Groin"), view: "Body Front", x: 50, y: 61 },
		{ key: "Leg", label: __("Leg"), view: "Body Front", x: 42, y: 76 },
		{ key: "Leg", label: __("Leg"), view: "Body Front", x: 58, y: 76 },
		{ key: "Foot", label: __("Foot"), view: "Body Front", x: 42, y: 94 },
		{ key: "Foot", label: __("Foot"), view: "Body Front", x: 58, y: 94 },
		{ key: "Scalp", label: __("Scalp"), view: "Face Front", x: 50, y: 10 },
		{ key: "Face", label: __("Forehead"), view: "Face Front", x: 50, y: 28 },
		{ key: "Face", label: __("Cheek"), view: "Face Front", x: 34, y: 48 },
		{ key: "Face", label: __("Cheek"), view: "Face Front", x: 66, y: 48 },
		{ key: "Face", label: __("Nose"), view: "Face Front", x: 50, y: 50 },
		{ key: "Face", label: __("Mouth"), view: "Face Front", x: 50, y: 68 },
		{ key: "Neck", label: __("Neck"), view: "Face Front", x: 50, y: 86 },
	];

	class DermaChartPage {
		constructor(wrapper) {
			this.wrapper = wrapper;
			this.$main = $(wrapper).find(".layout-main-section");
			this.context = null;
			this.data = null;
			this.view = "Body Front";
			this.mode = "skin";
			this.selected = null;
			this.unsubscribe = null;
			this.bindWatcher();
		}

		bindWatcher() {
			if (this.unsubscribe || !window.do_health?.patientWatcher) return;
			this.unsubscribe = window.do_health.patientWatcher.subscribe((patient) => {
				if (!patient || this.context?.patient === patient.patient) return;
				this.loadFromContext(patient);
			});
		}

		show() {
			const route = frappe.route_options || {};
			const sidebarContext = window.doHealthSidebar?.getSelectedPatient?.() || window.do_health?.patientWatcher?.read?.() || {};
			const context = {
				patient: route.patient || sidebarContext.patient,
				appointment: route.appointment || sidebarContext.appointment,
				encounter: route.encounter || sidebarContext.encounter_name || sidebarContext.encounter,
			};
			if (!context.patient) {
				this.renderEmpty();
				return;
			}
			this.loadFromContext(context);
		}

		async loadFromContext(context) {
			this.context = context;
			this.renderLoading();
			try {
				const { message } = await frappe.call({
					method: "do_derma.api.get_chart_context",
					args: context,
				});
				this.data = message;
				this.context = {
					patient: message.patient_id,
					appointment: message.appointment_id,
					encounter: message.encounter_id,
				};
				this.render();
			} catch (error) {
				console.warn("[do_derma] Failed to load chart", error);
				this.renderError();
			}
		}

		renderLoading() {
			this.$main.html(`<div class="derma-state">${__("Loading dermatology chart...")}</div>`);
		}

		renderEmpty() {
			this.$main.html(`
				<div class="derma-empty">
					<div>
						<h3>${__("Select a patient to begin")}</h3>
						<p>${__("Use the health sidebar to pin a patient and open the derma chart from the clinical actions.")}</p>
					</div>
				</div>
			`);
		}

		renderError() {
			this.$main.html(`<div class="derma-state derma-state--error">${__("Unable to load dermatology chart.")}</div>`);
		}

		render() {
			const patient = this.data?.patient || {};
			const appointment = this.data?.appointment || {};
			const encounter = this.data?.encounter || {};
			const age = patient.dob ? Math.floor((Date.now() - new Date(patient.dob)) / 31557600000) : "";
			const allergy = patient.custom_allergies || patient.allergies || __("None recorded");
			const visitType = appointment.custom_appointment_category || appointment.appointment_type || encounter.appointment_type || __("Visit");

			this.$main.html(`
				<div class="derma-shell">
					<header class="derma-session">
						<div class="derma-patient">
							${patient.image ? `<img src="${escapeHtml(patient.image)}" alt="">` : `<div class="derma-avatar">${escapeHtml((patient.patient_name || "?").slice(0, 1))}</div>`}
							<div>
								<h2>${escapeHtml(patient.patient_name || patient.name)}</h2>
								<div class="derma-meta">
									<span>${escapeHtml([age ? `${age}y` : "", patient.sex].filter(Boolean).join(", "))}</span>
									<span>${__("MRN")}: ${escapeHtml(patient.custom_file_number || patient.name || "")}</span>
									<span>${__("Visit")}: ${escapeHtml(visitType)}</span>
								</div>
							</div>
						</div>
						<div class="derma-session__signals">
							${this.renderSignal(__("Allergies"), allergy, allergy === __("None recorded") ? "muted" : "warn")}
							${this.renderSignal(__("Encounter"), encounter.name || this.context.encounter || __("Draft"), "good")}
							${this.renderSignal(__("Status"), encounter.status || appointment.status || __("In Progress"), "info")}
						</div>
						<div class="derma-session__actions">
							<button class="btn btn-default btn-sm" data-action="open-annotation"><i class="fa-regular fa-pen-swirl"></i> ${__("Annotate")}</button>
							<button class="btn btn-default btn-sm" data-action="open-encounter"><i class="fa-regular fa-file-medical"></i> ${__("Encounter")}</button>
							<button class="btn btn-primary btn-sm" data-action="refresh"><i class="fa-regular fa-rotate"></i> ${__("Refresh")}</button>
						</div>
					</header>
					<div class="derma-workspace">
						<nav class="derma-rail">
							${this.renderRailButton("skin", "fa-regular fa-user-doctor", __("Skin Exam"))}
							${this.renderRailButton("face", "fa-regular fa-face-smile", __("Face / Aesthetic"))}
							${this.renderRailButton("photos", "fa-regular fa-camera", __("Photos"))}
							${this.renderRailButton("orders", "fa-regular fa-flask-vial", __("Orders"))}
							${this.renderRailButton("rx", "fa-regular fa-prescription-bottle-medical", __("Rx"))}
							${this.renderRailButton("plan", "fa-regular fa-clipboard-check", __("Plan"))}
						</nav>
						<main class="derma-canvas-panel">
							<div class="derma-toolbar">
								<div class="derma-segments">
									${this.renderViewButton("Body Front")}
									${this.renderViewButton("Body Back")}
									${this.renderViewButton("Face Front")}
								</div>
								<div class="derma-toolbar__actions">
									<button class="btn btn-default btn-sm" data-action="new-finding"><i class="fa-regular fa-plus"></i> ${__("Finding")}</button>
									<button class="btn btn-default btn-sm" data-action="new-treatment"><i class="fa-regular fa-syringe"></i> ${__("Treatment")}</button>
									<button class="btn btn-default btn-sm" data-action="new-photo-set"><i class="fa-regular fa-images"></i> ${__("Photo Set")}</button>
								</div>
							</div>
							<div class="derma-map-shell">
								<div class="derma-map" data-map>
									${this.renderMapSvg()}
									${this.renderRegionHotspots()}
									${this.renderPins()}
								</div>
							</div>
							<section class="derma-timeline">
								<div class="derma-section-head">
									<h3>${__("Previous Activity")}</h3>
									<span>${(this.data.timeline || []).length} ${__("items")}</span>
								</div>
								<div class="derma-timeline__rows">${this.renderTimeline()}</div>
							</section>
						</main>
						<aside class="derma-context">
							${this.renderContextPanel()}
						</aside>
					</div>
				</div>
			`);
			this.bindEvents();
		}

		renderSignal(label, value, tone) {
			return `<div class="derma-signal derma-signal--${tone}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
		}

		renderRailButton(mode, icon, label) {
			return `<button class="${this.mode === mode ? "active" : ""}" data-mode="${mode}" title="${escapeHtml(label)}"><i class="${icon}"></i><span>${escapeHtml(label)}</span></button>`;
		}

		renderViewButton(view) {
			return `<button class="${this.view === view ? "active" : ""}" data-view="${escapeHtml(view)}">${escapeHtml(__(view))}</button>`;
		}

		renderMapSvg() {
			if (this.view === "Face Front") {
				return `
					<svg viewBox="0 0 360 520" role="img" aria-label="${__("Face map")}">
						<path d="M180 36 C108 36 76 96 80 174 C86 292 122 358 180 364 C238 358 274 292 280 174 C284 96 252 36 180 36Z" class="derma-figure"/>
						<path d="M128 154 C148 142 166 142 182 154 M178 154 C196 142 216 142 236 154" class="derma-guide"/>
						<path d="M180 174 C166 210 160 238 180 248 C202 238 194 210 180 174Z" class="derma-guide"/>
						<path d="M138 288 C166 310 196 310 224 288" class="derma-guide"/>
						<path d="M118 368 C128 430 152 478 180 492 C208 478 232 430 242 368" class="derma-guide"/>
						<line x1="180" y1="42" x2="180" y2="492" class="derma-midline"/>
					</svg>`;
			}
			const back = this.view === "Body Back";
			return `
				<svg viewBox="0 0 360 620" role="img" aria-label="${__(this.view)}">
					<circle cx="180" cy="58" r="38" class="derma-figure"/>
					<path d="M124 108 C144 92 216 92 236 108 L256 282 C236 320 204 338 180 338 C156 338 124 320 104 282Z" class="derma-figure"/>
					<path d="M116 130 C70 172 54 246 48 350 C58 360 72 360 80 350 C88 260 102 210 124 178Z" class="derma-figure"/>
					<path d="M244 130 C290 172 306 246 312 350 C302 360 288 360 280 350 C272 260 258 210 236 178Z" class="derma-figure"/>
					<path d="M134 330 C118 410 118 510 142 584 C156 592 170 590 178 580 C168 488 174 406 180 338Z" class="derma-figure"/>
					<path d="M226 330 C242 410 242 510 218 584 C204 592 190 590 182 580 C192 488 186 406 180 338Z" class="derma-figure"/>
					<line x1="180" y1="96" x2="180" y2="580" class="derma-midline"/>
					<path d="${back ? "M130 148 C162 170 198 170 230 148 M132 216 C162 236 198 236 228 216" : "M132 168 C162 156 198 156 228 168 M132 228 C162 244 198 244 228 228"}" class="derma-guide"/>
				</svg>`;
		}

		renderRegionHotspots() {
			return BODY_REGIONS
				.filter((region) => region.view === this.view)
				.map((region) => `
					<button class="derma-hotspot" style="left:${region.x}%;top:${region.y}%;" data-region="${escapeHtml(region.key)}" data-label="${escapeHtml(region.label)}" title="${escapeHtml(region.label)}">
						<span>+</span><em>${escapeHtml(region.label)}</em>
					</button>
				`)
				.join("");
		}

		renderPins() {
			const findings = (this.data?.findings || []).filter((row) => row.body_view === this.view);
			const treatments = (this.data?.treatments || []).filter((row) => row.body_view === this.view);
			return [
				...findings.map((row) => this.renderPin(row, "finding")),
				...treatments.map((row) => this.renderPin(row, "treatment")),
			].join("");
		}

		renderPin(row, type) {
			const title = type === "finding" ? row.diagnosis || row.finding_type || row.name : row.procedure_type || row.product_name || row.name;
			const tone = type === "finding" ? (row.severity || "Mild").toLowerCase() : "treatment";
			return `
				<button class="derma-pin derma-pin--${escapeHtml(tone)}" style="left:${flt(row.x_percent)}%;top:${flt(row.y_percent)}%;" data-kind="${type}" data-name="${escapeHtml(row.name)}" title="${escapeHtml(title)}">
					${type === "finding" ? "F" : "T"}
				</button>
			`;
		}

		renderContextPanel() {
			const findings = this.data?.findings || [];
			const treatments = this.data?.treatments || [];
			const photoSets = this.data?.photo_sets || [];
			return `
				<section class="derma-card">
					<div class="derma-section-head">
						<h3>${__("Quick Templates")}</h3>
						<span>${(this.data?.templates || []).length}</span>
					</div>
					<div class="derma-template-list">${this.renderTemplates()}</div>
				</section>
				<section class="derma-card">
					<div class="derma-section-head">
						<h3>${__("Today")}</h3>
						<span>${findings.length + treatments.length} ${__("records")}</span>
					</div>
					<div class="derma-today-list">
						${findings.slice(0, 8).map((row) => this.renderRecordRow(row, "finding")).join("") || `<div class="derma-muted">${__("No findings yet.")}</div>`}
						${treatments.slice(0, 8).map((row) => this.renderRecordRow(row, "treatment")).join("")}
					</div>
				</section>
				<section class="derma-card">
					<div class="derma-section-head">
						<h3>${__("Photos")}</h3>
						<span>${photoSets.length}</span>
					</div>
					${photoSets.slice(0, 5).map((row) => `<button class="derma-photo-row" data-open-doctype="Derma Photo Set" data-open-name="${escapeHtml(row.name)}"><strong>${escapeHtml(row.set_type || row.name)}</strong><span>${escapeHtml(row.body_region || row.body_view || "")}</span></button>`).join("") || `<div class="derma-muted">${__("No photo sets linked to this visit.")}</div>`}
				</section>
				<section class="derma-card derma-note-card">
					<div class="derma-section-head">
						<h3>${__("Generated Visit Summary")}</h3>
					</div>
					<pre>${escapeHtml(this.data?.narrative || __("Structured findings and treatments will build the visit summary."))}</pre>
				</section>
			`;
		}

		renderTemplates() {
			const templates = this.data?.templates || [];
			if (!templates.length) {
				return `<div class="derma-muted">${__("Create Derma Chart Template records for one-click charting.")}</div>`;
			}
			return templates.slice(0, 8).map((template) => `
				<button class="derma-template" data-template="${escapeHtml(template.name)}">
					<strong>${escapeHtml(template.title)}</strong>
					<span>${escapeHtml([template.workflow, template.body_view].filter(Boolean).join(" / "))}</span>
				</button>
			`).join("");
		}

		renderRecordRow(row, type) {
			const title = type === "finding" ? row.diagnosis || row.finding_type || row.name : row.procedure_type || row.product_name || row.name;
			const meta = type === "finding"
				? [row.severity, row.status, row.body_region].filter(Boolean).join(" / ")
				: [row.product_name, row.dose ? `${row.dose} ${row.dose_unit || ""}` : "", row.body_region].filter(Boolean).join(" / ");
			return `
				<button class="derma-record-row" data-kind="${type}" data-name="${escapeHtml(row.name)}">
					<strong>${escapeHtml(title)}</strong>
					<span>${escapeHtml(meta)}</span>
				</button>
			`;
		}

		renderTimeline() {
			const rows = this.data?.timeline || [];
			if (!rows.length) return `<div class="derma-muted">${__("No previous derma chart history.")}</div>`;
			return rows.slice(0, 10).map((row) => {
				const title = row.kind === "Finding" ? row.diagnosis || row.finding_type || row.name : row.procedure_type || row.product_name || row.name;
				const meta = [row.kind, row.body_region, row.status || row.workflow].filter(Boolean).join(" / ");
				return `<button class="derma-history-row" data-open-doctype="${row.kind === "Finding" ? "Derma Finding" : "Derma Treatment Entry"}" data-open-name="${escapeHtml(row.name)}"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(meta)}</span></button>`;
			}).join("");
		}

		bindEvents() {
			this.$main.find("[data-mode]").on("click", (event) => {
				this.mode = $(event.currentTarget).data("mode");
				if (this.mode === "face") this.view = "Face Front";
				this.render();
			});
			this.$main.find("[data-view]").on("click", (event) => {
				this.view = $(event.currentTarget).data("view");
				this.render();
			});
			this.$main.find("[data-action='refresh']").on("click", () => this.loadFromContext(this.context));
			this.$main.find("[data-action='open-encounter']").on("click", () => {
				if (this.context.encounter) frappe.set_route("Form", "Patient Encounter", this.context.encounter);
			});
			this.$main.find("[data-action='open-annotation']").on("click", () => this.openAnnotation());
			this.$main.find("[data-action='new-finding']").on("click", () => this.openFindingDialog({ body_view: this.view, x_percent: 50, y_percent: 50 }));
			this.$main.find("[data-action='new-treatment']").on("click", () => this.openTreatmentDialog({ body_view: this.view, x_percent: 50, y_percent: 50 }));
			this.$main.find("[data-action='new-photo-set']").on("click", () => this.openPhotoSetDialog({ body_view: this.view }));
			this.$main.find("[data-region]").on("click", (event) => {
				const $target = $(event.currentTarget);
				const location = {
					body_view: this.view,
					body_region: $target.data("region"),
					region_label: $target.data("label"),
					x_percent: this.parsePercent($target.css("left"), $target.parent().width()),
					y_percent: this.parsePercent($target.css("top"), $target.parent().height()),
				};
				this.openQuickEntry(location);
			});
			this.$main.find(".derma-map").on("dblclick", (event) => {
				if ($(event.target).closest("button").length) return;
				const rect = event.currentTarget.getBoundingClientRect();
				this.openQuickEntry({
					body_view: this.view,
					body_region: this.view.includes("Face") ? "Face" : "Other",
					x_percent: ((event.clientX - rect.left) / rect.width) * 100,
					y_percent: ((event.clientY - rect.top) / rect.height) * 100,
				});
			});
			this.$main.find("[data-kind][data-name]").on("click", (event) => this.openExisting($(event.currentTarget).data("kind"), $(event.currentTarget).data("name")));
			this.$main.find("[data-open-doctype]").on("click", (event) => frappe.set_route("Form", $(event.currentTarget).data("open-doctype"), $(event.currentTarget).data("open-name")));
			this.$main.find("[data-template]").on("click", (event) => this.applyTemplate($(event.currentTarget).data("template")));
		}

		parsePercent(value, total) {
			const px = parseFloat(value || 0);
			return total ? (px / total) * 100 : 50;
		}

		openQuickEntry(location) {
			const dialog = new frappe.ui.Dialog({
				title: `${__("Chart")} - ${location.region_label || location.body_region || this.view}`,
				fields: [
					{ fieldname: "hint", fieldtype: "HTML", options: `<div class="text-muted">${__("Choose what you want to record at this location.")}</div>` },
				],
			});
			dialog.set_primary_action(__("Finding"), () => {
				dialog.hide();
				this.openFindingDialog(location);
			});
			dialog.add_custom_action(__("Treatment"), () => {
				dialog.hide();
				this.openTreatmentDialog(location);
			});
			dialog.show();
		}

		openExisting(kind, name) {
			const source = kind === "finding" ? this.data.findings : this.data.treatments;
			const row = (source || []).find((item) => item.name === name);
			if (!row) return;
			if (kind === "finding") this.openFindingDialog(row);
			else this.openTreatmentDialog(row);
		}

		openFindingDialog(seed = {}) {
			const dialog = new frappe.ui.Dialog({
				title: seed.name ? __("Edit Finding") : __("New Finding"),
				fields: [
					{ fieldname: "finding_type", label: __("Finding Type"), fieldtype: "Select", options: "Lesion\nCondition\nAcne\nScar\nPigmentation\nInflammation\nHair\nNail\nOther", default: seed.finding_type || "Lesion", reqd: 1 },
					{ fieldname: "diagnosis", label: __("Diagnosis"), fieldtype: "Data", default: seed.diagnosis || "" },
					{ fieldname: "body_region", label: __("Body Region"), fieldtype: "Select", options: "Head\nFace\nScalp\nNeck\nChest\nAbdomen\nBack\nArm\nHand\nGroin\nLeg\nFoot\nOther", default: seed.body_region || "" },
					{ fieldname: "region_label", label: __("Region Label"), fieldtype: "Data", default: seed.region_label || "" },
					{ fieldname: "severity", label: __("Severity"), fieldtype: "Select", options: "Mild\nModerate\nSevere\nCritical", default: seed.severity || "Mild" },
					{ fieldname: "status", label: __("Status"), fieldtype: "Select", options: "Active\nMonitoring\nImproving\nResolved\nBiopsied\nExcised\nArchived", default: seed.status || "Active" },
					{ fieldname: "morphology", label: __("Morphology"), fieldtype: "Select", options: "\nMacule\nPapule\nPlaque\nNodule\nVesicle\nPustule\nComedone\nCyst\nScale\nCrust\nUlcer\nScar\nTelangiectasia\nOther", default: seed.morphology || "" },
					{ fieldname: "size_mm", label: __("Size (mm)"), fieldtype: "Float", default: seed.size_mm || "" },
					{ fieldname: "follow_up_required", label: __("Follow-up Required"), fieldtype: "Check", default: seed.follow_up_required || 0 },
					{ fieldname: "notes", label: __("Notes"), fieldtype: "Small Text", default: seed.notes || "" },
				],
				primary_action_label: __("Save Finding"),
				primary_action: async (values) => {
					await this.saveFinding({ ...seed, ...values });
					dialog.hide();
				},
			});
			dialog.show();
		}

		openTreatmentDialog(seed = {}) {
			const dialog = new frappe.ui.Dialog({
				title: seed.name ? __("Edit Treatment") : __("New Treatment"),
				fields: [
					{ fieldname: "workflow", label: __("Workflow"), fieldtype: "Select", options: "Medical\nAesthetic", default: seed.workflow || (this.mode === "face" ? "Aesthetic" : "Medical") },
					{ fieldname: "procedure_type", label: __("Procedure Type"), fieldtype: "Select", options: "Prescription\nBiopsy\nExcision\nCryotherapy\nInjection\nBotox\nFiller\nLaser\nPeel\nMicroneedling\nOther", default: seed.procedure_type || "" },
					{ fieldname: "body_region", label: __("Body Region"), fieldtype: "Select", options: "Head\nFace\nScalp\nNeck\nChest\nAbdomen\nBack\nArm\nHand\nGroin\nLeg\nFoot\nOther", default: seed.body_region || "" },
					{ fieldname: "region_label", label: __("Region Label"), fieldtype: "Data", default: seed.region_label || "" },
					{ fieldname: "product_name", label: __("Product / Device"), fieldtype: "Data", default: seed.product_name || "" },
					{ fieldname: "dose", label: __("Dose / Quantity"), fieldtype: "Float", default: seed.dose || "" },
					{ fieldname: "dose_unit", label: __("Dose Unit"), fieldtype: "Select", options: "\nUnits\nml\nmg\npass\nJ/cm2\nHz\nOther", default: seed.dose_unit || "" },
					{ fieldname: "lot_no", label: __("Lot No"), fieldtype: "Data", default: seed.lot_no || "" },
					{ fieldname: "expiry_date", label: __("Expiry Date"), fieldtype: "Date", default: seed.expiry_date || "" },
					{ fieldname: "settings", label: __("Settings"), fieldtype: "Small Text", default: seed.settings || "" },
					{ fieldname: "notes", label: __("Notes"), fieldtype: "Small Text", default: seed.notes || "" },
				],
				primary_action_label: __("Save Treatment"),
				primary_action: async (values) => {
					await this.saveTreatment({ ...seed, ...values });
					dialog.hide();
				},
			});
			dialog.show();
		}

		openPhotoSetDialog(seed = {}) {
			frappe.new_doc("Derma Photo Set", {
				patient: this.context.patient,
				appointment: this.context.appointment,
				encounter: this.context.encounter,
				body_view: seed.body_view || this.view,
				body_region: seed.body_region || "",
			});
		}

		async saveFinding(values) {
			const payload = this.basePayload(values);
			await frappe.call({ method: "do_derma.api.save_finding", args: { values: payload } });
			frappe.show_alert({ message: __("Finding saved."), indicator: "green" });
			await this.loadFromContext(this.context);
		}

		async saveTreatment(values) {
			const payload = this.basePayload(values);
			await frappe.call({ method: "do_derma.api.save_treatment", args: { values: payload } });
			frappe.show_alert({ message: __("Treatment saved."), indicator: "green" });
			await this.loadFromContext(this.context);
		}

		basePayload(values) {
			return {
				...values,
				patient: this.context.patient,
				appointment: this.context.appointment,
				encounter: this.context.encounter,
				body_view: values.body_view || this.view,
				x_percent: values.x_percent || 50,
				y_percent: values.y_percent || 50,
			};
		}

		applyTemplate(templateName) {
			const template = (this.data.templates || []).find((row) => row.name === templateName);
			if (!template) return;
			if (template.body_view) this.view = template.body_view;
			const seed = {
				body_view: template.body_view || this.view,
				finding_type: template.default_finding_type || "Condition",
				diagnosis: template.title,
				notes: template.narrative_template ? $("<div>").html(template.narrative_template).text() : "",
				x_percent: 50,
				y_percent: 50,
			};
			this.openFindingDialog(seed);
		}

		openAnnotation() {
			if (!this.context.encounter) return;
			const url = `/app/annotation?doctype=${encodeURIComponent("Patient Encounter")}&docname=${encodeURIComponent(this.context.encounter)}`;
			window.open(url, "_blank", "noopener,noreferrer");
		}
	}

	function flt(value) {
		const number = Number(value);
		return Number.isFinite(number) ? number : 0;
	}

	do_derma.DermaChartPage = DermaChartPage;
})();
