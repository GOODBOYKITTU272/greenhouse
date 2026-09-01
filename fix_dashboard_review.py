with open('admin_dashboard.html', 'r') as f:
    text = f.read()

# Add orange badge for HUMAN_REVIEW_NEEDED in the dossier
old_badge = """                let badge = qObj.matched_by === 'ai_fallback' ? `<span style="background-color: #3b82f6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 10px; font-weight: bold;">ChatGPT</span>` : '';
                if (qObj.matched_by === 'memory_bank') badge = `<span style="background-color: #8b5cf6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 10px; font-weight: bold;">Memory Bank</span>`;"""

new_badge = """                let badge = qObj.matched_by === 'ai_fallback' ? `<span style="background-color: #3b82f6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 10px; font-weight: bold;">ChatGPT</span>` : '';
                if (qObj.matched_by === 'memory_bank') badge = `<span style="background-color: #8b5cf6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 10px; font-weight: bold;">Memory Bank</span>`;
                if (qObj.matched_by === 'needs_human_review') badge = `<span style="background-color: #f59e0b; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 10px; font-weight: bold;">⚠ You Must Select</span>`;"""

text = text.replace(old_badge, new_badge)

with open('admin_dashboard.html', 'w') as f:
    f.write(text)
print("Dashboard updated!")
