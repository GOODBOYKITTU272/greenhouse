import React, { useState, useEffect } from 'react';
import { supabase } from './supabaseClient';
import { Briefcase, CheckCircle, AlertCircle, Clock, X } from 'lucide-react';

// Greenhouse's own standardized field_name values for genuinely candidate-level
// fields — stable across every company's form, confirmed against applywizz_brain.py's
// _layer1_basic_catch mapping. Safe to edit ONCE and apply to every one of a
// candidate's pending jobs. Everything else (custom/free-text questions, and
// demographic_question, whose wording+meaning both vary per company even when
// they happen to look similar) stays edited per-job — see jobAnswers below.
const SHARED_FIELD_NAMES = new Set([
  'first_name', 'last_name', 'email', 'phone',
  'resume', 'cover_letter', 'linkedin_profile', 'website',
]);

export default function App() {
  const [allJobs, setAllJobs] = useState([]);
  const [stats, setStats] = useState({ pending: 0, needsReview: 0, approved: 0, completed: 0, failed: 0, total: 0 });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("NEEDS_REVIEW");

  // Modal state
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [candidateJobs, setCandidateJobs] = useState([]);
  // Structured, genuinely-candidate-level fields (name/email/phone/etc.) —
  // one shared value edited once, applied to every job that has that field.
  const [sharedAnswers, setSharedAnswers] = useState({});
  // Everything else, keyed by job.id -> { [label]: { ...question, displayAns } }.
  // NOT merged across jobs — two different jobs can share the exact same
  // custom question wording (e.g. "Why do you want to work here?") while
  // needing different honest answers, so editing one must never bleed into
  // another job for the same candidate.
  const [jobAnswers, setJobAnswers] = useState({});
  const [approveStatus, setApproveStatus] = useState(null); // {done, total, failed: [{id,url,error}]}

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  async function fetchData() {
    setLoading(true);
    try {
      const { data, error } = await supabase
        .from('job_queue')
        .select('*')
        .order('created_at', { ascending: false })
        // Temporary safety cap — no real pagination exists yet. Fine while
        // the queue is empty/small; once real daily volume flows in this
        // needs actual server-side pagination or per-status filtering
        // instead of raising the number.
        .limit(2000);

      if (error) throw error;
      
      setAllJobs(data || []);
      
      const st = { pending: 0, needsReview: 0, approved: 0, completed: 0, failed: 0, total: data.length };
      data.forEach(j => {
        if (j.status === 'PENDING' || j.status === 'PENDING_NEW') st.pending++;
        else if (j.status === 'NEEDS_REVIEW' || j.status === 'NEEDS_ATTENTION' || j.status === 'PENDING_REVIEW') st.needsReview++;
        else if (j.status === 'APPROVED') st.approved++;
        else if (j.status === 'SUBMITTED' || j.status === 'COMPLETED' || j.status === 'VERIFIED_APPLIED' || j.status === 'SUBMITTED_EMAIL_PENDING') st.completed++;
        else if (j.status === 'FAILED' || j.status === 'ERROR') st.failed++;
      });
      setStats(st);
    } catch (err) {
      console.error("Error fetching data:", err);
    }
    setLoading(false);
  }

  const handleReviewDossier = (applywizzId, clientName) => {
    const jobs = allJobs.filter(j => {
      if (j.applywizz_id !== applywizzId) return false;
      if (activeTab === 'PENDING') return j.status === 'PENDING' || j.status === 'PENDING_NEW';
      if (activeTab === 'FAILED') return j.status === 'FAILED' || j.status === 'ERROR';
      if (activeTab === 'NEEDS_REVIEW') return j.status === 'NEEDS_REVIEW' || j.status === 'NEEDS_ATTENTION' || j.status === 'PENDING_REVIEW';
      if (activeTab === 'COMPLETED') return j.status === 'SUBMITTED' || j.status === 'COMPLETED' || j.status === 'VERIFIED_APPLIED' || j.status === 'SUBMITTED_EMAIL_PENDING';
      return j.status === activeTab;
    });
    setCandidateJobs(jobs);
    setSelectedCandidate({ applywizz_id: applywizzId, client_name: clientName });

    // Split each job's questions: genuinely candidate-level structured fields
    // (name/email/phone/etc., identified by Greenhouse's own stable field_name,
    // not by label text) go into one shared, edit-once bucket. Everything else
    // stays scoped to its own job so a company-specific answer can never bleed
    // into a different job just because the question wording matches.
    const shared = {};
    const ja = {};
    jobs.forEach(job => {
      const perJob = {};
      if (job.application_data && job.application_data.answer_map) {
        job.application_data.answer_map.forEach(q => {
          const label = q.question_label || q.label;
          if (SHARED_FIELD_NAMES.has(q.field_name)) {
            if (!shared[q.field_name]) shared[q.field_name] = { ...q, label, displayAns: q.answer || '' };
          } else {
            perJob[label] = { ...q, displayAns: q.answer || '' };
          }
        });
      }
      ja[job.id] = perJob;
    });
    setSharedAnswers(shared);
    setJobAnswers(ja);
    setApproveStatus(null);
  };

  const handleSharedAnswerChange = (fieldName, newAns) => {
    setSharedAnswers(prev => ({
      ...prev,
      [fieldName]: { ...prev[fieldName], displayAns: newAns }
    }));
  };

  const handleAnswerChange = (jobId, label, newAns) => {
    setJobAnswers(prev => ({
      ...prev,
      [jobId]: { ...prev[jobId], [label]: { ...prev[jobId][label], displayAns: newAns } }
    }));
  };

  const approveAll = async () => {
    if (!selectedCandidate) return;
    const failed = [];
    let done = 0;
    for (const job of candidateJobs) {
      try {
        // Build this job's own updated answer_map: shared structured fields
        // (by field_name) apply the one candidate-level edit; everything else
        // uses only this job's own jobAnswers entry — never another job's.
        const answerMap = (job.application_data?.answer_map || []).map(q => {
          if (SHARED_FIELD_NAMES.has(q.field_name)) {
            const sharedEdit = sharedAnswers[q.field_name];
            return sharedEdit ? { ...q, answer: sharedEdit.displayAns } : q;
          }
          const label = q.question_label || q.label;
          const edited = jobAnswers[job.id]?.[label];
          return edited ? { ...q, answer: edited.displayAns } : q;
        });
        const application_data = { ...job.application_data, answer_map: answerMap };

        const { error } = await supabase
          .from('job_queue')
          .update({
            status: 'APPROVED',
            application_data,
          })
          .eq('id', job.id);

        if (error) throw error;
        done++;
      } catch (err) {
        console.error(`Failed to approve job [${job.id}] (${job.url}):`, err);
        failed.push({ id: job.id, url: job.url, error: err.message || String(err) });
      }
    }

    setApproveStatus({ done, total: candidateJobs.length, failed });
    fetchData();
    // Only auto-close the modal on a clean sweep — if anything failed, keep
    // it open with the failure list visible instead of silently dropping
    // back to the table with no indication of what actually went through.
    if (failed.length === 0) {
      setSelectedCandidate(null);
    }
  };

  // Group by candidate for the table
  const candidateStats = {};
  allJobs.filter(j => {
    if (activeTab === 'PENDING') return j.status === 'PENDING' || j.status === 'PENDING_NEW';
    if (activeTab === 'FAILED') return j.status === 'FAILED' || j.status === 'ERROR';
      if (activeTab === 'NEEDS_REVIEW') return j.status === 'NEEDS_REVIEW' || j.status === 'NEEDS_ATTENTION' || j.status === 'PENDING_REVIEW';
      if (activeTab === 'COMPLETED') return j.status === 'SUBMITTED' || j.status === 'COMPLETED' || j.status === 'VERIFIED_APPLIED' || j.status === 'SUBMITTED_EMAIL_PENDING';
    return j.status === activeTab;
  }).forEach(j => {
    if (!candidateStats[j.applywizz_id]) {
      candidateStats[j.applywizz_id] = { name: j.client_name, count: 0 };
    }
    candidateStats[j.applywizz_id].count++;
  });

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800">ApplyWizz Live Queue (React)</h1>
          <button onClick={fetchData} className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg font-medium shadow-sm transition-colors">
            {loading ? 'Refreshing...' : 'Refresh Data'}
          </button>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
          <div onClick={() => setActiveTab("PENDING")} className="cursor-pointer"><StatCard title="PENDING JOBS" value={stats.pending} color="text-gray-800" icon={<Clock className="w-5 h-5" />} /></div>
          <div onClick={() => setActiveTab("NEEDS_REVIEW")} className="cursor-pointer"><StatCard title="NEEDS REVIEW (AI DONE)" value={stats.needsReview} color="text-blue-500" icon={<AlertCircle className="w-5 h-5" />} /></div>
          <div onClick={() => setActiveTab("APPROVED")} className="cursor-pointer"><StatCard title="APPROVED (READY TO SUBMIT)" value={stats.approved} color="text-purple-500" icon={<CheckCircle className="w-5 h-5" />} /></div>
          <div onClick={() => setActiveTab("COMPLETED")} className="cursor-pointer"><StatCard title="COMPLETED" value={stats.completed} color="text-green-500" icon={<CheckCircle className="w-5 h-5" />} /></div>
          <div onClick={() => setActiveTab("FAILED")} className="cursor-pointer"><StatCard title="FAILED / ERRORS" value={stats.failed} color="text-red-500" icon={<X className="w-5 h-5" />} /></div>
          <StatCard title="TOTAL IN QUEUE" value={stats.total} color="text-blue-500" icon={<Briefcase className="w-5 h-5" />} />
        </div>

        {/* Candidate Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-xl font-bold text-gray-800 mb-6">Viewing: {activeTab}</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-gray-100 text-xs uppercase tracking-wider text-gray-500">
                  <th className="pb-4 font-semibold">Candidate</th>
                  <th className="pb-4 font-semibold">ApplyWizz ID</th>
                  <th className="pb-4 font-semibold">Jobs Pending Approval</th>
                  <th className="pb-4 font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {Object.entries(candidateStats).map(([id, info]) => (
                  <tr key={id} className="hover:bg-gray-50 transition-colors">
                    <td className="py-4 font-medium text-gray-800">{info.name || id}</td>
                    <td className="py-4 text-gray-500">{id}</td>
                    <td className="py-4 font-semibold text-blue-600">{info.count} Jobs</td>
                    <td className="py-4">
                      <button 
                        onClick={() => handleReviewDossier(id, info.name)}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                      >
                        {activeTab === 'COMPLETED' ? 'View Completed' : activeTab === 'FAILED' ? 'View Errors' : 'Review Dossier'}
                      </button>
                    </td>
                  </tr>
                ))}
                {Object.keys(candidateStats).length === 0 && (
                  <tr><td colSpan="4" className="py-8 text-center text-gray-500">No jobs need review right now.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Modal */}
        {selectedCandidate && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
              <div className="p-6 border-b border-gray-100 flex justify-between items-center bg-gray-50 rounded-t-xl">
                <div>
                  <h3 className="text-xl font-bold text-gray-800">Candidate Dossier: {selectedCandidate.client_name || selectedCandidate.applywizz_id}</h3>
                  <p className="text-sm font-semibold text-gray-800 mt-1">{candidateJobs.length} Jobs Pending Approval</p>
                </div>
                <button onClick={() => setSelectedCandidate(null)} className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-lg font-medium">Close</button>
              </div>
              <div className="p-6 overflow-y-auto flex-1">
                <h4 className="font-bold text-gray-800 mb-4 text-lg">
                  {activeTab === 'COMPLETED' ? 'Successfully Submitted Jobs' : 'All Application Answers to Review'}
                </h4>
                
                {activeTab === 'COMPLETED' ? (
                  <div className="space-y-6">
                    {candidateJobs.map((job, idx) => (
                      <div key={idx} className="bg-white border-2 border-green-200 rounded-xl p-5 shadow-sm">
                        {/* Job Header with URL & Status */}
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3 pb-3 border-b border-gray-100">
                          <div className="flex items-center gap-2">
                            <CheckCircle className="w-6 h-6 text-green-500 flex-shrink-0" />
                            <a href={job.url} target="_blank" rel="noopener noreferrer" className="font-bold text-blue-600 hover:underline text-base break-all">
                              {job.url}
                            </a>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="bg-green-100 text-green-800 text-xs font-bold px-3 py-1.5 rounded-full flex items-center gap-1">
                              ✓ VERIFIED_APPLIED
                            </span>
                          </div>
                        </div>

                        {/* Top Execution Metrics: Start Time, Duration & Cost — real data only, no invented fallbacks */}
                        <div className="mb-4 bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3">
                          <div className="grid grid-cols-3 gap-2 text-center pb-3 border-b border-gray-200">
                            <div className="border-r border-gray-200 pr-2">
                              <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Started At</p>
                              <p className="text-sm font-black text-gray-800">
                                {job.approved_answer_map?.started_at || "Not recorded"}
                              </p>
                              <span className="text-[10px] text-gray-400">Triggered</span>
                            </div>
                            <div className="border-r border-gray-200 pr-2">
                              <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Time Taken</p>
                              <p className="text-sm font-black text-emerald-700">
                                {job.approved_answer_map?.time_taken || "Not recorded"}
                              </p>
                              <span className="text-[10px] text-emerald-600 font-semibold">End-to-End</span>
                            </div>
                            <div>
                              <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Total Cost</p>
                              <p className="text-sm font-black text-blue-600">
                                {job.approved_answer_map?.cost || "Not recorded"}
                              </p>
                              <span className="text-[10px] text-blue-500 font-semibold">Proxy Bandwidth</span>
                            </div>
                          </div>
                        </div>

                        {/* Inbound Confirmation Email — only rendered when we actually captured the email body for THIS job */}
                        {job.approved_answer_map?.email && job.approved_answer_map?.email_body ? (
                          <div className="mb-4 bg-emerald-50 border-2 border-emerald-300 rounded-xl p-5 shadow-sm space-y-4">
                            <div className="flex items-start justify-between gap-2 border-b border-emerald-200 pb-3">
                              <div className="flex items-center gap-3">
                                <span className="text-3xl">📧</span>
                                <div>
                                  <h5 className="text-base font-black text-emerald-950">
                                    {job.approved_answer_map?.email_subject || "Confirmation email"}
                                  </h5>
                                  <p className="text-xs font-semibold text-emerald-800">
                                    From: <span className="font-mono bg-emerald-100 px-1.5 py-0.5 rounded text-emerald-900">{job.approved_answer_map?.email_from || "unknown sender"}</span>
                                  </p>
                                </div>
                              </div>
                              <span className="bg-emerald-600 text-white text-xs font-black px-3 py-1 rounded-full uppercase tracking-wider shadow-sm flex items-center gap-1">
                                ✓ Verified In Zoho
                              </span>
                            </div>

                            {/* Rendered Email Content Box — the actual captured body, not a canned template */}
                            <div className="bg-white rounded-xl p-4 text-sm text-gray-800 border border-emerald-200 shadow-inner font-sans space-y-3">
                              <div className="text-xs text-gray-500 border-b border-gray-100 pb-2 flex justify-between">
                                <span><strong>To:</strong> {job.approved_answer_map.email}</span>
                                <span className="font-mono text-gray-400">Mailbox: {selectedCandidate?.applywizz_id}</span>
                              </div>

                              <div className="text-gray-900 space-y-2.5 leading-relaxed text-sm pt-1 whitespace-pre-wrap">
                                {job.approved_answer_map?.email_body || "Email body not captured."}
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div className="mb-4 bg-yellow-50 border-2 border-yellow-300 rounded-xl p-4 text-sm text-yellow-800 font-semibold">
                            {job.approved_answer_map?.email
                              ? `⚠️ Confirmation matched by keyword search for ${job.approved_answer_map.email} in the Zoho inbox — the full email body was not captured for display.`
                              : "⚠️ No confirmation email captured for this job — status reflects the browser submission only."}
                          </div>
                        )}

                        <div className="bg-gray-50 p-4 rounded-lg text-sm text-gray-700 space-y-1.5">
                          <p className="font-bold text-gray-800 text-xs uppercase tracking-wider mb-2">Submitted Candidate Data:</p>
                          {job.approved_answer_map ? (
                            Object.entries(job.approved_answer_map).map(([k, v], i) => (
                              <div key={i} className="flex justify-between border-b border-gray-200 py-1 text-xs">
                                <span className="font-semibold text-gray-600 capitalize">{k.replace('_', ' ')}:</span>
                                <span className="text-gray-900 font-medium truncate max-w-xs">{String(v)}</span>
                              </div>
                            ))
                          ) : (
                            job.application_data?.answer_map?.map((ans, i) => (
                              <div key={i} className="flex justify-between border-b border-gray-200 py-1 text-xs">
                                <span className="font-semibold text-gray-600">{ans.question_label || ans.label}:</span>
                                <span className="text-gray-900 font-medium truncate max-w-xs">{ans.answer || 'Blank'}</span>
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-6">
                    {Object.keys(sharedAnswers).length > 0 && (
                      <div className="bg-blue-50 border-2 border-blue-200 rounded-xl p-4">
                        <p className="text-xs font-bold text-blue-800 uppercase tracking-wider mb-3">Candidate Info — one edit applies to all {candidateJobs.length} jobs</p>
                        <div className="space-y-3">
                          {Object.entries(sharedAnswers).map(([fieldName, q]) => (
                            <div key={fieldName} className="bg-white border border-blue-100 rounded-lg p-3">
                              <p className="text-sm font-bold text-gray-700 mb-2">Q: {q.label}</p>
                              <input
                                type="text"
                                value={q.displayAns}
                                onChange={(e) => handleSharedAnswerChange(fieldName, e.target.value)}
                                className={activeTab === 'NEEDS_REVIEW' ? "w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500" : "w-full p-2 border-transparent bg-gray-50 rounded text-gray-700"}
                                placeholder="Type answer here..."
                                disabled={activeTab !== 'NEEDS_REVIEW'}
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {candidateJobs.map(job => (
                      <div key={job.id} className="bg-white border-2 border-gray-100 rounded-xl p-4 shadow-sm">
                        <a href={job.url} target="_blank" rel="noopener noreferrer" className="font-bold text-blue-600 hover:underline text-sm break-all block mb-3 pb-2 border-b border-gray-100">
                          {job.url}
                        </a>
                        <div className="space-y-3">
                          {Object.entries(jobAnswers[job.id] || {}).map(([label, q], idx) => (
                            <div key={idx} className="bg-gray-50 border border-gray-100 rounded-lg p-3">
                              <p className="text-sm font-bold text-gray-700 mb-2">Q: {label}</p>
                              <input
                                type="text"
                                value={q.displayAns}
                                onChange={(e) => handleAnswerChange(job.id, label, e.target.value)}
                                className={activeTab === 'NEEDS_REVIEW' ? "w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500" : "w-full p-2 border-transparent bg-white rounded text-gray-700"}
                                placeholder="Type answer here..."
                                disabled={activeTab !== 'NEEDS_REVIEW'}
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {approveStatus && (
                  <div className={`mt-4 rounded-xl p-4 text-sm font-semibold ${approveStatus.failed.length === 0 ? 'bg-green-50 border-2 border-green-300 text-green-800' : 'bg-red-50 border-2 border-red-300 text-red-800'}`}>
                    {approveStatus.failed.length === 0 ? (
                      <p>✓ All {approveStatus.total} jobs approved successfully.</p>
                    ) : (
                      <div className="space-y-2">
                        <p>⚠️ {approveStatus.done} of {approveStatus.total} jobs approved — {approveStatus.failed.length} failed and were NOT approved:</p>
                        <ul className="list-disc list-inside space-y-1">
                          {approveStatus.failed.map(f => (
                            <li key={f.id} className="break-all">Job [{f.id}] {f.url} — {f.error}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {activeTab === 'NEEDS_REVIEW' && (
                <div className="p-6 border-t border-gray-100 bg-gray-50 rounded-b-xl flex justify-end">
                  <button onClick={approveAll} className="bg-green-500 hover:bg-green-600 text-white px-8 py-3 rounded-xl font-bold text-lg shadow-sm flex items-center gap-2 transition-all transform hover:scale-105">
                    <CheckCircle className="w-6 h-6" />
                    Approve All {candidateJobs.length} Jobs
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ title, value, color, icon }) {
  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col items-center justify-center">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-gray-400">{icon}</span>
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">{title}</h3>
      </div>
      <p className={`text-5xl font-black ${color}`}>{value}</p>
    </div>
  );
}
