from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class OTPRequest(BaseModel):
    phone: str = Field(..., description="Trainee mobile number (10 digits)")

class OTPResponse(BaseModel):
    message: str
    phone_masked: str
    expires_in_minutes: int
    mock_otp: Optional[str] = None  # Transparently surfaced for demo/prototype convenience

class TraineeOnboardRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., description="Mobile number used to verify OTP")
    otp: str = Field(..., min_length=6, max_length=6)
    course_id: int
    district: str = Field(..., min_length=2, max_length=100)
    consent_outcome_followup: bool = Field(..., description="Explicit consent for 30/90/180-day employment follow-ups")
    consent_employer_contact: bool = Field(..., description="Explicit consent for employer verification outreach")

class TraineeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    msid: str
    course_id: int
    district: str
    consent_outcome_followup: bool
    consent_employer_contact: bool
    withdrawn: bool
    consent_timestamp: Optional[datetime]

class FollowUpSendRequest(BaseModel):
    phone: str = Field(..., description="Target phone number (POST body only, never in URL query)")
    interval_label: Optional[str] = "30_DAYS"
    channel: Optional[str] = "SMS"

class FollowUpSendResponse(BaseModel):
    follow_up_id: int
    trainee_id: int
    channel: str
    sent_timestamp: datetime
    risk_score: float
    risk_explanations: List[str]
    message_delivery_status: str

class FollowUpResponseSubmission(BaseModel):
    response_status: str = Field(..., description="EMPLOYED, SEEKING, EDUCATION, or UNAVAILABLE")
    employer_name: Optional[str] = None
    wage_band: Optional[str] = None
    non_placement_reason: Optional[str] = None
    reported_skill_gap: Optional[str] = None

class FollowUpRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trainee_id: int
    interval_label: str
    channel: str
    sent_timestamp: datetime
    response_timestamp: Optional[datetime]
    evidence_tier: str
    employer_name: Optional[str]
    wage_band: Optional[str]
    non_placement_reason: Optional[str]
    reported_skill_gap: Optional[str]
    risk_score: float
    employer_validation_link: Optional[str] = None

class EmployerValidationInfo(BaseModel):
    token: str
    trainee_name: str
    course_name: str
    claimed_employer: str
    status: str
    already_confirmed: bool
    confirmed_timestamp: Optional[datetime]

class EmployerConfirmRequest(BaseModel):
    token: str
    confirmed: bool

class ConsentWithdrawalRequest(BaseModel):
    purpose: Optional[str] = Field(None, description="Optional: 'outcome_followup', 'employer_contact', or None for both")

class AnalyticsSummaryResponse(BaseModel):
    total_trainees: int
    total_followups: int
    total_responses: int
    response_rate: float
    placement_rate: float
    evidence_tiers: Dict[str, int]
    note: str

class SkillGapAnalyticsResponse(BaseModel):
    top_non_placement_reasons: List[Dict[str, Any]]
    top_reported_skill_gaps: List[Dict[str, Any]]
    sector_breakdown: Dict[str, Dict[str, Any]]
    disclaimer: str

class IntegrationItem(BaseModel):
    name: str
    status: str
    production_prerequisites: str
    last_tested: str
    category: str

class MLTrainResponse(BaseModel):
    status: str
    message: str
    sample_count: int
    feature_explanations: Optional[List[str]] = None
    accuracy_score: Optional[float] = None

class MLPredictRequest(BaseModel):
    sector: str
    is_rural: bool
    channel: str
    prior_risk: float

class MLPredictResponse(BaseModel):
    predicted_response_likelihood: float
    will_respond_likely: bool
    confidence_statement: str
