app_name = "do_derma"
app_title = "Do Derma"
app_publisher = "Sayed Mohamed"
app_description = "Dermatology charting app for healthcare clinics"
app_email = "sayed10998@gmail.com"
app_license = "mit"

# Runtime expectations: healthcare, do_health, and annotation should be installed
# before this app is used. This bench's installer treats local required_apps names
# as remote tags, so the dependency is intentionally documented instead of enforced
# through the Frappe hook.

app_include_js = [
	"/assets/do_derma/js/derma_sidebar.js",
]

fixtures = [
	{"dt": "Custom Field", "filters": {"module": "Do Derma"}},
	{"dt": "Property Setter", "filters": {"module": "Do Derma"}},
]
