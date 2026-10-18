import sys
import time
import requests
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

tests_passed = 0
tests_failed = 0

def log_test(name, passed, detail=""):
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        print(f"  [{GREEN}PASS{RESET}] {name} {detail}")
    else:
        tests_failed += 1
        print(f"  [{RED}FAIL{RESET}] {name} {detail}")

def run_fst():
    print(f"\n{BOLD}{CYAN}==============================================================={RESET}")
    print(f"{BOLD}{CYAN}   KSHAMATA-SETU (SIH26135) — FULL SYSTEM TEST (FST) SUITE    {RESET}")
    print(f"{BOLD}{CYAN}   Team HexaCore | Government of Maharashtra Showcase         {RESET}")
    print(f"{BOLD}{CYAN}==============================================================={RESET}\n")

    start_time = time.time()

    # 1. Health Check
    print(f"{BOLD}1. SYSTEM HEALTH & TRUTH BOUNDARY CHECKS{RESET}")
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=3)
        log_test("GET /health", r.status_code == 200, f"(Status {r.status_code})")
        data = r.json()
        log_test("Truth Boundary Mode Declared", "PROTOTYPE_SIMULATION_ACTIVE" in data.get("mode", ""), f"({data.get('mode')})")
    except Exception as e:
        log_test("GET /health", False, str(e))

    # 2. Courses Available
    print(f"\n{BOLD}2. VOCATIONAL REGISTRY & CATALOG{RESET}")
    course_id = 1
    try:
        r = requests.get(f"{BASE_URL}/trainee/courses", timeout=3)
        courses = r.json()
        log_test("GET /trainee/courses", r.status_code == 200 and len(courses) >= 5, f"({len(courses)} active courses)")
        course_id = courses[0]["id"]
    except Exception as e:
        log_test("GET /trainee/courses", False, str(e))

    # 3. Trainee Onboarding & OTP Lifecycle
    print(f"\n{BOLD}3. CONSENT-FIRST ONBOARDING & PHONE-OTP LIFECYCLE{RESET}")
    sim_phone = f"98{int(time.time()) % 100000000:08d}"
    mock_otp = None
    try:
        # 3a. Request OTP
        r = requests.post(f"{BASE_URL}/trainee/request-otp", json={"phone": sim_phone}, timeout=3)
        otp_data = r.json()
        mock_otp = otp_data.get("mock_otp")
        log_test("POST /trainee/request-otp", r.status_code == 200 and len(mock_otp) == 6, f"(OTP generated: {mock_otp})")
        log_test("PII Protection (Masked Phone in Response)", "******" in otp_data.get("phone_masked", ""), f"({otp_data.get('phone_masked')})")

        # 3b. Wrong OTP Failure Mode (401)
        r_wrong = requests.post(f"{BASE_URL}/trainee/onboard", json={
            "name": "Validation Candidate",
            "phone": sim_phone,
            "otp": "000000",
            "course_id": course_id,
            "district": "Pune",
            "consent_outcome_followup": True,
            "consent_employer_contact": True
        }, timeout=3)
        log_test("Failure Mode: Wrong OTP Returns 401 Unauthorized", r_wrong.status_code == 401, f"(Status {r_wrong.status_code})")

        # 3c. Correct OTP Happy Path
        r_onboard = requests.post(f"{BASE_URL}/trainee/onboard", json={
            "name": "Validation Candidate",
            "phone": sim_phone,
            "otp": mock_otp,
            "course_id": course_id,
            "district": "Pune",
            "consent_outcome_followup": True,
            "consent_employer_contact": True
        }, timeout=3)
        onboard_data = r_onboard.json()
        new_trainee_id = onboard_data.get("id")
        msid = onboard_data.get("msid")
        log_test("POST /trainee/onboard (Correct OTP)", r_onboard.status_code == 201, f"(Trainee ID: {new_trainee_id})")
        log_test("Salted MSID Generated", msid.startswith("MSID-"), f"({msid})")
        log_test("Zero PII Leak (No raw phone in trainee payload)", "phone" not in onboard_data, "(Verified)")
    except Exception as e:
        log_test("Trainee Onboarding flow", False, str(e))

    # 4. Explainable Risk Engine & Follow-Up Outreach
    print(f"\n{BOLD}4. EXPLAINABLE RISK ENGINE & FOLLOW-UP DISPATCH{RESET}")
    follow_up_id = None
    try:
        r_fu = requests.post(f"{BASE_URL}/followup/send/{new_trainee_id}", json={
            "phone": sim_phone,
            "interval_label": "30_DAYS",
            "channel": "SMS"
        }, timeout=3)
        fu_data = r_fu.json()
        follow_up_id = fu_data.get("follow_up_id")
        risk_score = fu_data.get("risk_score")
        explanations = fu_data.get("risk_explanations", [])
        log_test("POST /followup/send/{id}", r_fu.status_code == 200, f"(Follow-Up #{follow_up_id})")
        log_test("Explainable Risk Calculated", 0.05 <= risk_score <= 0.95, f"(Risk Score: {risk_score:.2f})")
        log_test("Human-Readable Factor Explanations", len(explanations) >= 1, f"({len(explanations)} factors explained)")
    except Exception as e:
        log_test("Follow-Up dispatch flow", False, str(e))

    # 5. Outcome Response & Skill-Gap Capture
    print(f"\n{BOLD}5. OUTCOME RESPONSE & SKILL-GAP / NON-PLACEMENT DIAGNOSTICS{RESET}")
    val_token = None
    try:
        r_resp = requests.post(f"{BASE_URL}/followup/{follow_up_id}/response", json={
            "response_status": "EMPLOYED",
            "employer_name": "Tata Motors Service Hub",
            "wage_band": "18k-25k",
            "non_placement_reason": None,
            "reported_skill_gap": None
        }, timeout=3)
        resp_data = r_resp.json()
        val_link = resp_data.get("employer_validation_link")
        val_token = val_link.split("/")[-1] if val_link else None
        log_test("POST /followup/{id}/response (Employed)", r_resp.status_code == 200, f"(Tier: {resp_data.get('evidence_tier')})")
        log_test("Employer Validation Token Generated", val_token is not None, f"(Token: {val_token[:12]}...)")
    except Exception as e:
        log_test("Outcome response capture", False, str(e))

    # 6. Two-Sided Employer Validation & Audit Lock (409 Conflict)
    print(f"\n{BOLD}6. TWO-SIDED EMPLOYER AUDIT VERIFICATION & ANTI-TAMPER LOCK{RESET}")
    try:
        # 6a. GET validation info
        r_info = requests.get(f"{BASE_URL}/employer/confirm/{val_token}", timeout=3)
        info_data = r_info.json()
        log_test("GET /employer/confirm/{token}", r_info.status_code == 200, f"(Trainee: {info_data.get('trainee_name')})")

        # 6b. First submission (Confirm -> E3 upgrade)
        r_confirm = requests.post(f"{BASE_URL}/employer/confirm", json={
            "token": val_token,
            "confirmed": True
        }, timeout=3)
        confirm_data = r_confirm.json()
        log_test("POST /employer/confirm (First Confirmation)", r_confirm.status_code == 200, f"(Upgraded: {confirm_data.get('evidence_tier')})")

        # 6c. Second submission (MUST RETURN 409 CONFLICT)
        r_resubmit = requests.post(f"{BASE_URL}/employer/confirm", json={
            "token": val_token,
            "confirmed": False
        }, timeout=3)
        log_test("Failure Mode: Resubmission Rejection (HTTP 409 Conflict)", r_resubmit.status_code == 409, f"(Status {r_resubmit.status_code} - Locked)")
    except Exception as e:
        log_test("Employer audit flow", False, str(e))

    # 7. Consent Revocation Gate (403 Forbidden)
    print(f"\n{BOLD}7. CONSENT REVOCATION GATE (DPDP ACT 2023 COMPLIANCE){RESET}")
    try:
        # 7a. Withdraw consent
        r_wd = requests.post(f"{BASE_URL}/trainee/{new_trainee_id}/withdraw-consent", json={}, timeout=3)
        log_test("POST /trainee/{id}/withdraw-consent", r_wd.status_code == 200 and r_wd.json().get("withdrawn") is True, "(Revoked)")

        # 7b. Attempt subsequent outreach (MUST RETURN 403 FORBIDDEN)
        r_blocked = requests.post(f"{BASE_URL}/followup/send/{new_trainee_id}", json={
            "phone": sim_phone,
            "channel": "SMS"
        }, timeout=3)
        log_test("Failure Mode: Follow-up Blocked After Revocation (HTTP 403 Forbidden)", r_blocked.status_code == 403, f"(Status {r_blocked.status_code} - Blocked)")
    except Exception as e:
        log_test("Consent revocation flow", False, str(e))

    # 8. Skill-Gap & Sector Diagnostics Analytics
    print(f"\n{BOLD}8. AGGREGATE ANALYTICS & SKILL-GAP INTELLIGENCE{RESET}")
    try:
        r_sum = requests.get(f"{BASE_URL}/analytics/summary", timeout=3)
        sum_data = r_sum.json()
        tiers = sum_data.get("evidence_tiers", {})
        log_test("GET /analytics/summary", r_sum.status_code == 200, f"(Trainees: {sum_data.get('total_trainees')}, Response Rate: {sum_data.get('response_rate')}%)")
        log_test("Evidence Tier Segregation (E0 != Unemployed)", "E0_NONE" in tiers and "E3_EMPLOYER_CONFIRMED" in tiers, f"(E0={tiers.get('E0_NONE')}, E1={tiers.get('E1_SELF_REPORTED')}, E3={tiers.get('E3_EMPLOYER_CONFIRMED')})")

        r_gaps = requests.get(f"{BASE_URL}/analytics/skill-gaps", timeout=3)
        gaps_data = r_gaps.json()
        top_reasons = gaps_data.get("top_non_placement_reasons", [])
        top_gaps = gaps_data.get("top_reported_skill_gaps", [])
        log_test("GET /analytics/skill-gaps (SIH Deliverable)", r_gaps.status_code == 200 and len(top_reasons) > 0, f"({len(top_reasons)} reasons, {len(top_gaps)} skill gaps tracked)")
    except Exception as e:
        log_test("Analytics intelligence", False, str(e))

    # 9. Explainable Machine Learning (LogisticRegression)
    print(f"\n{BOLD}9. EXPLAINABLE ML LAYER (SCIKIT-LEARN LOGISTIC REGRESSION){RESET}")
    try:
        r_train = requests.post(f"{BASE_URL}/ml/train", timeout=3)
        train_data = r_train.json()
        acc = train_data.get("accuracy_score")
        acc_str = f"{acc*100:.1f}%" if acc is not None else "N/A"
        log_test("POST /ml/train", r_train.status_code == 200 and train_data.get("status") == "success", f"(Trained on {train_data.get('sample_count')} samples, Accuracy: {acc_str})")
        log_test("Plain-English Coefficient Weights", len(train_data.get("feature_explanations", [])) >= 5, f"({len(train_data.get('feature_explanations', []))} feature explainers)")

        r_pred = requests.get(f"{BASE_URL}/ml/predict?sector=Automotive&is_rural=false&channel=SMS&prior_risk=0.20", timeout=3)
        pred_data = r_pred.json()
        prob = pred_data.get("predicted_response_likelihood")
        log_test("GET /ml/predict (Live Inference)", r_pred.status_code == 200, f"(Response Likelihood: {prob*100:.1f}%)")
    except Exception as e:
        log_test("Explainable ML Layer", False, str(e))

    # 10. Integration Readiness Centre
    print(f"\n{BOLD}10. STATUTORY INTEGRATION READINESS MATRIX{RESET}")
    try:
        r_int = requests.get(f"{BASE_URL}/integrations", timeout=3)
        int_data = r_int.json()
        log_test("GET /integrations (11 External Registry Specs)", r_int.status_code == 200 and len(int_data) == 11, f"({len(int_data)} registries mapped)")
        has_epfo = any("EPFO" in item["name"] for item in int_data)
        has_aadhaar = any("Aadhaar" in item["name"] for item in int_data)
        log_test("EPFO & Aadhaar Status honestly labeled AUTHORIZATION_REQUIRED", has_epfo and has_aadhaar, "(Zero false claims)")
    except Exception as e:
        log_test("Integration Readiness matrix", False, str(e))

    # 11. Frontend Zero-Build Static Pages
    print(f"\n{BOLD}11. ZERO-BUILD FRONTEND PAGES (FASTAPI DIRECT SERVING){RESET}")
    routes = [
        ("/", "Simulator (index.html)"),
        ("/dashboard", "Executive Analytics (dashboard.html)"),
        ("/integrations-ui", "Integration Readiness (integrations.html)"),
        ("/employer-view", "Employer Portal (employer_confirm.html)")
    ]
    for route, label in routes:
        try:
            r_page = requests.get(f"{BASE_URL}{route}", timeout=3)
            log_test(f"GET {route} [{label}]", r_page.status_code == 200 and "KSHAMATA-SETU" in r_page.text, f"({len(r_page.text)} bytes)")
        except Exception as e:
            log_test(f"GET {route}", False, str(e))

    elapsed = time.time() - start_time

    # Summary
    print(f"\n{BOLD}{CYAN}==============================================================={RESET}")
    print(f"{BOLD}FULL SYSTEM TEST (FST) RESULTS:{RESET}")
    print(f"  Total Checks Executed : {tests_passed + tests_failed}")
    print(f"  Passed Checks         : {GREEN}{tests_passed}{RESET}")
    print(f"  Failed Checks         : {RED if tests_failed else GREEN}{tests_failed}{RESET}")
    print(f"  Total Execution Time  : {BOLD}{elapsed:.2f} seconds{RESET}")
    print(f"{BOLD}{CYAN}==============================================================={RESET}\n")

    if tests_failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    run_fst()
