import pytest

from guard.provenance import DataSource, SourceType, build_provenance_context


def test_user_and_system_sources_are_trusted_for_authorization() -> None:
    context = build_provenance_context(
        (
            DataSource("user-request", SourceType.USER),
            DataSource("system-policy", SourceType.SYSTEM),
        )
    )

    assert context.influenced_by_untrusted_content is False
    assert context.untrusted_source_ids == ()


def test_paypal_and_third_party_sources_are_untrusted() -> None:
    context = build_provenance_context(
        (
            DataSource("invoice-001", SourceType.PAYPAL_DATA),
            DataSource("invoice-note-001", SourceType.THIRD_PARTY),
        ),
        injection_risk_score=0.8,
    )

    assert context.influenced_by_untrusted_content is True
    assert context.untrusted_source_ids == ("invoice-001", "invoice-note-001")
    assert context.injection_risk_score == 0.8


def test_invalid_risk_score_is_rejected() -> None:
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        build_provenance_context((), injection_risk_score=1.5)
