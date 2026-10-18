from collections import Counter
from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Trainee, Course, FollowUpRecord, EvidenceTier
from app.schemas import AnalyticsSummaryResponse, SkillGapAnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["Analytics & Outcome Intelligence"])

@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_analytics_summary(db: Session = Depends(get_db)):
    """
    Returns high-level outcomes with granular evidence-tier segregation.
    CRITICAL TRUTH: E0_NONE indicates uncompleted follow-ups, NEVER presumed as unemployed.
    """
    total_trainees = db.query(func.count(Trainee.id)).scalar() or 0
    total_followups = db.query(func.count(FollowUpRecord.id)).scalar() or 0
    total_responses = (
        db.query(func.count(FollowUpRecord.id))
        .filter(FollowUpRecord.response_timestamp.isnot(None))
        .scalar()
        or 0
    )

    # Evidence tier counts
    tier_counts = (
        db.query(FollowUpRecord.evidence_tier, func.count(FollowUpRecord.id))
        .group_by(FollowUpRecord.evidence_tier)
        .all()
    )
    tiers_dict = {
        EvidenceTier.E0_NONE.value: 0,
        EvidenceTier.E1_SELF_REPORTED.value: 0,
        EvidenceTier.E3_EMPLOYER_CONFIRMED.value: 0,
        EvidenceTier.REJECTED_OR_DISPUTED.value: 0
    }
    for tier, count in tier_counts:
        tiers_dict[tier] = count

    response_rate = round((total_responses / total_followups * 100), 1) if total_followups > 0 else 0.0
    
    # Placed trainees = E1 + E3
    placed_count = tiers_dict[EvidenceTier.E1_SELF_REPORTED.value] + tiers_dict[EvidenceTier.E3_EMPLOYER_CONFIRMED.value]
    placement_rate = round((placed_count / total_responses * 100), 1) if total_responses > 0 else 0.0

    return AnalyticsSummaryResponse(
        total_trainees=total_trainees,
        total_followups=total_followups,
        total_responses=total_responses,
        response_rate=response_rate,
        placement_rate=placement_rate,
        evidence_tiers=tiers_dict,
        note="Prototype mode: synthetic data and mock adapters only. No live government API or real trainee PII is used."
    )

@router.get("/skill-gaps", response_model=SkillGapAnalyticsResponse)
def get_skill_gap_analytics(db: Session = Depends(get_db)):
    """
    Directly fulfills PS SIH26135 requirement:
    Identifies root causes of non-placement and trainee-reported skill deficits
    broken down overall and by course sector.
    """
    records = (
        db.query(FollowUpRecord, Course.sector)
        .join(Trainee, FollowUpRecord.trainee_id == Trainee.id)
        .join(Course, Trainee.course_id == Course.id)
        .filter(
            FollowUpRecord.response_timestamp.isnot(None),
            FollowUpRecord.evidence_tier != EvidenceTier.E3_EMPLOYER_CONFIRMED.value
        )
        .all()
    )

    all_reasons = []
    all_gaps = []
    sector_reasons: Dict[str, List[str]] = {}
    sector_gaps: Dict[str, List[str]] = {}

    for rec, sector in records:
        if rec.non_placement_reason and rec.non_placement_reason.strip():
            reason = rec.non_placement_reason.strip()
            all_reasons.append(reason)
            sector_reasons.setdefault(sector, []).append(reason)

        if rec.reported_skill_gap and rec.reported_skill_gap.strip():
            gap = rec.reported_skill_gap.strip()
            all_gaps.append(gap)
            sector_gaps.setdefault(sector, []).append(gap)

    top_reasons_counter = Counter(all_reasons).most_common(5)
    top_gaps_counter = Counter(all_gaps).most_common(5)

    top_reasons = [{"reason": r, "count": c} for r, c in top_reasons_counter]
    top_gaps = [{"gap": g, "count": c} for g, c in top_gaps_counter]

    sector_breakdown = {}
    all_sectors = set(list(sector_reasons.keys()) + list(sector_gaps.keys()))
    for s in all_sectors:
        reasons_s = [
            {"reason": r, "count": c} for r, c in Counter(sector_reasons.get(s, [])).most_common(3)
        ]
        gaps_s = [
            {"gap": g, "count": c} for g, c in Counter(sector_gaps.get(s, [])).most_common(3)
        ]
        sector_breakdown[s] = {
            "top_reasons": reasons_s,
            "top_skill_gaps": gaps_s,
            "total_unplaced_analyzed": len(sector_reasons.get(s, []))
        }

    return SkillGapAnalyticsResponse(
        top_non_placement_reasons=top_reasons,
        top_reported_skill_gaps=top_gaps,
        sector_breakdown=sector_breakdown,
        disclaimer="Diagnostic analysis derived from structured post-training follow-up feedback."
    )

@router.get("/by-course")
def get_analytics_by_course(db: Session = Depends(get_db)):
    """Course-level outcome metrics."""
    courses = db.query(Course).all()
    results = []

    for c in courses:
        trainees = db.query(Trainee).filter(Trainee.course_id == c.id).all()
        t_ids = [t.id for t in trainees]
        followups = (
            db.query(FollowUpRecord)
            .filter(FollowUpRecord.trainee_id.in_(t_ids))
            .all()
            if t_ids else []
        )

        total_f = len(followups)
        responded_f = [f for f in followups if f.response_timestamp is not None]
        total_resp = len(responded_f)
        e3_count = len([f for f in responded_f if f.evidence_tier == EvidenceTier.E3_EMPLOYER_CONFIRMED.value])
        e1_count = len([f for f in responded_f if f.evidence_tier == EvidenceTier.E1_SELF_REPORTED.value])

        placement_rate = round(((e1_count + e3_count) / total_resp * 100), 1) if total_resp > 0 else 0.0
        verified_rate = round((e3_count / total_resp * 100), 1) if total_resp > 0 else 0.0

        results.append({
            "course_id": c.id,
            "course_name": c.name,
            "sector": c.sector,
            "total_enrolled": len(trainees),
            "total_followups": total_f,
            "total_responses": total_resp,
            "placement_rate": placement_rate,
            "employer_verified_rate": verified_rate
        })

    return results

@router.get("/by-district")
def get_analytics_by_district(db: Session = Depends(get_db)):
    """District-level geographic distribution of trainees and outcomes."""
    districts = db.query(Trainee.district, func.count(Trainee.id)).group_by(Trainee.district).all()
    out = []
    for dist, count in districts:
        out.append({
            "district": dist,
            "trainee_count": count
        })
    return out
