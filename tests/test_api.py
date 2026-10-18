import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import Provider, Course, Trainee, FollowUpRecord, EmployerValidation, EvidenceTier
from app.security import otp_manager
from app.limiter import limiter

# Isolated test DB in memory
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    # Reset tables
    db.query(EmployerValidation).delete()
    db.query(FollowUpRecord).delete()
    db.query(Trainee).delete()
    db.query(Course).delete()
    db.query(Provider).delete()
    db.commit()

    # Seed baseline provider & course
    p = Provider(name="Pune Vocational Institute", district="Pune")
    db.add(p)
    db.commit()
    db.refresh(p)

    c = Course(name="Healthcare Assistant", sector="Healthcare", skill_tags="Patient Care, Vitals", provider_id=p.id)
    db.add(c)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)

def test_1_wrong_otp_returns_401():
    """Failure Mode 1: Invalid OTP must return 401 Unauthorized."""
    phone = "9876543210"
    otp_manager.generate_otp(phone)

    payload = {
        "name": "Amit Sharma",
        "phone": phone,
        "otp": "000000",  # WRONG OTP
        "course_id": 1,
        "district": "Pune",
        "consent_outcome_followup": True,
        "consent_employer_contact": True
    }
    response = client.post("/trainee/onboard", json=payload)
    assert response.status_code == 401
    assert "Invalid or expired OTP" in response.json()["detail"]

def test_1b_correct_otp_succeeds_and_hashes_phone():
    """Happy Path: Correct OTP onboards trainee, generates MSID, never leaks raw phone."""
    phone = "9876543210"
    code = otp_manager.generate_otp(phone)

    payload = {
        "name": "Amit Sharma",
        "phone": phone,
        "otp": code,
        "course_id": 1,
        "district": "Pune",
        "consent_outcome_followup": True,
        "consent_employer_contact": True
    }
    response = client.post("/trainee/onboard", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Amit Sharma"
    assert data["msid"].startswith("MSID-")
    assert "phone" not in data  # Never leak raw phone

def test_2_consent_withdrawal_blocks_followup_with_403():
    """Failure Mode 2: Follow-up attempt after consent withdrawal MUST return 403 Forbidden."""
    # 1. Onboard trainee
    phone = "9876543211"
    code = otp_manager.generate_otp(phone)
    client.post("/trainee/onboard", json={
        "name": "Sunita Patil",
        "phone": phone,
        "otp": code,
        "course_id": 1,
        "district": "Pune",
        "consent_outcome_followup": True,
        "consent_employer_contact": True
    })

    # 2. Withdraw consent
    withdraw_resp = client.post("/trainee/1/withdraw-consent", json={})
    assert withdraw_resp.status_code == 200
    assert withdraw_resp.json()["withdrawn"] is True

    # 3. Attempt follow-up outreach -> Must be blocked with 403
    followup_resp = client.post("/followup/send/1", json={"phone": phone, "channel": "SMS"})
    assert followup_resp.status_code == 403
    assert "Forbidden: Trainee has withdrawn consent" in followup_resp.json()["detail"]

def test_3_employer_confirm_resubmission_returns_409():
    """
    Failure Mode 3: Resubmitting employer validation once already confirmed/rejected
    MUST return 409 Conflict to protect audit-trail integrity.
    """
    phone = "9876543212"
    code = otp_manager.generate_otp(phone)
    client.post("/trainee/onboard", json={
        "name": "Rahul Deshmukh",
        "phone": phone,
        "otp": code,
        "course_id": 1,
        "district": "Pune",
        "consent_outcome_followup": True,
        "consent_employer_contact": True
    })

    # Trigger follow-up
    f_resp = client.post("/followup/send/1", json={"phone": phone, "channel": "SMS"})
    f_id = f_resp.json()["follow_up_id"]

    # Trainee responds with EMPLOYED status and employer name
    resp_submission = client.post(f"/followup/{f_id}/response", json={
        "response_status": "EMPLOYED",
        "employer_name": "Apollo Clinic",
        "wage_band": "18k-25k"
    })
    assert resp_submission.status_code == 200
    val_link = resp_submission.json()["employer_validation_link"]
    token = val_link.split("/")[-1]

    # Employer confirms for the first time -> 200 OK
    first_confirm = client.post("/employer/confirm", json={"token": token, "confirmed": True})
    assert first_confirm.status_code == 200
    assert first_confirm.json()["evidence_tier"] == EvidenceTier.E3_EMPLOYER_CONFIRMED.value

    # Attempt to re-submit / flip answer -> MUST BE REJECTED WITH 409 CONFLICT
    second_confirm = client.post("/employer/confirm", json={"token": token, "confirmed": False})
    assert second_confirm.status_code == 409
    assert "Conflict: This validation has already been submitted" in second_confirm.json()["detail"]

def test_4_rate_limiting_onboard_11th_returns_429():
    """Failure Mode 4: 11 rapid requests to /trainee/onboard returns 429 Too Many Requests."""
    # Reset limiter storage for clean test
    limiter.reset()

    phone = "9876543213"
    code = otp_manager.generate_otp(phone)
    payload = {
        "name": "Spam User",
        "phone": phone,
        "otp": code,
        "course_id": 1,
        "district": "Pune",
        "consent_outcome_followup": True,
        "consent_employer_contact": True
    }

    status_codes = []
    for _ in range(12):
        r = client.post("/trainee/onboard", json=payload)
        status_codes.append(r.status_code)

    # At least one request after limit of 10/minute must be 429
    assert 429 in status_codes

def test_5_ml_training_with_insufficient_data():
    """Failure Mode 5: ML training with insufficient dataset returns graceful status without crashing."""
    # Database currently has 0 follow-up records
    resp = client.post("/ml/train")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "insufficient_data"
    assert "Insufficient data to train LogisticRegression model" in data["message"]

def test_6_skill_gap_analytics():
    """Verify skill gaps and non placement reason aggregation."""
    db = TestingSessionLocal()
    # Create trainee
    t = Trainee(
        name="Kavita Jadhav",
        phone_hash="hash123",
        msid="MSID-KAVITA123",
        course_id=1,
        district="Pune",
        consent_outcome_followup=True,
        consent_employer_contact=True,
        withdrawn=False
    )
    db.add(t)
    db.commit()
    db.refresh(t)

    from datetime import datetime
    f = FollowUpRecord(
        trainee_id=t.id,
        interval_label="30_DAYS",
        channel="SMS",
        sent_timestamp=datetime.utcnow(),
        response_timestamp=datetime.utcnow(),
        evidence_tier=EvidenceTier.E1_SELF_REPORTED.value,
        non_placement_reason="Shift timings incompatible with public transit",
        reported_skill_gap="Hands-on practice with computerized equipment",
        risk_score=0.25
    )
    db.add(f)
    db.commit()
    db.close()

    resp = client.get("/analytics/skill-gaps")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["top_non_placement_reasons"]) >= 1
    assert data["top_non_placement_reasons"][0]["reason"] == "Shift timings incompatible with public transit"
    assert len(data["top_reported_skill_gaps"]) >= 1
    assert data["top_reported_skill_gaps"][0]["gap"] == "Hands-on practice with computerized equipment"

def test_7_integration_readiness_endpoint():
    """Verify integration readiness center matrix contains all 11 specs."""
    resp = client.get("/integrations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 11
    names = [item["name"] for item in data]
    assert any("Aadhaar" in n for n in names)
    assert any("EPFO" in n for n in names)
    assert any("GSTIN" in n for n in names)
    assert any("SMS Gateway" in n for n in names)
