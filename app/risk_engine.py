from typing import List, Tuple

# Rationale documentation:
# - BASELINE (0.20): Empirical vocational trainee attrition in Indian skill ecosystems.
# - RURAL_WEIGHT (+0.15): Remote geography faces higher cellular coverage drops and circular agrarian migration.
# - HIGH_MOBILITY_SECTOR_WEIGHT (+0.10): Sectors like Logistics, Construction, Hospitality, and Security show frequent phone number switches.
# - PRIOR_RESPONSE_BONUS (-0.08): Each verified prior interaction strengthens institutional trust and contact reliability.

RURAL_DISTRICTS = {
    "gadchiroli", "nandurbar", "washim", "hingoli", "yavatmal", 
    "beed", "osmanabad", "dharashiv", "jalna", "buldhana"
}

HIGH_MOBILITY_SECTORS = {
    "construction", "logistics", "security", "hospitality", "transport"
}

def calculate_non_response_risk(
    district: str,
    course_sector: str,
    prior_responses_count: int
) -> Tuple[float, List[str]]:
    """
    Computes transparent, explainable non-response risk score with human-readable factors.
    Returns: (score_clamped_0_to_1, list_of_explanation_strings)
    """
    score = 0.20
    explanations: List[str] = [
        "Baseline vocational cohort attrition risk (+0.20)"
    ]

    # Check Rural District
    clean_district = district.strip().lower()
    if clean_district in RURAL_DISTRICTS:
        score += 0.15
        explanations.append(
            f"Rural district '{district}': higher cellular connectivity fluctuation and migration (+0.15)"
        )

    # Check High Mobility Sector
    clean_sector = course_sector.strip().lower()
    if any(mob in clean_sector for mob in HIGH_MOBILITY_SECTORS):
        score += 0.10
        explanations.append(
            f"High-mobility sector '{course_sector}': elevated job turnover and SIM-churn rate (+0.10)"
        )

    # Prior responses bonus
    if prior_responses_count > 0:
        reduction = min(prior_responses_count * 0.08, 0.40)
        score -= reduction
        explanations.append(
            f"Trainee history: {prior_responses_count} prior verified responses indicate established contact trust (-{reduction:.2f})"
        )

    # Clamping
    clamped_score = max(0.05, min(0.95, round(score, 2)))
    return clamped_score, explanations
