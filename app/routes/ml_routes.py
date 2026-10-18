from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.ml_service import ml_service
from app.schemas import MLTrainResponse, MLPredictRequest, MLPredictResponse

router = APIRouter(prefix="/ml", tags=["Explainable Machine Learning"])

@router.post("/train", response_model=MLTrainResponse)
def train_model(db: Session = Depends(get_db)):
    """
    Trains an explainable scikit-learn LogisticRegression model on current database follow-up records.
    Returns human-readable feature coefficient explanations:
    '{feature}: {increases/decreases} response-likelihood (weight={value})'.
    Gracefully handles insufficient data without crashing.
    """
    result = ml_service.train_model(db)
    return MLTrainResponse(**result)

@router.post("/predict", response_model=MLPredictResponse)
def predict_response_likelihood(body: MLPredictRequest):
    """
    Runs live prediction for a trainee follow-up scenario using the trained model
    or rule-based baseline.
    """
    res = ml_service.predict(
        sector=body.sector,
        is_rural=body.is_rural,
        channel=body.channel,
        prior_risk=body.prior_risk
    )
    return MLPredictResponse(**res)

@router.get("/predict", response_model=MLPredictResponse)
def predict_response_likelihood_get(
    sector: str = Query("Healthcare", description="Vocational training sector"),
    is_rural: bool = Query(False, description="Whether district is rural"),
    channel: str = Query("SMS", description="SMS or WHATSAPP"),
    prior_risk: float = Query(0.20, description="Calculated non-response risk score")
):
    """Convenience GET endpoint for live browser/curl query."""
    res = ml_service.predict(
        sector=sector,
        is_rural=is_rural,
        channel=channel,
        prior_risk=prior_risk
    )
    return MLPredictResponse(**res)
