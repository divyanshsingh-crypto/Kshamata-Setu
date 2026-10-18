import datetime
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from app.database import Base

class EvidenceTier(str, Enum):
    E0_NONE = "E0_NONE"
    E1_SELF_REPORTED = "E1_SELF_REPORTED"
    E2_DOCUMENT_SUPPORTED = "E2_DOCUMENT_SUPPORTED"
    E3_EMPLOYER_CONFIRMED = "E3_EMPLOYER_CONFIRMED"
    E5_OFFICER_VERIFIED = "E5_OFFICER_VERIFIED"
    REJECTED_OR_DISPUTED = "REJECTED_OR_DISPUTED"

class Provider(Base):
    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    district = Column(String(100), nullable=False)

    courses = relationship("Course", back_populates="provider", cascade="all, delete-orphan")

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    sector = Column(String(100), nullable=False, index=True)  # e.g., Healthcare, Automotive, IT
    skill_tags = Column(String(255), nullable=True)          # comma-separated
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False)

    provider = relationship("Provider", back_populates="courses")
    trainees = relationship("Trainee", back_populates="course")

class Trainee(Base):
    __tablename__ = "trainees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    # NEVER store raw phone. Store salted SHA-256 hash.
    phone_hash = Column(String(64), nullable=False, index=True)
    # Salted-hash generated MSID (Maharashtra Skill Identity)
    msid = Column(String(64), unique=True, nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    district = Column(String(100), nullable=False, index=True)
    consent_outcome_followup = Column(Boolean, default=False, nullable=False)
    consent_employer_contact = Column(Boolean, default=False, nullable=False)
    withdrawn = Column(Boolean, default=False, nullable=False, index=True)
    consent_timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    course = relationship("Course", back_populates="trainees")
    follow_up_records = relationship("FollowUpRecord", back_populates="trainee", cascade="all, delete-orphan")

class FollowUpRecord(Base):
    __tablename__ = "follow_up_records"

    id = Column(Integer, primary_key=True, index=True)
    trainee_id = Column(Integer, ForeignKey("trainees.id"), nullable=False)
    interval_label = Column(String(50), default="30_DAYS", nullable=False) # 30_DAYS, 90_DAYS, 180_DAYS
    channel = Column(String(50), default="SMS", nullable=False)            # SMS, WHATSAPP
    sent_timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    response_timestamp = Column(DateTime, nullable=True)
    evidence_tier = Column(String(50), default=EvidenceTier.E0_NONE.value, nullable=False, index=True)
    employer_name = Column(String(255), nullable=True)
    wage_band = Column(String(50), nullable=True)                         # e.g., "<10k", "10k-15k", "15k-25k", ">25k"
    non_placement_reason = Column(Text, nullable=True)                    # Free text reason for seeking/non-placement
    reported_skill_gap = Column(Text, nullable=True)                      # Free text skill trainee felt they lacked
    risk_score = Column(Float, default=0.0, nullable=False)

    trainee = relationship("Trainee", back_populates="follow_up_records")
    employer_validation = relationship("EmployerValidation", back_populates="follow_up", uselist=False, cascade="all, delete-orphan")

class EmployerValidation(Base):
    __tablename__ = "employer_validations"

    id = Column(Integer, primary_key=True, index=True)
    follow_up_id = Column(Integer, ForeignKey("follow_up_records.id"), nullable=False, unique=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    confirmed = Column(Boolean, nullable=True)                            # None = pending, True = confirmed, False = rejected
    confirmed_timestamp = Column(DateTime, nullable=True)                 # Locked once set for audit trail

    follow_up = relationship("FollowUpRecord", back_populates="employer_validation")
