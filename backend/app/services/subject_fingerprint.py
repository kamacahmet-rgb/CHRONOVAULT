"""T.C. kimlik no → HMAC parmak izi (ham TC veritabanına yazılmaz)."""

from __future__ import annotations

import hashlib
import hmac


def normalize_tc(raw: str) -> str:
    return raw.replace(" ", "").strip()


def tc_fingerprint(secret: str, tc: str) -> str:
    """
    Sabit uzunlukta parmak izi (HMAC-SHA256 hex, 64 karakter).
    secret: SUBJECT_TC_HMAC_SECRET — üretimde KMS ile yönetilmelidir.
    """
    norm = normalize_tc(tc)
    if len(norm) != 11 or not norm.isdigit():
        raise ValueError("Geçersiz T.C. kimlik numarası formatı")
    return hmac.new(
        secret.encode("utf-8"),
        norm.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
