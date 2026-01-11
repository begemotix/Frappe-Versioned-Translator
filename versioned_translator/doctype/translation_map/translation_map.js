// Copyright (c) 2025, Your Name and contributors
// For license information, please see license.txt

frappe.ui.form.on('Translation Map', {
	refresh: function(frm) {
		// Add custom button 'Get Fields' to toolbar
		if (frm.doc.doctype_name) {
			frm.add_custom_button(__('Get Fields'), function() {
				get_fields_for_translation(frm);
			}, __('Actions'));
		}

		// Also handle the button field click (if button field is used)
		if (frm.fields_dict.auto_map_fields) {
			frm.fields_dict.auto_map_fields.$input.on('click', function() {
				get_fields_for_translation(frm);
			});
		}
	}
});

function get_fields_for_translation(frm) {
	if (!frm.doc.doctype_name) {
		frappe.msgprint(__('Please select a DocType first.'));
		return;
	}

	// Show loading indicator
	frappe.show_alert({
		message: __('Loading fields...'),
		indicator: 'blue'
	}, 2);

	// Call server method
	frappe.call({
		method: 'versioned_translator.logic.get_fields_for_translation',
		args: {
			doctype_name: frm.doc.doctype_name
		},
		callback: function(r) {
			if (r.message && r.message.length > 0) {
				// Clear existing field mappings
				frm.clear_table('field_mappings');
				
				// Add fields to child table
				r.message.forEach(function(field) {
					let row = frm.add_child('field_mappings');
					row.parent_doctype = frm.doc.doctype_name;
					row.field_name = field.field_name;
					row.field_label = field.field_label;
					row.field_type = field.field_type;
					row.translate = 1; // Default: translate enabled
				});
				
				frm.refresh_field('field_mappings');
				frappe.show_alert({
					message: __('{0} fields loaded successfully', [r.message.length]),
					indicator: 'green'
				}, 5);
			} else {
				frappe.msgprint(__('No translatable fields found for this DocType.'));
			}
		},
		error: function(r) {
			frappe.msgprint({
				title: __('Error'),
				message: __('Error loading fields: {0}', [r.message || 'Unknown error']),
				indicator: 'red'
			});
		}
	});
}
