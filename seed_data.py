import random
from datetime import datetime, timedelta
from faker import Faker
from app.database import engine, SessionLocal, Base
from app.models import Provider, Course, Trainee, FollowUpRecord, EmployerValidation, EvidenceTier
from app.security import hash_phone, generate_msid

fake = Faker('en_IN')
Faker.seed(42)
random.seed(42)

DISTRICTS = [
    "Pune", "Nagpur", "Aurangabad", "Nashik", "Gadchiroli",
    "Thane", "Amravati", "Nanded", "Kolhapur", "Solapur"
]

EMPLOYERS = [
    "Tata Motors Service Center",
    "Apollo Clinic & Diagnostics",
    "Suzlon CleanTech Solutions",
    "Avenue Supermarts (DMart)",
    "Infosys BPM Services",
    "Bajaj Auto Authorized Workshop",
    "Reliance Retail Logistics",
    "Mahindra Agri Tech Hub"
]

WAGE_BANDS = ["<12k", "12k-18k", "18k-25k", "25k-35k", ">35k"]

NON_PLACEMENT_REASONS = [
    "Relocation constraint due to family responsibilities in hometown",
    "Offered wage below local transport and accommodation living cost",
    "Night shift timings incompatible with public transit availability",
    "Apprenticeship pool interview result delayed by employer",
    "Lack of commercial four-wheeler driving license required by employer"
]

SKILL_GAPS = [
    "Hands-on practice with modern computerized OBD diagnostics tools",
    "Conversational English and workplace interpersonal communication",
    "Advanced Tally Prime GST reconciliation and filing modules",
    "High-voltage solar grid inverter troubleshooting certification",
    "Electronic health records (EHR) entry software workflow"
]

def seed():
    print("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("Clearing existing data for idempotent re-seed...")
    db.query(EmployerValidation).delete()
    db.query(FollowUpRecord).delete()
    db.query(Trainee).delete()
    db.query(Course).delete()
    db.query(Provider).delete()
    db.commit()

    # 1. Create 3 Training Providers
    print("Creating 3 Training Providers...")
    p1 = Provider(name="Maharashtra State Skill Development Society (MSSDS) - Pune Hub", district="Pune")
    p2 = Provider(name="Vidarbha Vocational & Technical Training Institute", district="Nagpur")
    p3 = Provider(name="Marathwada Agricultural & Industrial Skilling Centre", district="Aurangabad")
    db.add_all([p1, p2, p3])
    db.commit()

    # 2. Create 5 Courses across diverse sectors
    print("Creating 5 Courses...")
    c1 = Course(name="Automotive Diagnostics & EV Servicing", sector="Automotive", skill_tags="EV, Diagnostics, CAN-bus", provider_id=p1.id)
    c2 = Course(name="Solar PV Installation & Maintenance", sector="Solar & Renewable", skill_tags="Solar PV, Inverters, Grid-Tied", provider_id=p1.id)
    c3 = Course(name="Emergency Medical Assistant & Patient Care", sector="Healthcare", skill_tags="First Aid, Patient Care, Vitals", provider_id=p2.id)
    c4 = Course(name="Retail Sales Associate & Logistics", sector="Retail & Logistics", skill_tags="POS, Inventory, Customer Handling", provider_id=p2.id)
    c5 = Course(name="Digital Office Operations & Tally ERP", sector="Information Technology", skill_tags="Tally Prime, Excel, Office Suite", provider_id=p3.id)
    courses = [c1, c2, c3, c4, c5]
    db.add_all(courses)
    db.commit()

    # 3. Create 40 Trainees
    print("Creating 40 simulated Trainees with privacy-first hashes...")
    trainees = []
    for i in range(40):
        # 10-digit Indian simulated phone
        sim_phone = f"98{random.randint(10000000, 99999999)}"
        course_choice = random.choice(courses)
        dist_choice = random.choice(DISTRICTS)
        
        # 2 trainees with withdrawn consent to test the gate
        is_withdrawn = (i == 38 or i == 39)
        consent_outcomes = not is_withdrawn

        t = Trainee(
            name=fake.name(),
            phone_hash=hash_phone(sim_phone),
            msid=generate_msid(sim_phone),
            course_id=course_choice.id,
            district=dist_choice,
            consent_outcome_followup=consent_outcomes,
            consent_employer_contact=consent_outcomes,
            withdrawn=is_withdrawn,
            consent_timestamp=datetime.utcnow() - timedelta(days=random.randint(30, 180))
        )
        trainees.append((t, sim_phone))
        db.add(t)

    db.commit()
    for t, _ in trainees:
        db.refresh(t)

    # 4. Generate FollowUpRecords & EmployerValidations
    print("Generating simulated FollowUpRecords with realistic evidence tiers and skill gaps...")
    for idx, (t, sim_phone) in enumerate(trainees):
        if t.withdrawn:
            continue

        # Trainees 0 to 24 respond; trainees 25 to 37 are in E0_NONE (unresolved follow-up)
        has_responded = (idx < 25)
        is_rural = t.district.lower() in ["gadchiroli", "nanded", "amravati"]
        risk_score = round(0.20 + (0.15 if is_rural else 0.0) + random.uniform(-0.05, 0.10), 2)
        risk_score = max(0.05, min(0.95, risk_score))

        sent_time = datetime.utcnow() - timedelta(days=random.randint(10, 45))
        resp_time = sent_time + timedelta(hours=random.randint(2, 48)) if has_responded else None

        if not has_responded:
            # E0_NONE (Unresolved outreach - never counted as unemployed)
            f_record = FollowUpRecord(
                trainee_id=t.id,
                interval_label="30_DAYS",
                channel=random.choice(["SMS", "WHATSAPP"]),
                sent_timestamp=sent_time,
                response_timestamp=None,
                evidence_tier=EvidenceTier.E0_NONE.value,
                employer_name=None,
                wage_band=None,
                non_placement_reason=None,
                reported_skill_gap=None,
                risk_score=risk_score
            )
            db.add(f_record)
        else:
            # Responded: 15 Placed (8 E3 confirmed, 7 E1 self-reported), 10 Seeking/Unplaced
            is_placed = (idx < 15)
            if is_placed:
                emp_name = random.choice(EMPLOYERS)
                wage = random.choice(WAGE_BANDS)
                # First 8 get E3 Employer Confirmed, next 7 stay E1 Self-Reported
                is_employer_confirmed = (idx < 8)
                tier = EvidenceTier.E3_EMPLOYER_CONFIRMED.value if is_employer_confirmed else EvidenceTier.E1_SELF_REPORTED.value

                f_record = FollowUpRecord(
                    trainee_id=t.id,
                    interval_label=random.choice(["30_DAYS", "90_DAYS"]),
                    channel=random.choice(["SMS", "WHATSAPP"]),
                    sent_timestamp=sent_time,
                    response_timestamp=resp_time,
                    evidence_tier=tier,
                    employer_name=emp_name,
                    wage_band=wage,
                    non_placement_reason=None,
                    reported_skill_gap=None,
                    risk_score=risk_score
                )
                db.add(f_record)
                db.commit()
                db.refresh(f_record)

                # Create EmployerValidation token
                token_str = f"audit_token_{t.id}_{random.randint(100000, 999999)}"
                val = EmployerValidation(
                    follow_up_id=f_record.id,
                    token=token_str,
                    confirmed=True if is_employer_confirmed else None,
                    confirmed_timestamp=(resp_time + timedelta(hours=12)) if is_employer_confirmed else None
                )
                db.add(val)
            else:
                # Trainee seeking employment -> Record rich reasons and skill gaps
                reason = random.choice(NON_PLACEMENT_REASONS)
                gap = random.choice(SKILL_GAPS)
                f_record = FollowUpRecord(
                    trainee_id=t.id,
                    interval_label=random.choice(["30_DAYS", "90_DAYS"]),
                    channel=random.choice(["SMS", "WHATSAPP"]),
                    sent_timestamp=sent_time,
                    response_timestamp=resp_time,
                    evidence_tier=EvidenceTier.E1_SELF_REPORTED.value,
                    employer_name=None,
                    wage_band=None,
                    non_placement_reason=reason,
                    reported_skill_gap=gap,
                    risk_score=risk_score
                )
                db.add(f_record)

    db.commit()
    print("Database seeding completed successfully!")
    print(f"Total Trainees: {db.query(Trainee).count()}")
    print(f"Total FollowUpRecords: {db.query(FollowUpRecord).count()}")
    print(f"Total EmployerValidations: {db.query(EmployerValidation).count()}")
    db.close()

if __name__ == "__main__":
    seed()
