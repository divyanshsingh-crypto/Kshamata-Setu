import os
import time
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from jose import jwt, JWTError

SALT_SECRET = os.getenv("SALT_SECRET", "kshamata_audit_salt_2026_maharashtra_secure")
JWT_SECRET = os.getenv("JWT_SECRET", "kshamata-jwt-super-secret-key-national-finale-2026")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

def hash_phone(phone: str) -> str:
    """Hash raw phone with server salt so raw PII is never stored in DB."""
    clean_phone = "".join(filter(str.isdigit, phone))
    return hashlib.sha256(f"{clean_phone}:{SALT_SECRET}".encode("utf-8")).hexdigest()

def generate_msid(phone: str) -> str:
    """
    Generates Maharashtra Skill Identity (MSID).
    Salted SHA-256 of phone + random nonce + timestamp.
    Never Aadhaar-based. Fully pseudonymized and non-reversible.
    """
    clean_phone = "".join(filter(str.isdigit, phone))
    nonce = secrets.token_hex(8)
    ts = str(int(time.time()))
    digest = hashlib.sha256(f"{clean_phone}:{nonce}:{ts}:{SALT_SECRET}".encode("utf-8")).hexdigest()
    return f"MSID-{digest[:16].upper()}"

def mask_phone(phone: str) -> str:
    """Mask phone for safe logging and UI display (e.g. ******3456)."""
    clean = "".join(filter(str.isdigit, phone))
    if len(clean) >= 4:
        return f"+91 ******{clean[-4:]}"
    return "******"

class OTPManager:
    """
    In-memory OTP manager for MVP.
    Provides 6-digit cryptographically random OTP, 5-minute TTL, single-use invalidation.
    Production note: For distributed multi-instance deployment, replace with Redis.
    """
    def __init__(self):
        # Key: hashed_phone -> (otp_code, expires_at_timestamp)
        self._store: Dict[str, Tuple[str, float]] = {}

    def generate_otp(self, phone: str, ttl_seconds: int = 300) -> str:
        clean_phone = "".join(filter(str.isdigit, phone))
        code = f"{secrets.randbelow(900000) + 100000}"  # 6-digit numeric string
        expires_at = time.time() + ttl_seconds
        h = hash_phone(clean_phone)
        self._store[h] = (code, expires_at)
        return code

    def verify_and_consume_otp(self, phone: str, candidate_code: str) -> bool:
        clean_phone = "".join(filter(str.isdigit, phone))
        h = hash_phone(clean_phone)
        entry = self._store.get(h)
        if not entry:
            return False

        stored_code, expires_at = entry
        if time.time() > expires_at:
            # Expired
            self._store.pop(h, None)
            return False

        if secrets.compare_digest(stored_code, candidate_code.strip()):
            # Single-use: delete once consumed
            self._store.pop(h, None)
            return True

        return False

    def peek_otp(self, phone: str) -> Optional[str]:
        """Convenience method for testing/demo visibility without consuming."""
        clean_phone = "".join(filter(str.isdigit, phone))
        h = hash_phone(clean_phone)
        entry = self._store.get(h)
        if entry and time.time() <= entry[1]:
            return entry[0]
        return None

otp_manager = OTPManager()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
