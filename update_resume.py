import sys
from supabase import create_client

SUPABASE_URL = 'https://lnlvxsskkxeidlqgqqrj.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo'
db = create_client(SUPABASE_URL, SUPABASE_KEY)

resume_text = """SRUJAN MARYALA
Delray Beach, FL (Open to Relocate) | +1(561) 920-7873 | maryalasrujan0@gmail.com
PROFESSIONAL SUMMARY
AML Analyst with 2+ years of experience in transaction monitoring, alert investigation, case management, and SAR reporting across banking and fintech environments. Experienced in the end-to-end AML lifecycle, including investigation and regulatory reporting, with strong expertise in KYC, CDD, EDD, sanctions screening, and OFAC compliance. Proficient in SQL, Python, and Excel for transaction analysis and anomaly detection, supporting accurate alert disposition and compliance with BSA/AML regulations.
TECHNICAL SKILLS
AML & Financial Crime: AML, Transaction Monitoring, Alert Review, Alert Investigation, Alert Disposition, Case Investigation, Case Management, SAR, Fraud Detection, Sanctions Screening, OFAC, Watchlist Screening
KYC & Due Diligence: KYC, CDD, EDD, Client Onboarding, Customer Risk Profiling, PEP Screening, Identity Verification
Risk & Compliance: Risk Assessment, Risk-Based Approach, Compliance Monitoring, BSA/AML, Regulatory Compliance, Internal Controls, Compliance Audits, Escalation Handling
Data Analysis & Reporting: SQL, Python, Transaction Analysis, Anomaly Detection, Data Validation, Investigative Analysis, Regulatory Reporting
Tools & Technologies: Microsoft Excel, Power BI, Jupyter Notebook
Databases: MySQL, PostgreSQL
PROFESSIONAL EXPERIENCE
AML Analyst May 2023 - Jun 2024
Wissen Infotech | Hyderabad, India
• Investigated transactional data using SQL and Excel to perform alert review and transaction monitoring, uncovering suspicious patterns and improving detection accuracy by 28% in high-risk accounts.
• Led alert disposition by conducting detailed case investigations and documenting findings in structured formats, which reduced false positives by 22% and improved investigation accuracy.
• Executed KYC, CDD, and EDD processes by validating customer data and performing PEP and watchlist screening, ensuring regulatory compliance and lowering onboarding risk exposure.
• Leveraged Python (Pandas) with SQL to analyze transaction flows and detect anomalies, strengthening fraud detection capabilities and enabling early identification of unusual behavior.
• Produced SAR-ready reports by consolidating transaction trails and investigative insights, improving reporting quality and meeting regulatory reporting standards.
• Performed sanctions and OFAC screening on customer profiles and transactions, identifying potential matches and escalating high-risk cases through defined compliance workflows.
• Strengthened audit readiness by maintaining accurate case documentation and audit trails in Excel and internal systems, improving traceability during compliance reviews.
• Optimized monitoring effectiveness by analyzing historical alert data using SQL and supporting rule enhancements, which reduced redundant alerts and improved risk-based detection.
Financial Crime Analyst Aug 2022 - Mar 2023
HDFC Bank | India
• Analyzed transaction alerts using SQL and Microsoft Excel within transaction monitoring workflows, identifying suspicious fund movements and improving detection accuracy by 26% across retail accounts.
• Strengthened alert disposition by conducting detailed case investigations and documenting risk findings, which reduced false positives by 23% and enhanced case resolution efficiency.
• Executed KYC, CDD, and EDD checks by validating customer identity and screening risk indicators, improving customer risk classification and reducing financial crime exposure.
• Performed sanctions screening and OFAC/watchlist checks on customer profiles and transactions, identifying highrisk matches and ensuring adherence to regulatory compliance requirements.
• Leveraged SQL and Excel to analyze transaction patterns and detect anomalies, uncovering irregular activity that improved fraud detection efficiency by 27%.
• Produced SAR-ready case summaries by compiling transaction trails and investigative insights, improving reporting accuracy and supporting regulatory reporting standards.
• Applied a risk-based approach to prioritize high-risk alerts and escalate critical cases through defined escalation handling workflows, improving case resolution turnaround time.
• Maintained accurate case documentation and audit trails using Excel and internal systems, ensuring traceability and achieving 100% audit compliance during internal reviews. 
Risk & Compliance Analyst Aug 2021 - Jul 2022
KreditBee | India
• Assessed customer profiles using KYC, CDD, and risk assessment frameworks with SQL and Excel, identifying high-risk applicants and reducing onboarding fraud by 21%.
• Strengthened risk classification by performing credit and fraud risk analysis on transactional data using SQL, which improved decision accuracy and reduced default exposure.
• Monitored transactional activity through transaction monitoring workflows and Excel, identifying suspicious patterns and enhancing fraud detection across digital lending operations.
• Improved regulatory adherence by implementing compliance monitoring aligned with BSA/AML standards, validating onboarding data and reducing compliance gaps by 18%.
• Generated SQL-based risk and fraud reports to track key metrics and anomalies, enabling data-driven insights that increased investigation efficiency by 24%.
• Ensured audit readiness by maintaining validated records and performing data validation using Excel, improving data accuracy and supporting internal compliance audits.
"""

r = db.table('candidate_profiles').update({'resume_text': resume_text}).eq('applywizz_id', 'AWL-25629').execute()
print("Resume text updated successfully in the database!")
