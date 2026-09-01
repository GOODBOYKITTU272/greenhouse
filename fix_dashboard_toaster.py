with open('admin_dashboard.html', 'r') as f:
    text = f.read()

old_approve_end = """        // 3. Mark all their PENDING/NEEDS_REVIEW jobs as APPROVED
        const { error } = await supabaseClient.from('job_queue')
            .update({ status: 'APPROVED' })
            .eq('applywizz_id', applywizzId)
            .eq('status', 'NEEDS_REVIEW');
            
        if (error) {
            alert('Failed to approve candidate jobs: ' + error.message);
        } else {
            closeModal();
            fetchStats();
            showDetails('NEEDS_REVIEW');
        }
    }"""

new_approve_end = """        // 3. Get the list of jobs being approved so we can show them
        const candidateJobs = allJobs.filter(j => j.applywizz_id === applywizzId && j.status === 'NEEDS_REVIEW');
        
        // 4. Mark all their PENDING/NEEDS_REVIEW jobs as APPROVED
        const { error } = await supabaseClient.from('job_queue')
            .update({ status: 'APPROVED' })
            .eq('applywizz_id', applywizzId)
            .eq('status', 'NEEDS_REVIEW');
            
        if (error) {
            alert('Failed to approve candidate jobs: ' + error.message);
        } else {
            // SHOW SUCCESS TOASTER / PAGE IN THE MODAL
            const content = document.getElementById('modal-content');
            document.getElementById('modal-header').innerText = `✅ Candidate Approved!`;
            
            let jobLinksHtml = candidateJobs.map(j => 
                `<div style="padding: 10px; border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 8px; background: #f8fafc; font-size: 13px;">
                    <a href="${j.url}" target="_blank" style="color: #3b82f6; text-decoration: none; word-break: break-all;">${j.url}</a>
                </div>`
            ).join('');

            content.innerHTML = `
                <div style="text-align: center; padding: 30px 10px;">
                    <div style="font-size: 50px; margin-bottom: 20px;">🚀</div>
                    <h2 style="color: #10b981; margin-bottom: 10px;">Successfully Approved!</h2>
                    <p style="font-size: 16px; color: #475569; margin-bottom: 30px;">
                        The Muscle Worker will now automatically submit these ${candidateJobs.length} applications in the background.
                    </p>
                    <div style="text-align: left; max-width: 500px; margin: 0 auto;">
                        <h4 style="margin-bottom: 10px; color: #1e293b;">Jobs Queued for Submission:</h4>
                        ${jobLinksHtml}
                    </div>
                    
                    <button onclick="closeModal(); fetchStats(); showDetails('NEEDS_REVIEW');" style="margin-top: 40px; background-color: #3b82f6; color: white; font-weight: bold; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px;">
                        Return to Dashboard
                    </button>
                </div>
            `;
        }
    }"""

text = text.replace(old_approve_end, new_approve_end)

with open('admin_dashboard.html', 'w') as f:
    f.write(text)
print("Success view added to Dashboard!")
