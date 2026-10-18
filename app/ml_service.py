import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import numpy as np
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models import FollowUpRecord, Trainee, Course
from app.risk_engine import RURAL_DISTRICTS

class ExplainableMLService:
    def __init__(self):
        self.model = None
        self.feature_names: List[str] = []
        self.feature_explanations: List[str] = []
        self.is_trained = False
        self.accuracy: Optional[float] = None
        self.known_sectors: List[str] = ["Healthcare", "Automotive", "Solar & Renewable", "Retail & Logistics", "Information Technology"]

    def _extract_features_and_labels(self, db: Session):
        records = (
            db.query(FollowUpRecord, Trainee, Course)
            .join(Trainee, FollowUpRecord.trainee_id == Trainee.id)
            .join(Course, Trainee.course_id == Course.id)
            .all()
        )
        if not records:
            return None, None, []

        # Collect unique sectors across records
        sectors = sorted(list(set(c.sector for _, _, c in records)))
        if not sectors:
            sectors = self.known_sectors
        self.known_sectors = sectors

        X = []
        y = []

        for record, trainee, course in records:
            # Feature 1..K: Sector One-Hot
            sector_features = [1.0 if course.sector == s else 0.0 for s in self.known_sectors]
            # Feature K+1: is_rural (1 or 0)
            is_rural = 1.0 if trainee.district.strip().lower() in RURAL_DISTRICTS else 0.0
            # Feature K+2: channel is SMS
            is_sms = 1.0 if record.channel.upper() == "SMS" else 0.0
            # Feature K+3: prior risk score
            risk = float(record.risk_score)

            features = sector_features + [is_rural, is_sms, risk]
            # Target: 1 if responded, 0 if unresolved/no response
            target = 1 if record.response_timestamp is not None else 0

            X.append(features)
            y.append(target)

        feature_names = [f"Sector: {s}" for s in self.known_sectors] + [
            "District: Rural Geography",
            "Channel: SMS Outreach",
            "Prior Non-Response Risk Score"
        ]

        return np.array(X), np.array(y), feature_names

    def train_model(self, db: Session) -> Dict[str, Any]:
        from sklearn.linear_model import LogisticRegression

        X, y, feature_names = self._extract_features_and_labels(db)
        sample_count = len(y) if y is not None else 0

        # Graceful handling for insufficient data:
        # Require at least 8 samples and at least 2 classes in y
        if sample_count < 8 or len(np.unique(y)) < 2:
            return {
                "status": "insufficient_data",
                "message": (
                    f"Insufficient data to train LogisticRegression model. "
                    f"Found {sample_count} records with {len(np.unique(y)) if y is not None else 0} distinct classes. "
                    f"Need at least 8 samples with both responded and unresponded outcomes."
                ),
                "sample_count": sample_count,
                "feature_explanations": [],
                "accuracy_score": None
            }

        try:
            clf = LogisticRegression(solver="liblinear", max_iter=200, random_state=42)
            clf.fit(X, y)
            accuracy = float(clf.score(X, y))

            coefficients = clf.coef_[0]
            explanations = []
            for name, coef in zip(feature_names, coefficients):
                direction = "increases" if coef > 0 else "decreases"
                explanations.append(
                    f"{name}: {direction} response-likelihood (weight={coef:+.3f})"
                )

            self.model = clf
            self.feature_names = feature_names
            self.feature_explanations = explanations
            self.is_trained = True
            self.accuracy = round(accuracy, 3)

            return {
                "status": "success",
                "message": f"Trained explainable LogisticRegression model on {sample_count} historical records.",
                "sample_count": sample_count,
                "feature_explanations": explanations,
                "accuracy_score": self.accuracy
            }
        except Exception as e:
            return {
                "status": "insufficient_data",
                "message": f"Model training deferred: {str(e)}",
                "sample_count": sample_count,
                "feature_explanations": [],
                "accuracy_score": None
            }

    def predict(
        self,
        sector: str,
        is_rural: bool,
        channel: str,
        prior_risk: float
    ) -> Dict[str, Any]:
        """Live prediction using fitted model, or transparent rule fallback if un-trained."""
        if self.is_trained and self.model is not None:
            sector_features = [1.0 if sector == s else 0.0 for s in self.known_sectors]
            is_rural_val = 1.0 if is_rural else 0.0
            is_sms_val = 1.0 if channel.upper() == "SMS" else 0.0
            features = np.array([sector_features + [is_rural_val, is_sms_val, float(prior_risk)]])

            prob = self.model.predict_proba(features)[0][1]
            likelihood = round(float(prob), 3)
            will_respond = likelihood >= 0.50
            return {
                "predicted_response_likelihood": likelihood,
                "will_respond_likely": will_respond,
                "confidence_statement": (
                    f"Explainable Logistic Regression predicts {likelihood*100:.1f}% probability of trainee response "
                    f"based on calibrated model weights."
                )
            }
        else:
            base_prob = 0.70
            if is_rural:
                base_prob -= 0.15
            if prior_risk > 0.40:
                base_prob -= 0.15
            likelihood = round(max(0.10, min(0.95, base_prob)), 3)
            return {
                "predicted_response_likelihood": likelihood,
                "will_respond_likely": likelihood >= 0.50,
                "confidence_statement": (
                    f"Rule-based baseline estimate ({likelihood*100:.1f}% likelihood). "
                    f"Trigger POST /ml/train to calibrate on DB records."
                )
            }

ml_service = ExplainableMLService()
