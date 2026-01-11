"""
Logic module for Versioned Translator
Handles DeepL translation and async processing via frappe.enqueue
"""

import frappe
from frappe import _
import json
import hashlib
import requests
from datetime import datetime


def on_doc_load(doc, method):
	"""
	Hook function called when any document is loaded.
	Injects original_language field if DocType is in Translation Map.
	"""
	try:
		# Prüfe, ob DocType in Translation Map aktiv ist
		translation_map_name = frappe.db.get_value(
			"Translation Map",
			{"doctype_name": doc.doctype, "is_active": 1},
			"name"
		)
		if translation_map_name:
			# Injiziere original_language basierend auf frappe.local.lang
			if not hasattr(doc, "original_language"):
				doc.original_language = frappe.local.lang or "de"
	except frappe.DoesNotExistError:
		# Kein Translation Map für diesen DocType - kein Problem
		pass
	except Exception as e:
		frappe.log_error(f"Error in on_doc_load for {doc.doctype}: {str(e)}", "Versioned Translator")


def on_doc_update(doc, method):
	"""
	Hook function called when any document is updated.
	Checks if relevant fields changed and triggers async translation.
	"""
	try:
		# Prüfe, ob Translation Settings aktiviert sind
		settings = get_translation_settings()
		if not settings or not settings.get("enable_auto_translation") or not settings.get("auto_translate_on_update"):
			return

		# Prüfe, ob DocType in Translation Map aktiv ist
		translation_map_name = frappe.db.get_value(
			"Translation Map",
			{"doctype_name": doc.doctype, "is_active": 1},
			"name"
		)
		if not translation_map_name:
			return
		
		translation_map = frappe.get_doc("Translation Map", translation_map_name, ignore_permissions=True)
		if not translation_map.field_mappings:
			return

		# Prüfe, ob relevante Felder geändert wurden
		# In Frappe werden geänderte Felder in doc._changed markiert
		changed_fields = getattr(doc, "_changed", [])
		relevant_fields_changed = False

		for field_mapping in translation_map.field_mappings:
			if field_mapping.translate and field_mapping.field_name in changed_fields:
				relevant_fields_changed = True
				break

		if relevant_fields_changed:
			# Rufe translate_to_all_languages asynchron auf
			frappe.enqueue(
				"versioned_translator.logic.translate_to_all_languages",
				doctype=doc.doctype,
				docname=doc.name,
				queue="long",
				timeout=600
			)

	except frappe.DoesNotExistError:
		# Kein Translation Map - kein Problem
		pass
	except Exception as e:
		frappe.log_error(f"Error in on_doc_update for {doc.doctype} {doc.name}: {str(e)}", "Versioned Translator")


def translate_to_all_languages(doctype, docname):
	"""
	Translate document to all configured target languages using DeepL API.
	Creates entries in Translation Store for each language.
	"""
	try:
		# Lade Dokument
		doc = frappe.get_doc(doctype, docname)

		# Hole Translation Settings
		settings = get_translation_settings()
		if not settings or not settings.get("api_key"):
			frappe.log_error("DeepL API Key not configured in Translation Settings", "Versioned Translator")
			return

		api_key = settings.get("api_key")
		source_language = settings.get("default_source_language") or "de"
		target_languages_str = settings.get("default_target_languages") or ""
		
		if not target_languages_str:
			frappe.log_error("No target languages configured in Translation Settings", "Versioned Translator")
			return

		target_languages = [lang.strip().upper() for lang in target_languages_str.split(",") if lang.strip()]

		# Hole Translation Map
		translation_map_name = frappe.db.get_value(
			"Translation Map",
			{"doctype_name": doctype, "is_active": 1},
			"name"
		)
		if not translation_map_name:
			frappe.log_error(f"No active Translation Map found for {doctype}", "Versioned Translator")
			return
		
		translation_map = frappe.get_doc("Translation Map", translation_map_name, ignore_permissions=True)
		if not translation_map.field_mappings:
			frappe.log_error(f"No active Translation Map found for {doctype}", "Versioned Translator")
			return

		# Sammle zu übersetzende Felder
		fields_to_translate = {}
		for field_mapping in translation_map.field_mappings:
			if field_mapping.translate and hasattr(doc, field_mapping.field_name):
				field_value = getattr(doc, field_mapping.field_name)
				if field_value:
					fields_to_translate[field_mapping.field_name] = str(field_value)

		if not fields_to_translate:
			frappe.log_error(f"No fields to translate for {doctype} {docname}", "Versioned Translator")
			return

		# Erstelle Version ID basierend auf modified timestamp
		# Dies gewährleistet Revisionssicherheit
		version_id = get_version_id(doc)

		# Übersetze für jede Zielsprache
		for target_lang in target_languages:
			try:
				# Übersetze alle Felder
				translated_fields = {}
				for field_name, field_value in fields_to_translate.items():
					translated_text = translate_text(api_key, field_value, source_language, target_lang)
					if translated_text:
						translated_fields[field_name] = translated_text

				if translated_fields:
					# Speichere im Translation Store
					save_translation_to_store(
						doctype=doctype,
						docname=docname,
						version_id=version_id,
						language=target_lang.lower(),
						translated_content=translated_fields
					)

			except Exception as e:
				frappe.log_error(f"Error translating {doctype} {docname} to {target_lang}: {str(e)}", "Versioned Translator")
				# Setze Status auf Failed
				update_translation_status(doctype, docname, version_id, target_lang, "Failed")

	except Exception as e:
		frappe.log_error(f"Error in translate_to_all_languages for {doctype} {docname}: {str(e)}", "Versioned Translator")


def translate_text(api_key, text, source_lang, target_lang):
	"""
	Translate single text using DeepL API REST endpoint.
	Returns translated text or None on error.
	"""
	try:
		# DeepL API URL (kann später konfigurierbar gemacht werden)
		api_url = "https://api-free.deepl.com/v2/translate"

		# Request-Daten als form-urlencoded
		# requests.post macht URL-Encoding automatisch bei data=
		data = {
			"text": text,
			"source_lang": source_lang.upper(),
			"target_lang": target_lang.upper()
		}

		headers = {
			"Authorization": f"DeepL-Auth-Key {api_key}",
			"Content-Type": "application/x-www-form-urlencoded"
		}

		# REST-Call an DeepL
		# requests.post encodiert data automatisch als form-urlencoded
		response = requests.post(api_url, data=data, headers=headers, timeout=30)

		if response.status_code == 200:
			result = response.json()
			if "translations" in result and len(result["translations"]) > 0:
				return result["translations"][0].get("text")
		else:
			frappe.log_error(
				f"DeepL API Error: {response.status_code} - {response.text}",
				"Versioned Translator"
			)

	except requests.exceptions.RequestException as e:
		frappe.log_error(f"DeepL API Request Error: {str(e)}", "Versioned Translator")
	except Exception as e:
		frappe.log_error(f"Error in translate_text: {str(e)}", "Versioned Translator")

	return None


def get_version_id(doc):
	"""
	Generate version ID based on document modified timestamp.
	This ensures revision safety.
	"""
	# Nutze modified timestamp als Version ID
	# Format: doctype_name_modified_timestamp_hash
	if hasattr(doc, "modified") and doc.modified:
		modified_str = doc.modified.strftime("%Y%m%d%H%M%S") if isinstance(doc.modified, datetime) else str(doc.modified)
		version_string = f"{doc.doctype}_{doc.name}_{modified_str}"
		# Erstelle Hash für kürzere ID
		version_hash = hashlib.md5(version_string.encode()).hexdigest()[:12]
		return f"{doc.name}_{version_hash}"
	else:
		# Fallback: Nutze current timestamp
		current_time = datetime.now().strftime("%Y%m%d%H%M%S")
		return f"{doc.name}_{current_time}"


def save_translation_to_store(doctype, docname, version_id, language, translated_content):
	"""
	Save translated content to Translation Store.
	"""
	try:
		# Prüfe, ob bereits ein Eintrag existiert
		existing = frappe.db.get_value(
			"Translation Store",
			{
				"parent_doctype": doctype,
				"parent_name": docname,
				"version_id": version_id,
				"language": language
			},
			"name"
		)

		if existing:
			# Update existing entry
			store_doc = frappe.get_doc("Translation Store", existing)
			store_doc.translated_content = json.dumps(translated_content)
			store_doc.translation_status = "Completed"
			store_doc.last_translated = datetime.now()
			store_doc.save(ignore_permissions=True)
		else:
			# Create new entry
			store_doc = frappe.get_doc({
				"doctype": "Translation Store",
				"parent_doctype": doctype,
				"parent_name": docname,
				"version_id": version_id,
				"language": language,
				"translated_content": json.dumps(translated_content),
				"translation_status": "Completed",
				"edit_mode": 0,
				"last_translated": datetime.now()
			})
			store_doc.insert(ignore_permissions=True)

		frappe.db.commit()

	except Exception as e:
		frappe.log_error(f"Error saving to Translation Store: {str(e)}", "Versioned Translator")
		frappe.db.rollback()


def update_translation_status(doctype, docname, version_id, language, status):
	"""
	Update translation status in Translation Store.
	"""
	try:
		existing = frappe.db.get_value(
			"Translation Store",
			{
				"parent_doctype": doctype,
				"parent_name": docname,
				"version_id": version_id,
				"language": language
			},
			"name"
		)

		if existing:
			store_doc = frappe.get_doc("Translation Store", existing)
			store_doc.translation_status = status
			store_doc.save(ignore_permissions=True)
			frappe.db.commit()
		else:
			# Create entry with failed status
			store_doc = frappe.get_doc({
				"doctype": "Translation Store",
				"parent_doctype": doctype,
				"parent_name": docname,
				"version_id": version_id,
				"language": language,
				"translated_content": "{}",
				"translation_status": status,
				"edit_mode": 0
			})
			store_doc.insert(ignore_permissions=True)
			frappe.db.commit()

	except Exception as e:
		frappe.log_error(f"Error updating translation status: {str(e)}", "Versioned Translator")
		frappe.db.rollback()


def get_translation_for_ui(doctype, docname, version_id, language):
	"""
	Get translated content for UI.
	Can be called from frontend to load translated content for specific version.
	Returns translated content as dict or None.
	"""
	try:
		store_name = frappe.db.get_value(
			"Translation Store",
			{
				"parent_doctype": doctype,
				"parent_name": docname,
				"version_id": version_id,
				"language": language
			},
			"name"
		)
		
		if not store_name:
			return None
		
		store_doc = frappe.get_doc("Translation Store", store_name, ignore_permissions=True)

		if store_doc.translated_content:
			# Parse JSON content
			if isinstance(store_doc.translated_content, str):
				return json.loads(store_doc.translated_content)
			return store_doc.translated_content

	except frappe.DoesNotExistError:
		# Kein Eintrag gefunden
		return None
	except Exception as e:
		frappe.log_error(f"Error in get_translation_for_ui: {str(e)}", "Versioned Translator")
		return None


def get_translation_settings():
	"""
	Get Translation Settings (Single DocType).
	Returns dict with settings or None.
	"""
	try:
		settings = frappe.get_single("Translation Settings")
		return {
			"api_key": settings.get("api_key"),
			"enable_auto_translation": settings.get("enable_auto_translation"),
			"auto_translate_on_update": settings.get("auto_translate_on_update"),
			"default_source_language": settings.get("default_source_language"),
			"default_target_languages": settings.get("default_target_languages")
		}
	except Exception as e:
		frappe.log_error(f"Error getting Translation Settings: {str(e)}", "Versioned Translator")
		return None


@frappe.whitelist()
def get_fields_for_translation(doctype_name):
	"""
	Get all translatable fields for a DocType.
	Returns list of fields with field_name and field_label.
	"""
	try:
		if not doctype_name:
			frappe.throw(_("DocType name is required"))

		# Get DocType meta
		meta = frappe.get_meta(doctype_name)
		
		# Translatable field types
		translatable_types = ["Data", "Text", "Small Text", "Long Text", "HTML", "Text Editor"]
		
		fields = []
		for field in meta.fields:
			# Check if field type is translatable
			if field.fieldtype in translatable_types:
				# Skip system fields
				if field.fieldname in ["name", "owner", "creation", "modified", "modified_by"]:
					continue
				
				# Skip read-only fields that are usually system-generated
				if field.read_only and field.fieldtype == "Data":
					continue
				
				fields.append({
					"field_name": field.fieldname,
					"field_label": field.label or field.fieldname,
					"field_type": field.fieldtype
				})
		
		return fields

	except Exception as e:
		frappe.log_error(f"Error in get_fields_for_translation for {doctype_name}: {str(e)}", "Versioned Translator")
		frappe.throw(_(f"Error getting fields: {str(e)}"))
