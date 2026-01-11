// Copyright (c) 2025, Your Name and contributors
// Translation Controller - Global Widget for Versioned Translator

(function() {
	'use strict';

	let translationWidget = {
		currentLanguage: 'original',
		originalValues: {},
		translatedValues: {},
		isTranslationActive: false,
		docType: null,
		docName: null,
		versionId: null,
		originalLanguage: 'de'
	};

	// Initialize translation widget on form refresh
	frappe.ui.form.on('*', {
		refresh: function(frm) {
			// Skip if no document
			if (!frm.doc || !frm.doc.doctype) return;

			// Reset widget state
			translationWidget.docType = frm.doc.doctype;
			translationWidget.docName = frm.doc.name;
			translationWidget.currentLanguage = 'original';
			translationWidget.originalValues = {};
			translationWidget.translatedValues = {};
			translationWidget.isTranslationActive = false;

			// Check if translation is configured for this DocType
			checkTranslationAvailability(frm);
		},

		before_save: function(frm) {
			// If in translated mode, restore original values before save
			if (translationWidget.currentLanguage !== 'original') {
				restoreOriginalValues(frm, true);
			}
		}
	});

	function checkTranslationAvailability(frm) {
		if (!frm.doc.doctype) return;
		
		// Quick check: Does a Translation Map exist for this DocType?
		frappe.call({
			method: 'frappe.client.get_list',
			args: {
				doctype: 'Translation Map',
				filters: {
					doctype_name: frm.doc.doctype,
					is_active: 1
				},
				limit_page_length: 1
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					// Translation is configured
					translationWidget.isTranslationActive = true;
					setupTranslationWidget(frm);
				}
			},
			error: function() {
				// Silently fail - translation not available
				translationWidget.isTranslationActive = false;
			}
		});
	}

	function setupTranslationWidget(frm) {
		// Remove existing widget if present
		if (frm.translation_widget) {
			frm.translation_widget.remove();
		}

		// Get original language from document or user language
		let originalLang = frm.doc.original_language || frappe.boot.lang || 'de';
		translationWidget.originalLanguage = originalLang;

		// Set original_language for new documents
		if (frm.is_new() && !frm.doc.original_language) {
			let userLang = frappe.boot.lang || 'de';
			frm.set_value('original_language', userLang);
			translationWidget.originalLanguage = userLang;
		}

		// Get version ID for existing documents
		if (!frm.is_new() && frm.doc.modified) {
			translationWidget.versionId = generateVersionId(frm.doc);
		}

		// Create widget HTML
		let widgetHtml = createWidgetHTML(originalLang);
		let $widget = $(widgetHtml);
		
		// Add to form toolbar
		// Try multiple locations to ensure compatibility
		if (frm.page && frm.page.$form_actions && frm.page.$form_actions.length) {
			// Primary location: form actions toolbar
			frm.page.$form_actions.prepend($widget);
		} else if (frm.$wrapper && frm.$wrapper.find('.form-actions').length) {
			// Alternative: form-actions div
			frm.$wrapper.find('.form-actions').first().prepend($widget);
		} else if (frm.page && frm.page.$inner_toolbar && frm.page.$inner_toolbar.length) {
			// Alternative: inner toolbar
			frm.page.$inner_toolbar.prepend($widget);
		} else {
			// Fallback: add as custom button in toolbar
			frm.add_custom_button(__('Translation'), function() {
				// Widget is shown inline, button not needed
			}, __('Tools'));
			return; // Skip widget setup if we can't find a location
		}

		frm.translation_widget = $widget;
		attachWidgetHandlers(frm, $widget);
	}

	function createWidgetHTML(originalLang) {
		let originalLangUpper = originalLang.toUpperCase();
		let targetLang = getTargetLanguage(originalLang);

		return `
			<div class="translation-widget" style="display: inline-flex; align-items: center; margin-right: 10px; gap: 8px;">
				<div class="btn-group" role="group">
					<button type="button" class="btn btn-sm btn-default translation-btn translation-btn-original active" data-lang="original">
						${originalLangUpper}
					</button>
					<button type="button" class="btn btn-sm btn-default translation-btn translation-btn-target" data-lang="${targetLang}">
						${targetLang.toUpperCase()}
					</button>
				</div>
				<div class="translation-info-badge" style="font-size: 11px; color: #6c757d;">
					<span class="source-info">Source: ${originalLangUpper}</span> | 
					<span class="status-info">Status: AI</span>
				</div>
			</div>
		`;
	}

	function getTargetLanguage(sourceLang) {
		// Default target language (can be enhanced to use Translation Settings)
		let langMap = {
			'de': 'en',
			'en': 'de',
			'fr': 'en',
			'es': 'en'
		};
		return langMap[sourceLang] || 'en';
	}

	function attachWidgetHandlers(frm, $widget) {
		// Handle language toggle buttons
		$widget.find('.translation-btn').on('click', function() {
			let targetLang = $(this).data('lang');
			toggleTranslation(frm, targetLang);
		});
	}

	function toggleTranslation(frm, targetLang) {
		if (targetLang === 'original') {
			// Switch back to original
			restoreOriginalValues(frm, false);
			updateButtonStates(frm, 'original');
		} else {
			// Switch to translated
			if (frm.is_new()) {
				frappe.msgprint(__('Please save the document first before viewing translations.'));
				return;
			}

			if (!translationWidget.versionId) {
				translationWidget.versionId = generateVersionId(frm.doc);
			}

			loadTranslation(frm, targetLang);
		}
	}

	function loadTranslation(frm, targetLang) {
		// Show loading indicator
		frappe.show_alert({
			message: __('Loading translation...'),
			indicator: 'blue'
		}, 2);

		// Save original values first (async, but continue)
		saveOriginalValues(frm, function() {
			// Call server method to get translation after saving original values
			frappe.call({
				method: 'versioned_translator.logic.get_translation_for_ui',
				args: {
					doctype: translationWidget.docType,
					docname: translationWidget.docName,
					version_id: translationWidget.versionId,
					language: targetLang
				},
				callback: function(r) {
					if (r.message && Object.keys(r.message).length > 0) {
						translationWidget.translatedValues = r.message;
						applyTranslation(frm, r.message);
						updateButtonStates(frm, targetLang);
						frappe.show_alert({
							message: __('Translation loaded'),
							indicator: 'green'
						}, 3);
					} else {
						frappe.msgprint(__('No translation available for this version.'));
						updateButtonStates(frm, 'original');
					}
				},
				error: function() {
					frappe.msgprint(__('Error loading translation.'));
					updateButtonStates(frm, 'original');
				}
			});
		});
	}

	function saveOriginalValues(frm, callback) {
		// Get field mappings for this DocType
		frappe.call({
			method: 'frappe.client.get_list',
			args: {
				doctype: 'Translation Map',
				filters: {
					doctype_name: translationWidget.docType,
					is_active: 1
				},
				fields: ['name'],
				limit_page_length: 1
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					frappe.call({
						method: 'frappe.client.get',
						args: {
							doctype: 'Translation Map',
							name: r.message[0].name
						},
						callback: function(mapResult) {
							if (mapResult.message && mapResult.message.field_mappings) {
								translationWidget.originalValues = {};
								mapResult.message.field_mappings.forEach(function(mapping) {
									if (mapping.translate && mapping.field_name) {
										let fieldValue = frm.doc[mapping.field_name];
										// Save current value (even if undefined/null)
										translationWidget.originalValues[mapping.field_name] = fieldValue;
									}
								});
							}
							if (callback) callback();
						},
						error: function() {
							if (callback) callback();
						}
					});
				} else {
					if (callback) callback();
				}
			},
			error: function() {
				if (callback) callback();
			}
		});
	}

	function applyTranslation(frm, translatedFields) {
		// Apply translated values without marking form as dirty
		// Store original dirty state
		let wasDirty = frm.dirty || false;
		
		// Apply translations
		Object.keys(translatedFields).forEach(function(fieldName) {
			if (frm.fields_dict[fieldName] && frm.doc.hasOwnProperty(fieldName)) {
				// Update the document value directly (bypasses change detection)
				frm.doc[fieldName] = translatedFields[fieldName];
			}
		});

		// Refresh all affected fields
		Object.keys(translatedFields).forEach(function(fieldName) {
			if (frm.fields_dict[fieldName]) {
				frm.refresh_field(fieldName);
			}
		});

		// Restore dirty state - don't mark as dirty if it wasn't dirty before
		if (!wasDirty) {
			frm.dirty = false;
		}
		
		translationWidget.currentLanguage = 'translated';
	}

	function restoreOriginalValues(frm, silent) {
		// Restore original values
		let wasDirty = frm.dirty || false;
		
		Object.keys(translationWidget.originalValues).forEach(function(fieldName) {
			if (frm.fields_dict[fieldName] && frm.doc.hasOwnProperty(fieldName)) {
				// Update the document value directly (bypasses change detection)
				frm.doc[fieldName] = translationWidget.originalValues[fieldName];
			}
		});

		// Refresh all affected fields
		Object.keys(translationWidget.originalValues).forEach(function(fieldName) {
			if (frm.fields_dict[fieldName]) {
				frm.refresh_field(fieldName);
			}
		});

		// Restore dirty state
		if (!silent && !wasDirty) {
			frm.dirty = false;
		}

		translationWidget.currentLanguage = 'original';
	}

	function updateButtonStates(frm, activeLang) {
		if (!frm.translation_widget) return;

		let $widget = frm.translation_widget;
		$widget.find('.translation-btn').removeClass('active');
		
		if (activeLang === 'original') {
			$widget.find('.translation-btn-original').addClass('active');
		} else {
			$widget.find('.translation-btn-target').addClass('active');
		}
	}

	function generateVersionId(doc) {
		// Generate version ID same as backend logic
		if (doc.modified) {
			let modifiedStr = doc.modified;
			if (typeof modifiedStr === 'object') {
				modifiedStr = modifiedStr.toISOString().replace(/[-:T\.]/g, '').substring(0, 14);
			}
			// Simple hash (frontend version)
			let hash = 0;
			let str = doc.doctype + '_' + doc.name + '_' + modifiedStr;
			for (let i = 0; i < str.length; i++) {
				let char = str.charCodeAt(i);
				hash = ((hash << 5) - hash) + char;
				hash = hash & hash; // Convert to 32bit integer
			}
			return doc.name + '_' + Math.abs(hash).toString(36).substring(0, 12);
		}
		return doc.name + '_' + Date.now().toString(36);
	}

})();
