from __future__ import annotations

from app.utils import normalize_text


def test_normalize_wake_variants() -> None:
    variants = {
        "Oye Kay",
        "oye  kay",
        "Óye  Key",
        "oye kei",
    }
    normalized = {normalize_text(v) for v in variants}
    assert "oyekay" in normalized
    assert "oyekey" in normalized
    assert "oyekei" in normalized
