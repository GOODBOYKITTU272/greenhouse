with open('applywizz_brain.py', 'r') as f:
    text = f.read()

# The bug: "male" appears inside "female", causing wrong match
# Fix: check for EXACT match first, then prefix match, never substring
old_matcher = """        # Find the best matching dropdown option
        intent_lower = str(intent).lower()
        for opt in options:
            opt_label = str(opt.get('label', '')).lower()
            if intent_lower in opt_label or opt_label in intent_lower:
                return opt.get('label')

        # Fallback: yes/no intent on dropdown
        if intent_lower in ['yes', 'true']:
            for opt in options:
                if 'yes' in str(opt.get('label', '')).lower():
                    return opt.get('label')
        if intent_lower in ['no', 'false']:
            for opt in options:
                if 'no' in str(opt.get('label', '')).lower():
                    return opt.get('label')

        return None"""

new_matcher = """        # Find the best matching dropdown option
        intent_lower = str(intent).lower()

        # Pass 1: EXACT match (e.g. intent="Male" matches option "Male" only)
        for opt in options:
            opt_label = str(opt.get('label', '')).lower()
            if intent_lower == opt_label:
                return opt.get('label')

        # Pass 2: Intent STARTS WITH the option label (e.g. "I am not a protected veteran" matches "I am not")
        for opt in options:
            opt_label = str(opt.get('label', '')).lower()
            if opt_label and intent_lower.startswith(opt_label):
                return opt.get('label')

        # Pass 3: Option label starts with intent (careful: avoid "male" matching "female")
        for opt in options:
            opt_label = str(opt.get('label', '')).lower()
            # Only match if intent is at least 4 chars to avoid false positives
            if len(intent_lower) >= 4 and opt_label.startswith(intent_lower):
                return opt.get('label')

        # Pass 4: Yes/No intent on dropdown
        if intent_lower in ['yes', 'true']:
            for opt in options:
                ol = str(opt.get('label', '')).lower()
                if ol in ['yes', 'yes, i am', 'yes, i do']:
                    return opt.get('label')
            for opt in options:
                if str(opt.get('label', '')).lower().startswith('yes'):
                    return opt.get('label')
        if intent_lower in ['no', 'false']:
            for opt in options:
                ol = str(opt.get('label', '')).lower()
                if ol in ['no', 'no, i am not', 'no, i do not']:
                    return opt.get('label')
            for opt in options:
                if str(opt.get('label', '')).lower().startswith('no'):
                    return opt.get('label')

        return None"""

text = text.replace(old_matcher, new_matcher)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("Gender matcher fixed!")
