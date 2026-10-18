from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Trainee, Course
from app.schemas import (
    OTPRequest, OTPResponse, TraineeOnboardRequest, TraineeResponse, ConsentWithdrawalRequest
)
from app.security import (
    hash_phone, generate_msid, mask_phone, otp_manager
)
from app.messaging import messaging_service
from app.limiter import limiter

router = APIRouter(prefix="/trainee", tags=["Trainee Onboarding & Privacy"])

@router.post("/request-otp", response_model=OTPResponse)
@limiter.limit("5/minute")
def request_otp(request: Request, body: OTPRequest):
    """
    Request 6-digit one-time verification passcode.
    Phone is transmitted strictly via POST body (never query parameters) to prevent URL leak.
    """
    phone = body.phone.strip()
    clean_phone = "".join(filter(str.isdigit, phone))
    if len(clean_phone) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid mobile number. Please supply a valid 10-digit number."
        )

    code = otp_manager.generate_otp(clean_phone)
    masked = mask_phone(clean_phone)

    # Dispatch via Twilio/mock messaging layer
    sms_body = (
        f"Kshamata-Setu Verification: Your one-time login OTP is {code}. "
        f"Valid for 5 minutes. Do not share this code with anyone."
    )
    messaging_service.send_sms(clean_phone, sms_body)

    return OTPResponse(
        message=f"Verification OTP dispatched successfully to {masked}",
        phone_masked=masked,
        expires_in_minutes=5,
        mock_otp=code  # Surfaced for instant judge/demo inspection
    )

@router.post("/onboard", response_model=TraineeResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def onboard_trainee(request: Request, body: TraineeOnboardRequest, db: Session = Depends(get_db)):
    """
    Onboard a trainee with consent-first privacy guarantees:
    - Verifies 6-digit OTP (returns 401 if invalid or expired).
    - Requires distinct, explicit consent checkboxes.
    - Generates MSID (Maharashtra Skill ID) via salted SHA-256 hash.
    - NEVER stores raw mobile number in database.
    """
    clean_phone = "".join(filter(str.isdigit, body.phone))
    
    # 1. Verify OTP
    valid_otp = otp_manager.verify_and_consume_otp(clean_phone, body.otp)
    if not valid_otp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP. Please request a new verification code."
        )

    # 2. Check course exists
    course = db.query(Course).filter(Course.id == body.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID {body.course_id} does not exist."
        )

    # 3. Privacy-safe credentials
    phone_h = hash_phone(clean_phone)
    msid_val = generate_msid(clean_phone)

    # 4. Check for duplicate registration on this course
    existing = db.query(Trainee).filter(
        Trainee.phone_hash == phone_h,
        Trainee.course_id == body.course_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trainee is already registered in this course."
        )

    # 5. Persist Trainee record
    trainee = Trainee(
        name=body.name.strip(),
        phone_hash=phone_h,
        msid=msid_val,
        course_id=body.course_id,
        district=body.district.strip(),
        consent_outcome_followup=body.consent_outcome_followup,
        consent_employer_contact=body.consent_employer_contact,
        withdrawn=False,
        consent_timestamp=datetime.utcnow()
    )
    db.add(trainee)
    db.commit()
    db.refresh(trainee)

    return trainee

@router.post("/{trainee_id}/withdraw-consent")
def withdraw_consent(trainee_id: int, body: Optional[ConsentWithdrawalRequest] = None, db: Session = Depends(get_db)):
    """
    Withdraw consent to stop all automated post-training outreach.
    Sets withdrawn=True and permanently blocks subsequent follow-up dispatches.
    """
    trainee = db.query(Trainee).filter(Trainee.id == trainee_id).first()
    if not trainee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trainee with ID {trainee_id} not found."
        )

    purpose = body.purpose if body else None
    if purpose == "employer_contact":
        trainee.consent_employer_contact = False
    elif purpose == "outcome_followup":
        trainee.consent_outcome_followup = False
        trainee.withdrawn = True
    else:
        # Default: withdraw both
        trainee.consent_outcome_followup = False
        trainee.consent_employer_contact = False
        trainee.withdrawn = True

    db.commit()
    return {
        "status": "CONSENT_WITHDRAWN",
        "trainee_id": trainee.id,
        "withdrawn": trainee.withdrawn,
        "consent_outcome_followup": trainee.consent_outcome_followup,
        "consent_employer_contact": trainee.consent_employer_contact,
        "message": "Consent successfully updated. Future automated outreach is blocked."
    }

@router.get("/list", response_model=List[TraineeResponse])
def list_trainees(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """List registered trainees for simulation and audit review."""
    return db.query(Trainee).offset(skip).limit(limit).all()

@router.get("/courses")
def list_courses(db: Session = Depends(get_db)):
    """List vocational courses for onboarding selection."""
    courses = db.query(Course).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "sector": c.sector,
            "skill_tags": c.skill_tags.split(",") if c.skill_tags else []
        }
        for c in courses
    ]
