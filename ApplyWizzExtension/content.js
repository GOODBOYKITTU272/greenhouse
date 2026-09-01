chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "FILL_FORM") {
    try {
        const data = request.data;
        const names = data.client.full_name.split(' ');
        const firstName = names[0];
        const lastName = names.slice(1).join(' ');
        const email = data.client.company_email;
        const phone = data.additional_information.primary_phone;
        const linkedin = data.additional_information.linked_in_url;

        // 1. Fill standard text fields by Exact ID
        function nativeTypeById(id, text) {
            const el = document.getElementById(id);
            if (el) {
                el.focus();
                el.select();
                document.execCommand('insertText', false, text);
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
            }
        }

        nativeTypeById('first_name', firstName);
        nativeTypeById('last_name', lastName);
        nativeTypeById('email', email);
        nativeTypeById('phone', phone);
        
        // 2. Fill Custom Text & Dropdown Fields dynamically by matching their Label text!
        function fillCustomField(labelText, answerText, isDropdown=false) {
            // Find the label element that contains our text
            const labels = Array.from(document.querySelectorAll('label, .asterisk'));
            const target = labels.find(l => l.innerText && l.innerText.toLowerCase().includes(labelText.toLowerCase()));
            
            if (target) {
                // Get the parent container of the question
                const container = target.closest('div');
                if (container) {
                    if (isDropdown) {
                        // React-Select dropdowns use an input with role="combobox"
                        const input = container.parentElement.querySelector('input[role="combobox"]');
                        if (input) {
                            input.focus();
                            document.execCommand('insertText', false, answerText);
                            setTimeout(() => {
                                input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
                            }, 100);
                        }
                    } else {
                        // Standard custom text field
                        const input = container.parentElement.querySelector('input[type="text"]');
                        if (input && input.id !== 'first_name') { // Prevent overwriting first_name!
                            input.focus();
                            input.select();
                            document.execCommand('insertText', false, answerText);
                        }
                    }
                }
            }
        }

        // Custom Text Fields
        fillCustomField('LinkedIn', linkedin, false);
        fillCustomField('salary expectations', '100k - 130k', false);
        fillCustomField('hear about this job', 'Company Website', false);

        // Custom Dropdowns
        fillCustomField('worked for our company before', 'No', true);
        fillCustomField('temporary or subject to expiration', 'Yes', true);
        fillCustomField('authorized to work in the United States', 'Yes', true);
        fillCustomField('receive text message updates', 'Yes', true);
        
        // Demographics
        fillCustomField('gender identity', 'I prefer not to answer', true);
        fillCustomField('racial/ethnic background', 'I prefer not to answer', true);
        fillCustomField('sexual orientation', 'I prefer not to answer', true);
        fillCustomField('identify as transgender', 'I prefer not to answer', true);
        fillCustomField('disability or chronic condition', 'No', true);
        fillCustomField('veteran or active member', 'I am not a protected veteran', true);

        sendResponse({ success: true });
    } catch (err) {
        console.error(err);
        sendResponse({ success: false, error: err.toString() });
    }
  }
  return true;
});
