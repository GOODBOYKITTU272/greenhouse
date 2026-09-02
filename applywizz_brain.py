import os
"""
ApplyWizz Brain — Answer Engine
=================================
4-Layer Funnel:
  1. BASIC CATCH       — deterministic standard fields (name, email, resume, etc.)
  2. FUZZY MATCHER     — predictable patterned questions using explicit CRM data
  3. GROQ AI ROUTER    — custom free-text questions only
  4. FINAL JUDGE       — validates every answer before storing

Golden Rule: NEVER invent candidate facts. Missing data → status = NEEDS_ATTENTION.
The CRM / candidate_profiles is the PRIMARY SOURCE OF TRUTH.
"""

import re
import json
import datetime
import requests
import time
import urllib.parse

try:
    import openai
except ImportError:
    openai = None

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = "inclusionai/ling-3.0-flash-fin:free"

# Questions the AI Router is BANNED from answering.
# These must only come from explicit CRM data.
STRUCTURED_ONLY_FIELDS = {
    "gender", "race", "race_ethnicity", "ethnicity", "veteran", "veteran_status",
    "disability", "disability_status", "sexual_orientation", "transgender",
    "visa", "sponsorship", "citizenship", "work_authorization",
    "salary", "salary_expectation", "county",
}

# ─────────────────────────────────────────────
# STATUS CODES
# ─────────────────────────────────────────────
STATUS_APPROVED        = "APPROVED"         # answer is confirmed + supported
STATUS_CORRECTED       = "CORRECTED"        # matched but mapped to ATS option
STATUS_DERIVED         = "DERIVED"          # deterministically derived
STATUS_AI_GENERATED    = "AI_GENERATED"     # came from Groq
STATUS_MEMORY          = "MEMORY"           # came from AI Memory Bank
STATUS_NEEDS_ATTENTION = "NEEDS_ATTENTION"  # missing data — human must fill


class ApplyWizzBrain:

    def __init__(self, job_url, candidate_profile, memory_bank=None, resume_text=None):
        self.job_url           = job_url
        self.candidate_profile = candidate_profile      # normalised CRM dict
        self.memory_bank       = memory_bank or {}      # {question_label: answer}
        self.resume_text       = resume_text or ""
        self.ai_questions_count = 0
        self.board_token, self.job_id = self._parse_url(job_url)

        # Groq client (OpenAI-compatible)
        if openai:
            self.client = openai.OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=OPENROUTER_API_KEY,
            )
        else:
            self.client = None

    # ──────────────────────────────────────────
    # URL PARSER
    # ──────────────────────────────────────────

    def _parse_url(self, url):
        """Resolve grnh.se shortlinks and extract (board_token, job_id)."""
        if "grnh.se" in url:
            try:
                url = requests.get(url, allow_redirects=True, timeout=10).url
            except Exception:
                pass

        for pattern in [
            r"boards\.greenhouse\.io/([^/]+)/jobs/(\d+)",
            r"job-boards\.greenhouse\.io/([^/]+)/jobs/(\d+)",
            r"for=([^&]+).*token=(\d+)",
        ]:
            m = re.search(pattern, url)
            if m:
                return m.group(1), m.group(2)

        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        job_id = (qs.get("gh_jid") or [""])[0]
        if job_id and job_id.isdigit():
            host_parts = parsed.netloc.split(".")
            board_token = host_parts[-2] if len(host_parts) >= 2 else host_parts[0]
            return board_token, job_id

        raise ValueError(f"Cannot extract board_token/job_id from: {url}")

    # ──────────────────────────────────────────
    # GREENHOUSE API
    # ──────────────────────────────────────────

    def fetch_job_details(self):
        # If the worker pre-fetched and cached the job schema, use it directly.
        # This means for 15 clients on the same job, Greenhouse is hit exactly once.
        if hasattr(self, '_prefetched_job_data') and self._prefetched_job_data:
            return self._prefetched_job_data

        url = (
            f"https://boards-api.greenhouse.io/v1/boards/"
            f"{self.board_token}/jobs/{self.job_id}?questions=true"
        )
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        return resp.json()

    # ATS Synonym Dictionary for strict matching without hallucination
    ATS_SYNONYMS = {
        "Male": ["man", "male (he/him)", "cisgender male", "male"],
        "Female": ["woman", "female (she/her)", "cisgender female", "female"],
        "Non-binary": ["non-binary", "nonbinary", "genderqueer", "gender non-conforming"],
        
        "Asian": ["east asian", "south asian", "asian / pacific islander", "asian (not hispanic or latino)"],
        "Black": ["african american", "black or african american", "black (not hispanic or latino)"],
        "White": ["caucasian", "white (not hispanic or latino)"],
        "Hispanic": ["hispanic or latino", "latino", "latina", "hispanic"],
        "Native American": ["american indian", "alaska native", "indigenous", "native hawaiian"],
        
        "Yes": ["true", "i agree", "i consent", "yes"],
        "No": ["false", "i disagree", "i do not consent", "no"],
    }

    # ──────────────────────────────────────────
    # OPTION MATCHERS
    # ──────────────────────────────────────────

    def _match_option(self, options, intent):
        """
        Find the ATS option using the ATS Synonym Dictionary.
        Returns (matched_label, True) or (intent, False) if no match found.
        """
        if not options or not intent:
            return intent, False

        intent_str = str(intent).strip()
        intent_lower = intent_str.lower()
        
        # 1. Expand intent using synonym dictionary
        synonyms = [intent_lower]
        for key, syn_list in self.ATS_SYNONYMS.items():
            if key.lower() == intent_lower or intent_lower in syn_list:
                synonyms.extend(syn_list)
                break
                
        # 2. Check ATS options against all valid synonyms
        for opt in options:
            label = str(opt.get("label", "")).strip()
            label_lower = label.lower()
            for syn in synonyms:
                # Exact match or substring match
                if syn == label_lower or syn in label_lower or label_lower in syn:
                    return label, True
                    
        return intent_str, False

    # ──────────────────────────────────────────
    # LAYER 1 — BASIC CATCH
    # ──────────────────────────────────────────

    def _layer1_basic_catch(self, field_name, options, label=""):
        """
        Map well-known Greenhouse field names directly to candidate profile.
        Returns a trace dict or None.
        """
        cp = self.candidate_profile
        phone_val = cp.get("phone")
        if not phone_val or phone_val == "+":
            import re
            if getattr(self, 'resume_text', None):
                # Look for xxx-xxx-xxxx or similar
                match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', self.resume_text)
                if match:
                    phone_val = match.group(0)

        mapping = {
            "first_name":       cp.get("first_name"),
            "last_name":        cp.get("last_name"),
            "email":            cp.get("email"),
            "phone":            phone_val,
            "resume":           cp.get("resume_url"),
            "cover_letter":     cp.get("cover_letter_url") or "",
            "linkedin_profile": cp.get("linkedin") or cp.get("linkedin_url") or "",
            "website":          cp.get("website") or cp.get("github_url") or "",
        }

        # 1. Try exact field name match
        if field_name in mapping:
            value = mapping[field_name]
            return self._trace(
                answer=value,
                source=f"candidate_profiles.{field_name}",
                resolver="BASIC_CATCH",
                status=STATUS_APPROVED if value else STATUS_NEEDS_ATTENTION,
            )

        # 2. Try label fuzzy match (for obfuscated field names like question_1234)
        lbl = label.lower()
        if "first name" in lbl:
            key = "first_name"
        elif "last name" in lbl:
            key = "last_name"
        elif "email" in lbl:
            key = "email"
        elif "phone" in lbl:
            key = "phone"
        elif "resume" in lbl or "cv" in lbl:
            key = "resume"
        elif "cover letter" in lbl:
            key = "cover_letter"
        elif "linkedin" in lbl:
            key = "linkedin_profile"
        elif "website" in lbl:
            key = "website"
        else:
            return None

        value = mapping[key]
        return self._trace(
            answer=value,
            source=f"candidate_profiles.{key}",
            resolver="BASIC_CATCH",
            status=STATUS_APPROVED if value else STATUS_NEEDS_ATTENTION,
        )

    # ──────────────────────────────────────────
    # LAYER 2 — FUZZY MATCHER
    # ──────────────────────────────────────────

    def _layer2_fuzzy_matcher(self, label, options, field_name):
        """
        Match predictable question patterns against explicit CRM fields.
        NEVER invents answers. Always reads from candidate_profile.
        """
        cp  = self.candidate_profile
        ll  = label.lower()

        # ── Work Authorization ──
        if any(w in ll for w in ["authorized to work", "legally authorized", "authorized work", "employment authorization"]):
            auth = cp.get("eligible_to_work_in_us", cp.get("authorized_to_work", True))
            intent = "Yes" if auth else "No"
            matched, _ = self._match_option(options, intent)
            return self._trace(matched, "candidate_profiles.eligible_to_work_in_us", "FUZZY_MATCHER", STATUS_APPROVED)

        # ── Sponsorship / Visa ──
        if any(w in ll for w in ["sponsorship", "sponsor", "visa"]):
            needs = cp.get("require_sponsorship", cp.get("sponsorship", False))
            if needs is None:
                needs = cp.get("visa_status") in ["F1", "OPT", "H1B", "TN"]
            intent = "Yes" if needs else "No"
            matched, _ = self._match_option(options, intent)
            return self._trace(matched, "candidate_profiles.require_sponsorship", "FUZZY_MATCHER", STATUS_APPROVED)

        # ── Relocation ──
        if any(w in ll for w in ["relocate", "relocation", "willing to move"]):
            willing = cp.get("willing_to_relocate", True)
            intent = "Yes" if willing else "No"
            matched, _ = self._match_option(options, intent)
            return self._trace(matched, "candidate_profiles.willing_to_relocate", "FUZZY_MATCHER", STATUS_APPROVED)

        # ── Onsite / Hybrid ──
        if any(w in ll for w in ["days in office", "onsite", "on-site", "hybrid"]):
            can = cp.get("can_work_onsite", True)
            intent = "Yes" if can else "No"
            matched, _ = self._match_option(options, intent)
            return self._trace(matched, "candidate_profiles.can_work_onsite", "FUZZY_MATCHER", STATUS_APPROVED)

        # ── GENDER (always use explicit CRM data — never infer or AI-guess) ──
        if any(w in ll for w in ["gender", "gender identity"]):
            gender_val = cp.get("gender")
            if gender_val:
                matched, found = self._match_option(options, gender_val)
                status = STATUS_CORRECTED if found else STATUS_APPROVED
                return self._trace(matched, "candidate_profiles.gender", "FUZZY_MATCHER", status)
            return self._eeoc_fallback(options, "gender")

        # ── RACE / ETHNICITY ──
        if any(w in ll for w in ["race", "ethnicity", "racial", "ethnic origin"]):
            race_val = cp.get("race") or cp.get("race_ethnicity")
            hispanic  = cp.get("is_hispanic_latino")

            # Try combined match (Asian + Not Hispanic) only if both values confirmed
            if race_val and hispanic is not None:
                combined = f"{race_val} (Not Hispanic or Latino)" if str(hispanic).lower() == "no" else f"{race_val} (Hispanic or Latino)"
                matched, found = self._match_option(options, combined)
                if found:
                    return self._trace(matched, "candidate_profiles.race+is_hispanic_latino", "FUZZY_MATCHER", STATUS_CORRECTED)

            if race_val:
                matched, found = self._match_option(options, race_val)
                status = STATUS_CORRECTED if found else STATUS_APPROVED
                return self._trace(matched, "candidate_profiles.race", "FUZZY_MATCHER", status)

            return self._eeoc_fallback(options, "race")

        # ── HISPANIC / LATINO ──
        if any(w in ll for w in ["hispanic", "latino", "latina"]):
            val = cp.get("is_hispanic_latino")
            if val:
                matched, _ = self._match_option(options, val)
                return self._trace(matched, "candidate_profiles.is_hispanic_latino", "FUZZY_MATCHER", STATUS_APPROVED)
            return self._eeoc_fallback(options, "is_hispanic_latino")

        # ── VETERAN STATUS ──
        if any(w in ll for w in ["veteran", "armed forces", "military service"]):
            val = cp.get("veteran") or cp.get("veteran_status")
            if val:
                matched, found = self._match_option(options, val)
                return self._trace(matched, "candidate_profiles.veteran_status", "FUZZY_MATCHER", STATUS_CORRECTED if found else STATUS_APPROVED)
            return self._eeoc_fallback(options, "veteran_status")

        # ── DISABILITY ──
        if any(w in ll for w in ["disability", "disabled", "chronic condition"]):
            val = cp.get("disability") or cp.get("disability_status")
            if val:
                matched, found = self._match_option(options, val)
                return self._trace(matched, "candidate_profiles.disability_status", "FUZZY_MATCHER", STATUS_CORRECTED if found else STATUS_APPROVED)
            return self._eeoc_fallback(options, "disability_status")

        # ── SEXUAL ORIENTATION (never infer from gender) ──
        if any(w in ll for w in ["sexual orientation", "sexual identity"]):
            val = cp.get("sexual_orientation")
            if val:
                matched, found = self._match_option(options, val)
                return self._trace(matched, "candidate_profiles.sexual_orientation", "FUZZY_MATCHER", STATUS_APPROVED)
            return self._eeoc_fallback(options, "sexual_orientation")

        # ── TRANSGENDER (never infer from gender) ──
        if any(w in ll for w in ["transgender", "trans identity"]):
            val = cp.get("transgender_status")
            if val:
                matched, found = self._match_option(options, val)
                return self._trace(matched, "candidate_profiles.transgender_status", "FUZZY_MATCHER", STATUS_APPROVED)
            return self._eeoc_fallback(options, "transgender_status")

        # ── SALARY ──
        if any(w in ll for w in ["salary", "compensation", "pay expectation", "desired pay"]):
            val = cp.get("salary_expectation", "")
            if val:
                if "hour" in ll:
                    val = self._normalize_salary(val, "hourly")
                elif "annual" in ll or "year" in ll:
                    val = self._normalize_salary(val, "annual")
                matched, _ = self._match_option(options, val)
                return self._trace(matched, "candidate_profiles.salary_expectation", "FUZZY_MATCHER", STATUS_APPROVED)
            return self._trace("", "candidate_profiles.salary_expectation", "FUZZY_MATCHER", STATUS_NEEDS_ATTENTION)

        # ── START DATE ──
        if any(w in ll for w in ["start date", "when can you start", "available to start"]):
            return self._trace("2 weeks", "deterministic_rule", "FUZZY_MATCHER", STATUS_DERIVED)

        # ── SECURITY CLEARANCE ──
        if "security clearance" in ll:
            matched, _ = self._match_option(options, "None")
            return self._trace(matched, "deterministic_rule", "FUZZY_MATCHER", STATUS_DERIVED)

        # ── FELONY / CRIMINAL ──
        if any(w in ll for w in ["felony", "criminal", "convicted"]):
            val = cp.get("convicted_of_felony", False)
            intent = "Yes" if val else "No"
            matched, _ = self._match_option(options, intent)
            return self._trace(matched, "candidate_profiles.convicted_of_felony", "FUZZY_MATCHER", STATUS_APPROVED)

        # ── BACKGROUND CHECK / DRUG TEST ──
        if "drug" in ll:
            val = cp.get("willing_drug_screen", True)
            intent = "Yes" if val else "No"
            matched, _ = self._match_option(options, intent)
            return self._trace(matched, "candidate_profiles.willing_drug_screen", "FUZZY_MATCHER", STATUS_APPROVED)
            
        if "background check" in ll:
            val = cp.get("willing_background_check", True)
            intent = "Yes" if val else "No"
            matched, _ = self._match_option(options, intent)
            return self._trace(matched, "candidate_profiles.willing_background_check", "FUZZY_MATCHER", STATUS_APPROVED)

        # ── LEGAL DOCS / PROOF OF IDENTITY ──
        if any(w in ll for w in ["legal documents", "proof of identity", "verify your identity"]):
            val = cp.get("can_provide_legal_docs", True)
            intent = "Yes" if val else "No"
            matched, _ = self._match_option(options, intent)
            return self._trace(matched, "candidate_profiles.can_provide_legal_docs", "FUZZY_MATCHER", STATUS_APPROVED)

        # ── DATE OF BIRTH ──
        if any(w in ll for w in ["date of birth", "dob", "birth date"]):
            val = cp.get("date_of_birth", "")
            return self._trace(val, "candidate_profiles.date_of_birth", "FUZZY_MATCHER", STATUS_APPROVED if val else STATUS_NEEDS_ATTENTION)

        # ── RELATIVES ──
        if any(w in ll for w in ["relatives", "family member", "related to"]):
            val = cp.get("has_relatives_in_company")
            if val is not None:
                intent = "Yes" if val else "No"
                matched, _ = self._match_option(options, intent)
                return self._trace(matched, "candidate_profiles.has_relatives_in_company", "FUZZY_MATCHER", STATUS_APPROVED)
            return self._trace("", "candidate_profiles.has_relatives_in_company", "FUZZY_MATCHER", STATUS_NEEDS_ATTENTION)

        # ── DISCHARGED / TERMINATED ──
        if any(w in ll for w in ["discharged", "terminated", "fired", "policy violation"]):
            val = cp.get("discharged_for_policy_violation", False)
            intent = "Yes" if val else "No"
            matched, _ = self._match_option(options, intent)
            return self._trace(matched, "candidate_profiles.discharged_for_policy_violation", "FUZZY_MATCHER", STATUS_APPROVED)

        # ── PENDING INVESTIGATION ──
        if "pending investigation" in ll:
            val = cp.get("pending_investigation", False)
            intent = "Yes" if val else "No"
            matched, _ = self._match_option(options, intent)
            return self._trace(matched, "candidate_profiles.pending_investigation", "FUZZY_MATCHER", STATUS_APPROVED)

        # ── WORKED BEFORE ──
        if any(w in ll for w in ["worked for", "previously employed", "former employee"]):
            return self._trace("No", "deterministic_rule", "FUZZY_MATCHER", STATUS_DERIVED)

        # ── SMS OPT-IN ──
        if any(w in ll for w in ["opt in", "text message", "sms consent"]):
            matched, _ = self._match_option(options, "Yes")
            return self._trace(matched, "deterministic_rule", "FUZZY_MATCHER", STATUS_DERIVED)

        # ── HOW DID YOU HEAR ──
        if any(w in ll for w in ["hear about", "how did you find", "referred by", "source"]):
            matched, _ = self._match_option(options, "Company Website")
            return self._trace(matched, "deterministic_rule", "FUZZY_MATCHER", STATUS_DERIVED)

        # ── ADDRESS FIELDS ──
        if any(w in ll for w in ["address line 1", "street address"]):
            val = cp.get("street_address") or cp.get("full_address", "")
            return self._trace(val, "candidate_profiles.street_address", "FUZZY_MATCHER", STATUS_APPROVED if val else STATUS_NEEDS_ATTENTION)

        if any(w in ll for w in ["address line 2", "apt", "suite"]):
            return self._trace("", "deterministic_rule", "FUZZY_MATCHER", STATUS_DERIVED)

        if "city" in ll and "state" not in ll:
            val = cp.get("city", "")
            return self._trace(val, "candidate_profiles.city", "FUZZY_MATCHER", STATUS_APPROVED if val else STATUS_NEEDS_ATTENTION)

        if "state" in ll and "united" not in ll:
            val = cp.get("state", "")
            matched, _ = self._match_option(options, val)
            return self._trace(matched, "candidate_profiles.state", "FUZZY_MATCHER", STATUS_APPROVED if val else STATUS_NEEDS_ATTENTION)

        if any(w in ll for w in ["zip", "postal code"]):
            val = cp.get("zip_code", "")
            return self._trace(val, "candidate_profiles.zip_code", "FUZZY_MATCHER", STATUS_APPROVED if val else STATUS_NEEDS_ATTENTION)

        if "county" in ll:
            return self._trace("", "deterministic_rule", "FUZZY_MATCHER", STATUS_DERIVED)

        if "country" in ll:
            val = cp.get("country", "United States")
            matched, _ = self._match_option(options, val)
            return self._trace(matched, "candidate_profiles.country", "FUZZY_MATCHER", STATUS_APPROVED)

        # ── SIGNATURE ──
        if any(w in ll for w in ["signature", "lie detector", "certify", "i certify"]):
            full = f"{cp.get('first_name', '')} {cp.get('last_name', '')}".strip()
            return self._trace(full, "candidate_profiles.full_name", "FUZZY_MATCHER", STATUS_DERIVED)

        # ── EDUCATION ──
        if any(w in ll for w in ["degree", "highest education", "highest level of education"]):
            val = cp.get("highest_education", "")
            matched, _ = self._match_option(options, val)
            return self._trace(matched, "candidate_profiles.highest_education", "FUZZY_MATCHER", STATUS_APPROVED if val else STATUS_NEEDS_ATTENTION)
            
        if any(w in ll for w in ["university", "college", "school", "institution"]):
            val = cp.get("university", "")
            return self._trace(val, "candidate_profiles.university", "FUZZY_MATCHER", STATUS_APPROVED if val else STATUS_NEEDS_ATTENTION)

        if "gpa" in ll:
            val = cp.get("gpa", "")
            return self._trace(val, "candidate_profiles.gpa", "FUZZY_MATCHER", STATUS_APPROVED if val else STATUS_NEEDS_ATTENTION)
            
        if any(w in ll for w in ["graduation year", "year of graduation", "class of"]):
            val = cp.get("graduation_year", "")
            matched, _ = self._match_option(options, val)
            return self._trace(matched, "candidate_profiles.graduation_year", "FUZZY_MATCHER", STATUS_APPROVED if val else STATUS_NEEDS_ATTENTION)
            
        if any(w in ll for w in ["major", "field of study", "main subject"]):
            val = cp.get("main_subject", "")
            return self._trace(val, "candidate_profiles.main_subject", "FUZZY_MATCHER", STATUS_APPROVED if val else STATUS_NEEDS_ATTENTION)

        # ── EXPERIENCE ──
        if any(w in ll for w in ["years of experience", "how many years"]):
            val = cp.get("experience_years", "")
            matched, _ = self._match_option(options, val)
            return self._trace(matched, "candidate_profiles.experience_years", "FUZZY_MATCHER", STATUS_APPROVED if val else STATUS_NEEDS_ATTENTION)

        return None

    def _eeoc_fallback(self, options, attribute):
        """
        STRICT STOP RULE:
        When candidate data is missing for an EEOC field,
        we NEVER guess and NEVER auto-pick 'Decline'.
        We instantly pause and flag as NEEDS_ATTENTION so a human can safely fill it.
        """
        return self._trace("", f"candidate_profiles.{attribute}", "FUZZY_MATCHER", STATUS_NEEDS_ATTENTION)

    def _normalize_salary(self, raw, mode):
        """Convert salary between hourly and annual. Returns same string if unparseable."""
        try:
            nums = re.findall(r"\d+", str(raw).replace(",", ""))
            if not nums:
                return raw
            val = float(nums[0])
            if mode == "hourly" and val > 500:
                return str(round(val / 2080))
            elif mode == "annual" and val < 500:
                return str(round(val * 2080))
            return str(int(val))
        except Exception:
            return raw

    # ──────────────────────────────────────────
    # LAYER 3 — GROQ AI ROUTER
    # ──────────────────────────────────────────

    def _layer3_ai_router(self, label, required, options):
        """
        Only for custom free-text questions.
        BANNED from structured / EEOC fields.
        """
        ll = label.lower()
        for banned_word in STRUCTURED_ONLY_FIELDS:
            if banned_word in ll:
                return self._trace("", "ai_ban_rule", "AI_ROUTER", STATUS_NEEDS_ATTENTION)

        if not required:
            return self._trace("", "deterministic_rule", "AI_ROUTER", STATUS_DERIVED)

        self.ai_questions_count += 1

        if not self.client:
            return self._trace("", "no_api_client", "AI_ROUTER", STATUS_NEEDS_ATTENTION)

        prompt = (
            f"You are helping fill out a job application. Use ONLY the candidate data below. "
            f"Do NOT invent facts, skills, employers, or experiences not mentioned.\n\n"
            f"Candidate Profile:\n{json.dumps(self.candidate_profile, indent=2)}\n\n"
            f"Resume:\n{self.resume_text[:3000]}\n\n"
            f"Question: {label}\n\n"
            f"Provide a concise, honest, professional answer using only the candidate's actual data. "
            f"If you cannot answer from the data provided, reply with exactly: NEEDS_ATTENTION"
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=OPENROUTER_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                )
                ai_answer = response.choices[0].message.content.strip()
                # Strip reasoning tokens
                ai_answer = re.sub(r"<think>.*?</think>", "", ai_answer, flags=re.DOTALL).strip()

                if "NEEDS_ATTENTION" in ai_answer or not ai_answer:
                    return self._trace("", "ai_refused", "AI_ROUTER", STATUS_NEEDS_ATTENTION)

                if options:
                    matched, found = self._match_option(options, ai_answer)
                    if found:
                        return self._trace(matched, "ai_generated+option_match", "AI_ROUTER", STATUS_AI_GENERATED)

                return self._trace(ai_answer, "ai_generated", "AI_ROUTER", STATUS_AI_GENERATED)

            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "too many requests" in err_str or "rate limit" in err_str:
                    if attempt < max_retries - 1:
                        time.sleep(3 ** attempt)  # Backoff: 1s, 3s, 9s
                        continue
                return self._trace("", f"ai_error:{e}", "AI_ROUTER", STATUS_NEEDS_ATTENTION)
        
        return self._trace("", "ai_max_retries_exceeded", "AI_ROUTER", STATUS_NEEDS_ATTENTION)

    # ──────────────────────────────────────────
    # LAYER 4 — FINAL JUDGE
    # ──────────────────────────────────────────

    def _layer4_final_judge(self, trace, label, options):
        """
        Validate every answer before storing.
        Never store hallucinations. Never store AI_PLACEHOLDER.
        """
        answer = trace.get("answer", "") or ""
        ll     = label.lower()

        # Always blank these
        if any(w in ll for w in ["address line 2", "address line 3", "county"]):
            trace["answer"] = ""
            trace["status"] = STATUS_DERIVED
            trace["source"] = "deterministic_rule"
            return trace

        # Cover letter must be URL or blank
        if "cover letter" in ll and answer and "http" not in answer.lower():
            trace["answer"] = ""
            trace["status"] = STATUS_DERIVED
            return trace

        # Block AWS hallucination on non-resume fields
        if "amazonaws.com" in answer.lower() and "resume" not in ll and "cv" not in ll:
            trace["answer"] = ""
            trace["status"] = STATUS_NEEDS_ATTENTION
            trace["source"] = "judge_hallucination_blocked"
            return trace

        # Never store placeholder strings
        if answer in ("AI_PLACEHOLDER", "AI_ANSWER_PENDING_API_KEY", "+", "None", "none"):
            trace["answer"] = ""
            trace["status"] = STATUS_NEEDS_ATTENTION
            return trace

        # If ATS options exist, answer must be a valid option
        if options and answer:
            labels = [str(o.get("label", "")) for o in options]
            if answer not in labels:
                matched, found = self._match_option(options, answer)
                if found:
                    trace["answer"] = matched
                    trace["status"] = STATUS_CORRECTED

        return trace

    # ──────────────────────────────────────────
    # TRACE HELPER
    # ──────────────────────────────────────────

    def _trace(self, answer, source, resolver, status):
        return {
            "answer":   answer if answer is not None else "",
            "source":   source,
            "resolver": resolver,
            "status":   status,
        }

    # ──────────────────────────────────────────
    # MEMORY BANK CHECK
    # ──────────────────────────────────────────

    def _check_memory_bank(self, label):
        val = self.memory_bank.get(label)
        if val and val not in ("AI_PLACEHOLDER", "AI_ANSWER_PENDING_API_KEY", "+", "None", "none", ""):
            return self._trace(val, "memory_bank", "MEMORY_BANK", STATUS_MEMORY)
        return None

    # ──────────────────────────────────────────
    # MAIN PROCESS
    # ──────────────────────────────────────────

    def process(self):
        job_data  = self.fetch_job_details()
        questions = job_data.get("questions") or []
        answer_map = []

        for q in questions:
            field_name = q.get("name", "")
            label      = q.get("label", "")
            required   = q.get("required", False)
            options    = q.get("values", [])

            # 1. Basic Catch
            trace = self._layer1_basic_catch(field_name, options, label)
            # 2. Memory Bank
            if trace is None:
                trace = self._check_memory_bank(label)
            # 3. Fuzzy Matcher
            if trace is None:
                trace = self._layer2_fuzzy_matcher(label, options, field_name)
            # 4. AI Router
            if trace is None:
                trace = self._layer3_ai_router(label, required, options)
            # Final Judge
            trace = self._layer4_final_judge(trace, label, options)

            answer_map.append({
                "field_name": field_name,
                "label":      label,
                "required":   required,
                "answer":     trace["answer"],
                "source":     trace["source"],
                "resolver":   trace["resolver"],
                "status":     trace["status"],
            })

        # ── EEOC / Demographic questions ──
        for dq in self._extract_demo_questions(job_data):
            label   = dq.get("label", "")
            options = dq.get("answer_options") or dq.get("values") or []

            trace = self._check_memory_bank(label)
            if trace is None:
                trace = self._layer2_fuzzy_matcher(label, options, "demographic_question")
            if trace is None:
                trace = self._eeoc_fallback(options, label)

            trace = self._layer4_final_judge(trace, label, options)

            answer_map.append({
                "field_name": "demographic_question",
                "label":      label,
                "required":   dq.get("required", False),
                "answer":     trace["answer"],
                "source":     trace["source"],
                "resolver":   trace["resolver"],
                "status":     trace["status"],
            })

        return {
            "job_url":            self.job_url,
            "board_token":        self.board_token,
            "job_id":             self.job_id,
            "job_title":          job_data.get("title", ""),
            "status":             "needs_review",
            "ai_questions_count": self.ai_questions_count,
            "answer_map":         answer_map,
        }

    def _extract_demo_questions(self, job_data):
        questions = []
        demo_obj = job_data.get("demographic_questions")
        if isinstance(demo_obj, dict):
            questions += demo_obj.get("questions", [])
        elif isinstance(demo_obj, list):
            questions += demo_obj

        comp_obj = job_data.get("compliance")
        if isinstance(comp_obj, list):
            for c in comp_obj:
                if isinstance(c, dict):
                    questions += c.get("questions", [])
        return questions
