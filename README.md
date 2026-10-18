# KSHAMATA-SETU (क्षमता-सेतू)
### Smart India Hackathon 2026 — National Finale MVP (SIH26135)
**Organization:** Government of Maharashtra (Maharashtra State Innovation Society)  
**Team:** HexaCore  
**Problem Statement:** Difficulties in tracking post-training employment outcomes, skill gaps, and the long-term impact of skilling initiatives.

---

## 1. Executive Summary & Problem Diagnosis

Current skilling programs (such as PMKVY, MSSDS, and NSDC portals) track **enrolment and certification** with high precision. However, a systemic "data black hole" occurs post-certification:
1. **Attrition & Churn:** Trainees frequently swap SIM cards or migrate, causing high follow-up attrition.
2. **Binary Illusion:** Analytics naively classify outcomes as a binary "placed vs. unplaced", ignoring whether data is self-reported, verified, or pending.
3. **No Diagnostic Feedback:** Trainees who drop out or fail to get placed never report **WHY** they were unplaced (e.g. shift timings, wage gap) or **WHAT** specific technical or soft skill deficits they experienced.
4. **Fraudulent Verification Claims:** Many systems claim live Aadhaar/EPFO verification without legal authorization.

**Kshamata-Setu** is an audit-safe, privacy-preserving, and explainable outcome validation engine designed specifically for state skill missions.

---

## 2. "What's Real vs. Simulated vs. Deferred" (Truth Boundary)

Judges value intellectual honesty and regulatory compliance over hollow claims. Below is our explicit truth matrix:

| Feature Area | Implementation in this MVP | Why It Is Architected This Way | Production Deployment Gate (Phase 2) |
| :--- | :--- | :--- | :--- |
| **Identity Verification** | **REAL** Working 6-Digit Phone OTP (Server-side TTL, single-use) | UIDAI AUA/KUA licensing cannot legally be obtained for hackathons. Phone OTP provides identical privacy-preserving authentication. | Plug in Aadhaar OTP via state nodal agency licensed AUA/KUA gateway. |
| **Data Privacy (PII)** | **REAL** Salted SHA-256 phone hashing; Non-reversible MSID generation; No phones in URLs/query params | Comply with DPDP Act (Digital Personal Data Protection Act 2023). Raw phone numbers are never stored or logged. | Hardware Security Module (HSM) key storage for salt rotation. |
| **Employer Validation** | **REAL** Audit-Locked Two-Sided Token Confirmation (HTTP 409 conflict on re-submission) | Eliminates single-sided self-reporting fraud without requiring enterprise ERP integrations. | Bulk employer webhooks & MahaSwayam company portal SSO. |
| **Explainable ML** | **REAL** Scikit-learn `LogisticRegression` with direct plain-English weight explainers & rule fallbacks | Deep neural networks or XGBoost are indefensible without years of historical data. Judges need to see *why* risk is calculated. | Calibrated Bayesian hierarchical models over millions of multi-year records. |
| **State Registries (EPFO, GSTIN, Aadhaar, SIDH)** | **SIMULATED / READY** "Integration Readiness Centre" dashboard with status badges & prerequisites | Live queries to EPFO or GSTIN require inter-ministerial MOUs. Claiming live access would be fraudulent. | File administrative data-sharing requests via Ministry of Labour & MSDE. |
| **Messaging Dispatches** | **REAL / FALLBACK** Twilio SDK with transparent mock logger fallback | Works out-of-the-box in localhost demo; immediately goes live once Twilio/CDAC credentials are added to `.env`. | Sanctioned Telecom DLT principal entity registration. |

---

## 3. Technology Stack & Reliability Rationale

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy ORM, Pydantic v2, SQLite (PostgreSQL-compatible with 1 env-var).
- **Frontend:** Plain HTML5, Vanilla JavaScript, Tailwind CSS (CDN), Chart.js (CDN). **Zero build-step (no Node.js/npm/webpack)** to guarantee 100% demo uptime without package conflicts. Served directly by FastAPI.
- **Security & Rate Limiting:** `slowapi` rate limiting on critical endpoints, SHA-256 cryptographic nonces, CORS middleware, JWT token foundations (`python-jose`).
- **Explainable AI:** `scikit-learn` (LogisticRegression with `liblinear` solver and plain-English weight translation).

---

## 4. Quick Start & Setup

### Prerequisites
- Python 3.10+ installed
- Git

### 1. Clone & Navigate
```bash
git clone <your-repo-url>
cd kshamata_setu
```

### 2. Set Up Virtual Environment & Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env if you wish to attach Twilio credentials or a PostgreSQL database URL
```

### 4. Seed Database & Start Server
```bash
python seed_data.py
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 5. Access the Web Interfaces
- **Interactive Demo Simulator:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Executive Analytics Dashboard:** [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)
- **Integration Readiness Centre:** [http://127.0.0.1:8000/integrations-ui](http://127.0.0.1:8000/integrations-ui)
- **Interactive OpenAPI/Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 6. Run Automated Test Suite
```bash
PYTHONPATH=. pytest tests/test_api.py -v
```

---

## 5. Judge Demonstration Script (5-Minute Live Presentation)

Follow this sequence during your live evaluation to hit every evaluation rubric:

### Minute 1: The Core Problem & Privacy-First Onboarding
1. Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Point out the **Prototype Truth Banner**.
2. **Step 1:** Enter a mobile number (e.g. `9876543210`) and click **"Request OTP"**.
   - *Say:* "We do not fake an Aadhaar login. We demonstrate an achievable, DPDP-compliant identity verification layer via real phone OTP."
3. Observe the 6-digit OTP in the prompt. Fill name, select course, and highlight the **two separate, unselected consent checkboxes** (Follow-up consent & Employer contact consent).
4. Click **"Onboard Trainee"**.
   - *Say:* "Notice the live inspector: The database never stores the phone number. It generates an immutable, salted Maharashtra Skill ID (`MSID-...`) and a cryptographic hash."

### Minute 2: Explainable Follow-Up Risk Engine
1. **Step 2:** Select the newly onboarded trainee and click **"Dispatch Follow-Up & Calculate Attrition Risk"**.
2. Point out the **Risk-of-Non-Response Score** and the **Explainable Factors**:
   - *Say:* "Instead of an unexplainable black-box, our risk engine explains every weight: baseline attrition (+0.20), rural connectivity penalty (+0.15), high-mobility sector (+0.10), and historical response trust bonus (-0.08)."
3. Mention that in production, this trigger connects to a background job scheduler (e.g., Celery/APScheduler) for automated 30/90/180-day milestone outreach.

### Minute 3: Capturing WHY and WHAT (The SIH PS Core)
1. **Step 3:** Select status as **"Seeking Employment (Not Placed)"**.
2. Choose a reason for non-placement (e.g. *"Shift timings incompatible with transit"*) and a skill deficit (e.g. *"Advanced Tally Prime GST reconciliation"*).
3. Click **"Record Response"**.
   - *Say:* "This directly solves problem statement SIH26135. Most systems only report that someone is unplaced. Kshamata-Setu records why they weren't hired and what skill they felt they lacked, feeding directly into state curriculum reform."
4. Now demonstrate an employed outcome: select **"Employed"**, enter **"Tata Motors Hub"**, and submit.
5. Point out the generated **"Employer Validation Token Link"**.

### Minute 4: Two-Sided Audit Lock (The Anti-Fraud Gate)
1. Click **"Open Employer Verification Portal"** (opens `employer-view`).
2. Click **"Confirm Placement (Tier E3)"**.
   - *Say:* "The evidence tier upgrades to E3 Employer Confirmed, and an immutable audit timestamp is locked."
3. Click **"Test Re-Submission (Verify 409 Lock)"** or try to click Reject.
   - *Say:* "Notice the system rejects it with an **HTTP 409 Conflict**. Once confirmed by an employer, the audit record cannot be tampered with or flipped."
4. Return to the simulator and click **"Withdraw Consent"** on Step 4. Then try to send a follow-up to show the **HTTP 403 Forbidden Gate**.

### Minute 5: Executive Intelligence & Integration Readiness
1. Navigate to **[http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)**:
   - Point out the **Evidence Tier Breakdown Chart**: Explain that **Tier E0 (Unresolved)** is strictly segregated from unemployed trainees.
   - Show the **Skill-Gap Diagnostics Panel**: Visualizing top non-placement reasons and missing skills broken down by sector.
   - Show the **Explainable ML Card**: Click **"Train / Calibrate ML"** to show actual learned logistic regression coefficients in plain English.
2. Navigate to **[http://127.0.0.1:8000/integrations-ui](http://127.0.0.1:8000/integrations-ui)**:
   - *Say:* "Here is our Integration Readiness Centre. Rather than falsely claiming unauthorized access to EPFO or Aadhaar, we present all 11 state and national registries with their exact licensing prerequisites and sandbox adapters."

---

## 6. Rehearsed Answers to Hard Judge Questions

### Q1: "Why didn't you integrate with real Aadhaar e-KYC or EPFO data?"
> **Answer:** "Statutory regulations prohibit any student team or prototype from querying live UIDAI or EPFO endpoints without a formal government MOU, SOC-2 audited hosting, and an AUA/KUA license. Claiming real access in a hackathon demo would be misleading. Instead, we architected our data model with compliant adapters, used real Phone-OTP verification for achievable identity, and provided two-sided employer confirmation tokens to verify employment without centralized registry dependencies."

### Q2: "Why use Logistic Regression instead of Deep Learning or XGBoost?"
> **Answer:** "For government policy and outcome attribution, explainability and auditability are non-negotiable legal requirements. An XGBoost model trained on small or synthetic datasets is impossible to defend and prone to severe overfitting. Scikit-learn Logistic Regression provides exact, transparent mathematical coefficients that we translate directly into human-readable policy statements: e.g., showing state officers exactly how rural geography and sector mobility impact response attrition."

### Q3: "Why not just use NSDC's existing reports or LMIS portals?"
> **Answer:** "NSDC's LMIS and state dashboards generate aggregate, periodic batch reports based on training provider self-declarations. They suffer from three systemic flaws:
> 1. Training providers have an inherent conflict of interest to inflate placement rates.
> 2. The data is aggregate rather than trainee-level, so dropouts are permanently lost to follow-up.
> 3. They record binary certification metrics without capturing post-placement wage progression, retention at 90/180 days, or qualitative skill deficits for unplaced candidates. Kshamata-Setu provides continuous, evidence-tiered verification directly from the trainee and employer."

### Q4: "How does the system handle trainees who change phone numbers?"
> **Answer:** "By decoupling identity from raw phone numbers through salted MSIDs and multi-channel fallback (SMS, WhatsApp, and training provider contact updating). If a trainee updates their number, their MSID remains constant and historical follow-up records retain continuity."

---

## 7. Deployment Readiness Notes

### Render.com Free-Tier Deployment
1. The repository includes a ready-to-use `render.yaml` Blueprint specification.
2. Ensure this code is pushed to your GitHub repository.
3. In Render, select **New + -> Blueprint** and connect the repository.
4. **Important Deployment Details:**
   - **Cold Start Notice:** Render free-tier instances spin down after 15 minutes of inactivity. The first request may take 30–60 seconds to respond. **Always ping the live URL 5 minutes before your evaluation**, and run localhost as your primary demo with the cloud URL as backup.
   - **SQLite Ephemerality:** Render free-tier disks are ephemeral; restarting or redeploying re-runs `seed_data.py` to restore the 40 clean demo trainees. If persistent multi-day data is required for production, simply set `DATABASE_URL` in Render environment variables to a free Supabase or Neon PostgreSQL connection string (`postgresql://...`) — **zero code changes are required**.
   - **JWT Secret:** In production, replace `JWT_SECRET` with a secure 64-character random string.

---

## 8. Verified Failure Modes & Test Suite

Our automated test suite (`tests/test_api.py`) verifies all non-happy paths:
1. **Wrong OTP:** `POST /trainee/onboard` with invalid OTP returns `401 Unauthorized`.
2. **Consent Withdrawal Gate:** `POST /followup/send/{id}` on a withdrawn trainee returns `403 Forbidden`.
3. **Employer Audit Tampering:** Resubmitting a confirmed employer verification returns `409 Conflict`.
4. **Rate Limiting:** Exceeding 10 onboarding requests per minute returns `429 Too Many Requests`.
5. **Low Data ML Handling:** Training ML with insufficient samples gracefully returns `{"status": "insufficient_data"}` without crashing.

---
**Team HexaCore** | Smart India Hackathon 2026 | National Finale Showcase
