import json
import requests

candidate = {
    "first_name": "Yakub",
    "last_name": "Ali Mohammed",
    "email": "yakubali.mohammed@applywizard.ai",
    "phone": "1234567890",
    "linkedin": "https://www.linkedin.com/in/yakub-mohammed"
}

def match_dropdown_option(question_label, options):
    label_lower = question_label.lower()
    
    # Helper to find closest exact text match in available options
    def find_match(keywords):
        for opt in options:
            opt_lower = opt.lower()
            for kw in keywords:
                if kw in opt_lower:
                    return opt
        return None

    # ApplyWizz Business Rules matched against the exact API options
    if "veteran" in label_lower:
        return find_match(["not a protected veteran", "no", "decline", "don't wish"])
    if "disability" in label_lower:
        return find_match(["no", "decline", "don't wish"])
    if "gender" in label_lower or "sex" in label_lower or "race" in label_lower or "transgender" in label_lower:
        return find_match(["prefer not to", "decline", "don't wish"])
    if "sponsorship" in label_lower or "temporary" in label_lower or "expiration" in label_lower:
        return find_match(["yes"])
    if "authorized" in label_lower:
        return find_match(["yes"])
    if "text message" in label_lower or "sms" in label_lower:
        return find_match(["yes"])
        
    return "UNKNOWN - Requires Human/AI Input"

def main():
    url = "https://boards-api.greenhouse.io/v1/boards/lendingtree/jobs/8155569?questions=true"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    
    print("Fetching Job Schema from Greenhouse API...")
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching API: {response.status_code}")
        return
        
    data = response.json()
    
    # Combine all questions (standard, compliance, demographic)
    all_questions = data.get("questions", [])
    for eeoc in (data.get("compliance") or []):
        all_questions.extend(eeoc.get("questions", []))
        
    if "demographic_questions" in data:
        all_questions.extend((data.get("demographic_questions") or {}).get("questions", []))
        
    frontend_map = []
    
    for q in all_questions:
        label = q.get("label", "Unknown Question")
        fields = q.get("fields", [])
        if not fields: continue
            
        field = fields[0]
        field_type = field.get("type", "unknown")
        
        # Extract options if it's a dropdown
        options = []
        if "values" in field:
            options = [v.get("label") for v in field["values"]]
        elif "answer_options" in field: 
            options = [v.get("label") for v in field["answer_options"]]
            
        proposed_answer = ""
        
        # Map Text fields
        if field_type == "input_text" or field_type == "textarea":
            lbl_lower = label.lower()
            if "first name" in lbl_lower: proposed_answer = candidate["first_name"]
            elif "last name" in lbl_lower: proposed_answer = candidate["last_name"]
            elif "email" in lbl_lower: proposed_answer = candidate["email"]
            elif "phone" in lbl_lower: proposed_answer = candidate["phone"]
            elif "linkedin" in lbl_lower: proposed_answer = candidate["linkedin"]
            elif "location" in lbl_lower: proposed_answer = "San Francisco, CA"
            else: proposed_answer = "UNKNOWN - Requires Human/AI Input"
            
        # Map Dropdowns using the exact API wording!
        elif field_type in ["multi_value_single_select", "multi_value_multi_select"]:
            proposed_answer = match_dropdown_option(label, options)
            
        frontend_map.append({
            "Question": label,
            "Available_Options": options if options else "N/A (Text Field)",
            "Proposed_Answer": proposed_answer
        })
        
    # Write to JSON file
    with open("frontend_mapping.json", "w") as f:
        json.dump(frontend_map, f, indent=4)
        
    print("\n✅ Successfully extracted and mapped the questions!")
    print("I have saved the results to 'frontend_mapping.json'.\n")
    print("==================================================")
    print("FRONTEND DISPLAY PREVIEW:")
    print("==================================================")
    
    for item in frontend_map:
        print(f"\n❓ Question: {item['Question']}")
        if item['Available_Options'] != "N/A (Text Field)":
            print(f"   (Options: {', '.join(item['Available_Options'])})")
        print(f"👉 Proposed Answer: {item['Proposed_Answer']}")

if __name__ == "__main__":
    main()
