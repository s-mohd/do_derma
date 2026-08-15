from __future__ import annotations

import frappe

FEMALE_IMAGE_ALIASES = {
	"Body Front": "Female Front Body",
	"Body Back": "Female Rear Body",
	"Body Left": "Female Left Body",
	"Body Right": "Female Right Body",
	"Face Left Profile": "Face Left",
}


STANDARD_TEMPLATES = [
	# Female body atlas. Generic names are kept for compatibility with existing derma defaults.
	("Body Front", "Body", "Female", "body_front", 10),
	("Body Right", "Body", "Female", "body_right", 20),
	("Body Back", "Body", "Female", "body_back", 30),
	("Body Left", "Body", "Female", "body_left", 40),
	("Face Left Profile", "Face", "Female", "face_left_profile", 110),
	("Face Left Oblique", "Face", "Female", "face_left_oblique", 120),
	("Face Front", "Face", "Female", "face_front", 130),
	("Face Right Oblique", "Face", "Female", "face_right_oblique", 140),
	("Face Right Profile", "Face", "Female", "face_right_profile", 150),
	("Scalp Front", "Scalp", "Female", "scalp_front", 210),
	("Scalp Top", "Scalp", "Female", "scalp_top", 220),
	("Scalp Back", "Scalp", "Female", "scalp_back", 230),
	("Hands Palmar", "Hands", "Female", "hands_palmar", 310),
	("Hands Dorsal", "Hands", "Female", "hands_dorsal", 320),
	("Chest", "Custom", "Female", "chest", 410),
	("Abdomen", "Custom", "Female", "abdomen", 420),
	("Upper Back", "Custom", "Female", "upper_back", 430),
	("Lower Back", "Custom", "Female", "lower_back", 440),
	("Left Arm", "Custom", "Female", "left_arm", 450),
	("Right Arm", "Custom", "Female", "right_arm", 460),
	("Left Hand", "Custom", "Female", "left_hand", 465),
	("Right Hand", "Custom", "Female", "right_hand", 466),
	("Left Leg", "Custom", "Female", "left_leg", 470),
	("Right Leg", "Custom", "Female", "right_leg", 480),
	("Left Foot", "Custom", "Female", "left_foot", 490),
	("Right Foot", "Custom", "Female", "right_foot", 500),
	("Neck Front", "Custom", "Female", "neck_front", 510),
	("Neck Back", "Custom", "Female", "neck_back", 520),
	("Eyes", "Custom", "Female", "eyes", 530),
	("Nose and Mouth", "Custom", "Female", "nose_mouth", 540),
	("Left Ear", "Custom", "Female", "left_ear", 550),
	("Right Ear", "Custom", "Female", "right_ear", 560),
	# Male body atlas.
	("Male Body Front", "Body", "Male", "male_body_front", 10),
	("Male Body Right", "Body", "Male", "male_body_right", 20),
	("Male Body Back", "Body", "Male", "male_body_back", 30),
	("Male Body Left", "Body", "Male", "male_body_left", 40),
	("Male Face Left Profile", "Face", "Male", "male_face_left_profile", 110),
	("Male Face Left Oblique", "Face", "Male", "male_face_left_oblique", 120),
	("Male Face Front", "Face", "Male", "male_face_front", 130),
	("Male Face Right Oblique", "Face", "Male", "male_face_right_oblique", 140),
	("Male Face Right Profile", "Face", "Male", "male_face_right_profile", 150),
	("Male Scalp Front", "Scalp", "Male", "male_scalp_front", 210),
	("Male Scalp Top", "Scalp", "Male", "male_scalp_top", 220),
	("Male Scalp Back", "Scalp", "Male", "male_scalp_back", 230),
	("Male Hands Palmar", "Hands", "Male", "male_hands_palmar", 310),
	("Male Hands Dorsal", "Hands", "Male", "male_hands_dorsal", 320),
	("Male Chest", "Custom", "Male", "male_chest", 410),
	("Male Abdomen", "Custom", "Male", "male_abdomen", 420),
	("Male Upper Back", "Custom", "Male", "male_upper_back", 430),
	("Male Lower Back", "Custom", "Male", "male_lower_back", 440),
	("Male Left Arm", "Custom", "Male", "male_left_arm", 450),
	("Male Right Arm", "Custom", "Male", "male_right_arm", 460),
	("Male Left Hand", "Custom", "Male", "male_left_hand", 465),
	("Male Right Hand", "Custom", "Male", "male_right_hand", 466),
	("Male Left Leg", "Custom", "Male", "male_left_leg", 470),
	("Male Right Leg", "Custom", "Male", "male_right_leg", 480),
	("Male Left Foot", "Custom", "Male", "male_left_foot", 490),
	("Male Right Foot", "Custom", "Male", "male_right_foot", 500),
	("Male Neck Front", "Custom", "Male", "male_neck_front", 510),
	("Male Neck Back", "Custom", "Male", "male_neck_back", 520),
	("Male Eyes", "Custom", "Male", "male_eyes", 530),
	("Male Nose and Mouth", "Custom", "Male", "male_nose_mouth", 540),
	("Male Left Ear", "Custom", "Male", "male_left_ear", 550),
	("Male Right Ear", "Custom", "Male", "male_right_ear", 560),
]


def execute():
	if not frappe.db.exists("DocType", "Derma Body Template"):
		return

	alias_images = {
		target: frappe.db.get_value("Derma Body Template", source, "image")
		for target, source in FEMALE_IMAGE_ALIASES.items()
		if frappe.db.exists("Derma Body Template", source)
	}

	for title, template_type, gender, view_key, sequence in STANDARD_TEMPLATES:
		doc = (
			frappe.get_doc("Derma Body Template", title)
			if frappe.db.exists("Derma Body Template", title)
			else frappe.new_doc("Derma Body Template")
		)
		doc.title = title
		doc.template_type = template_type
		doc.gender = gender
		doc.is_standard = 1
		doc.view_key = view_key
		doc.sequence = sequence
		doc.disabled = 0
		if alias_images.get(title) and not doc.image:
			doc.image = alias_images[title]
		doc.save(ignore_permissions=True)

	disable_alias_templates()
	update_category_allowed_templates()
	update_category_default_templates()


def disable_alias_templates():
	for alias in FEMALE_IMAGE_ALIASES.values():
		if frappe.db.exists("Derma Body Template", alias):
			frappe.db.set_value("Derma Body Template", alias, "disabled", 1, update_modified=False)


def update_category_allowed_templates():
	if not frappe.db.exists("DocType", "Clinical Procedure Template"):
		return
	for name, category in frappe.get_all(
		"Clinical Procedure Template",
		filters={"custom_derma_category": ["is", "set"]},
		fields=["name", "custom_derma_category"],
		as_list=True,
	):
		if category in {"Botox", "Filler", "Laser", "Acne", "Scar", "Pigmentation"}:
			allowed = "Face Front, Face Left Profile, Face Left Oblique, Face Right Oblique, Face Right Profile, Male Face Front, Male Face Left Profile, Male Face Left Oblique, Male Face Right Oblique, Male Face Right Profile"
		elif category in {"Lesion", "Biopsy"}:
			allowed = "Body Front, Body Back, Body Left, Body Right, Male Body Front, Male Body Back, Male Body Left, Male Body Right, Face Front, Male Face Front"
		else:
			allowed = "Body Front, Body Back, Body Left, Body Right, Face Front, Male Body Front, Male Body Back, Male Body Left, Male Body Right, Male Face Front"
		frappe.db.set_value(
			"Clinical Procedure Template",
			name,
			"custom_derma_allowed_body_templates",
			allowed,
			update_modified=False,
		)


def update_category_default_templates():
	if not frappe.db.exists("DocType", "Derma Procedure Category"):
		return
	defaults = {
		"Botox": "Face Front",
		"Filler": "Face Front",
		"Laser": "Face Front",
		"Acne": "Face Front",
		"Scar": "Face Front",
		"Pigmentation": "Face Front",
		"Lesion": "Body Front",
		"Biopsy": "Body Front",
	}
	for category, template in defaults.items():
		if frappe.db.exists("Derma Procedure Category", category) and frappe.db.exists(
			"Derma Body Template", template
		):
			frappe.db.set_value(
				"Derma Procedure Category", category, "default_body_template", template, update_modified=False
			)
