with open('admin_dashboard.html', 'r') as f:
    text = f.read()

old_code = """                let ans = qObj.answer || '';
                let badge = qObj.matched_by === 'ai_fallback' ? `<span style="background-color: #3b82f6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 10px; font-weight: bold;">ChatGPT</span>` : '';
                if (qObj.matched_by === 'memory_bank') badge = `<span style="background-color: #8b5cf6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 10px; font-weight: bold;">Memory Bank</span>`;
                if (qObj.matched_by === 'needs_human_review') badge = `<span style="background-color: #f59e0b; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 10px; font-weight: bold;">⚠ You Must Select</span>`;
                
                content.innerHTML += `
                    <div class="qa-item" style="margin-bottom: 15px;">
                        <div class="qa-q" style="font-weight: bold; margin-bottom: 4px;">Q: ${qLabel} ${badge}</div>
                        <div>
                            <input type="text" id="edit-ans-${idx}" value="${ans.replace(/"/g, '&quot;')}" style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-family: inherit;">
                        </div>
                    </div>
                `;"""


new_code = """                let ans = qObj.answer || '';
                
                // Format resume filename instead of long S3 URL for display
                let displayAns = ans;
                let isResume = (qLabel.includes('Resume') || qLabel.includes('CV'));
                if (isResume && ans.startsWith('http')) {
                    try {
                        let path = new URL(ans).pathname;
                        displayAns = decodeURIComponent(path.split('/').pop());
                    } catch(e) {
                        displayAns = ans.split('?')[0].split('/').pop();
                    }
                }
                
                let badge = qObj.matched_by === 'ai_fallback' ? `<span style="background-color: #3b82f6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 10px; font-weight: bold;">ChatGPT</span>` : '';
                if (qObj.matched_by === 'memory_bank') badge = `<span style="background-color: #8b5cf6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 10px; font-weight: bold;">Memory Bank</span>`;
                if (qObj.matched_by === 'needs_human_review') badge = `<span style="background-color: #f59e0b; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 10px; font-weight: bold;">⚠ You Must Select</span>`;
                
                content.innerHTML += `
                    <div class="qa-item" style="margin-bottom: 15px;">
                        <div class="qa-q" style="font-weight: bold; margin-bottom: 4px;">Q: ${qLabel} ${badge}</div>
                        <div>
                            ${isResume 
                                ? `<input type="hidden" id="edit-ans-${idx}" value="${ans.replace(/"/g, '&quot;')}">
                                   <input type="text" value="📄 ${displayAns.replace(/"/g, '&quot;')}" disabled style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-family: inherit; background-color: #f3f4f6; color: #666;">` 
                                : `<input type="text" id="edit-ans-${idx}" value="${ans.replace(/"/g, '&quot;')}" style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-family: inherit;">`
                            }
                        </div>
                    </div>
                `;"""

text = text.replace(old_code, new_code)

with open('admin_dashboard.html', 'w') as f:
    f.write(text)
print("Dashboard resume display fixed!")
