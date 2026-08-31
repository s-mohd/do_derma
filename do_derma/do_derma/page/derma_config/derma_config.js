frappe.pages["derma-config"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Derma Configuration"),
		single_column: true,
	});
};

frappe.pages["derma-config"].on_page_show = function (wrapper) {
	load_derma_config(wrapper);
};

function load_derma_config(wrapper) {
	const $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();

	frappe.require(["derma_config.bundle.css", "derma_config.bundle.js"]).then(() => {
		wrapper.derma_config = new frappe.ui.DermaConfig({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}
