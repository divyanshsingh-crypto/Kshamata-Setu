from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import EmployerValidation, FollowUpRecord, Trainee, Course, EvidenceTier
from app.schemas import EmployerValidationInfo, EmployerConfirmRequest
from app.limiter import limiter

router = APIRouter(prefix="/employer", tags=["Employer Two-Sided Validation"])

@router.get("/confirm/{token}", response_model=EmployerValidationInfo)
def get_employer_validation_info(token: str, db: Session = Depends(get_db)):
    """
    Displays verification prompt to employer representative:
    - Trainee Name
    - Training Course Name
    - Claimed Employer Name
    - Current confirmation status and audit lock state
    """
    val = (
        db.query(EmployerValidation)
        .filter(EmployerValidation.token == token)
        .first()
    )
    if not val:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired employer validation token."
        )

    follow_up = val.follow_up
    trainee = follow_up.trainee
    course = trainee.course if trainee else None

    status_str = "PENDING"
    if val.confirmed is True:
        status_str = "CONFIRMED"
    elif val.confirmed is False:
        status_str = "REJECTED"

    return EmployerValidationInfo(
        token=val.token,
        trainee_name=trainee.name if trainee else "Unknown",
        course_name=course.name if course else "Vocational Course",
        claimed_employer=follow_up.employer_name or "Not Specified",
        status=status_str,
        already_confirmed=(val.confirmed_timestamp is not None),
        confirmed_timestamp=val.confirmed_timestamp
    )

@router.post("/confirm")
@limiter.limit("20/minute")
def submit_employer_confirmation(
    request: Request,
    body: EmployerConfirmRequest,
    db: Session = Depends(get_db)
):
    """
    Audit-safe outcome confirmation:
    - Verifies token exists.
    - REJECTS resubmission with 409 Conflict if already responded (audit integrity lock).
    - Upgrades evidence tier to E3_EMPLOYER_CONFIRMED if approved.
    - Sets tier to REJECTED_OR_DISPUTED if denied.
    """
    val = (
        db.query(EmployerValidation)
        .filter(EmployerValidation.token == body.token)
        .first()
    )
    if not val:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid validation token."
        )

    # CRITICAL AUDIT INTEGRITY LOCK:
    # Once an employer response has been timestamped, it CANNOT be altered or flipped.
    if val.confirmed_timestamp is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict: This validation has already been submitted and is permanently locked for audit integrity."
        )

    val.confirmed = body.confirmed
    val.confirmed_timestamp = datetime.utcnow()

    # Upgrade follow-up evidence tier accordingly
    follow_up = val.follow_up
    if body.confirmed:
        follow_up.evidence_tier = EvidenceTier.E3_EMPLOYER_CONFIRMED.value
    else:
        follow_up.evidence_tier = EvidenceTier.REJECTED_OR_DISPUTED.value

    db.commit()
    db.refresh(val)
    db.refresh(follow_up)

    result_status = "EMPLOYER_CONFIRMED (Tier E3)" if body.confirmed else "EMPLOYER_DISPUTED (Dispute Flagged)"
    return {
        "status": "RECORDED",
        "result": result_status,
        "evidence_tier": follow_up.evidence_tier,
        "confirmed_timestamp": val.confirmed_timestamp,
        "message": "Employer validation recorded securely. Audit lock engaged."
    }
