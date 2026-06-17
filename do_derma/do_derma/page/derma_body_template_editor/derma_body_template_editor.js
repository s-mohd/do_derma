frappe.pages["derma-body-template-editor"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Derma Body Map Designer"),
		single_column: true,
	});

	window.process = window.process || {};
	window.process.env = {
		NODE_ENV: "production",
		IS_PREACT: "false",
	};
};

frappe.pages["derma-body-template-editor"].on_page_show = function (wrapper) {
	load_derma_body_template_editor(wrapper);
};

function load_derma_body_template_editor(wrapper) {
	const $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();

	frappe.require(["body_template_editor.bundle.css", "body-template-editor.bundle.jsx"]).then(() => {
		wrapper.derma_body_template_editor = new frappe.ui.DermaBodyTemplateEditor({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}
