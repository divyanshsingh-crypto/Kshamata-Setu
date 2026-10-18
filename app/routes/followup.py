import secrets
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Trainee, Course, FollowUpRecord, EmployerValidation, EvidenceTier
from app.schemas import (
    FollowUpSendRequest, FollowUpSendResponse, FollowUpResponseSubmission, FollowUpRecordResponse
)
from app.risk_engine import calculate_non_response_risk
from app.messaging import messaging_service
from app.limiter import limiter

router = APIRouter(prefix="/followup", tags=["Follow-Up & Evidence Capture"])

@router.post("/send/{trainee_id}", response_model=FollowUpSendResponse)
@limiter.limit("15/minute")
def trigger_followup(
    request: Request,
    trainee_id: int,
    body: FollowUpSendRequest,
    db: Session = Depends(get_db)
):
    """
    Triggers follow-up outreach:
    1. Checks trainee exists.
    2. Enforces Consent Withdrawal Gate: If trainee.withdrawn is True, rejects with 403 Forbidden.
    3. Computes transparent risk score with human-readable rationale.
    4. Records FollowUpRecord initialized to E0_NONE evidence tier.
    5. Dispatches communication via Twilio / mock gateway.
    """
    trainee = db.query(Trainee).filter(Trainee.id == trainee_id).first()
    if not trainee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trainee with ID {trainee_id} not found."
        )

    # Consent gate
    if trainee.withdrawn or not trainee.consent_outcome_followup:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Trainee has withdrawn consent or not authorized outcome follow-ups."
        )

    # Count prior responses to calculate trust reduction
    prior_responses = (
        db.query(FollowUpRecord)
        .filter(
            FollowUpRecord.trainee_id == trainee_id,
            FollowUpRecord.response_timestamp.isnot(None)
        )
        .count()
    )

    course = db.query(Course).filter(Course.id == trainee.course_id).first()
    course_sector = course.sector if course else "General"

    # Compute risk & explanation factors
    risk_score, explanations = calculate_non_response_risk(
        district=trainee.district,
        course_sector=course_sector,
        prior_responses_count=prior_responses
    )

    # Create FollowUpRecord
    channel = body.channel or "SMS"
    interval_label = body.interval_label or "30_DAYS"
    record = FollowUpRecord(
        trainee_id=trainee.id,
        interval_label=interval_label,
        channel=channel,
        sent_timestamp=datetime.utcnow(),
        evidence_tier=EvidenceTier.E0_NONE.value,
        risk_score=risk_score
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # Dispatch message
    clean_phone = "".join(filter(str.isdigit, body.phone))
    sms_text = (
        f"Kshamata-Setu Follow-Up: Namaste {trainee.name}! Please share your employment status "
        f"for {course.name if course else 'your training'} ({interval_label}). "
        f"Reply or click your outcome check-in link."
    )
    dispatch_result = messaging_service.send_sms(clean_phone, sms_text)

    return FollowUpSendResponse(
        follow_up_id=record.id,
        trainee_id=trainee.id,
        channel=channel,
        sent_timestamp=record.sent_timestamp,
        risk_score=risk_score,
        risk_explanations=explanations,
        message_delivery_status=dispatch_result.get("status", "SENT")
    )

@router.post("/{follow_up_id}/response", response_model=FollowUpRecordResponse)
def record_trainee_response(
    follow_up_id: int,
    body: FollowUpResponseSubmission,
    db: Session = Depends(get_db)
):
    """
    Records trainee follow-up response and evidence tier.
    - If status is EMPLOYED -> Upgrades tier from E0_NONE to E1_SELF_REPORTED.
    - If employer_name is supplied -> Automatically generates EmployerValidation audit token.
    - Captures non_placement_reason and reported_skill_gap for diagnostic analytics.
    """
    record = db.query(FollowUpRecord).filter(FollowUpRecord.id == follow_up_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Follow-up record {follow_up_id} not found."
        )

    record.response_timestamp = datetime.utcnow()
    record.wage_band = body.wage_band
    record.non_placement_reason = body.non_placement_reason
    record.reported_skill_gap = body.reported_skill_gap

    validation_link = None
    status_upper = body.response_status.strip().upper()

    if status_upper == "EMPLOYED":
        record.evidence_tier = EvidenceTier.E1_SELF_REPORTED.value
        record.employer_name = body.employer_name

        # If employer name provided, generate employer verification token
        if body.employer_name and body.employer_name.strip():
            # Check if token already exists
            existing_val = db.query(EmployerValidation).filter(
                EmployerValidation.follow_up_id == record.id
            ).first()

            if not existing_val:
                token = secrets.token_urlsafe(24)
                val_entry = EmployerValidation(
                    follow_up_id=record.id,
                    token=token,
                    confirmed=None,
                    confirmed_timestamp=None
                )
                db.add(val_entry)
                db.commit()
                db.refresh(val_entry)
                validation_link = f"/employer/confirm/{token}"
            else:
                validation_link = f"/employer/confirm/{existing_val.token}"
    else:
        # Trainee is seeking, further education, or unavailable
        # Note: evidence_tier remains E0_NONE or E1_SELF_REPORTED (unplaced self-attested)
        record.evidence_tier = EvidenceTier.E1_SELF_REPORTED.value
        record.employer_name = None

    db.commit()
    db.refresh(record)

    response_data = FollowUpRecordResponse(
        id=record.id,
        trainee_id=record.trainee_id,
        interval_label=record.interval_label,
        channel=record.channel,
        sent_timestamp=record.sent_timestamp,
        response_timestamp=record.response_timestamp,
        evidence_tier=record.evidence_tier,
        employer_name=record.employer_name,
        wage_band=record.wage_band,
        non_placement_reason=record.non_placement_reason,
        reported_skill_gap=record.reported_skill_gap,
        risk_score=record.risk_score,
        employer_validation_link=validation_link
    )
    return response_data

@router.get("/records", response_model=List[FollowUpRecordResponse])
def list_followup_records(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """List recent follow-up interactions."""
    records = db.query(FollowUpRecord).order_by(FollowUpRecord.id.desc()).offset(skip).limit(limit).all()
    out = []
    for r in records:
        link = None
        if r.employer_validation:
            link = f"/employer/confirm/{r.employer_validation.token}"
        out.append(
            FollowUpRecordResponse(
                id=r.id,
                trainee_id=r.trainee_id,
                interval_label=r.interval_label,
                channel=r.channel,
                sent_timestamp=r.sent_timestamp,
                response_timestamp=r.response_timestamp,
                evidence_tier=r.evidence_tier,
                employer_name=r.employer_name,
                wage_band=r.wage_band,
                non_placement_reason=r.non_placement_reason,
                reported_skill_gap=r.reported_skill_gap,
                risk_score=r.risk_score,
                employer_validation_link=link
            )
        )
    return out
