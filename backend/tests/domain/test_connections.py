"""Scopes for connecting your own AI (ADR-0047 C, mcp-threat-model.md M7)."""

from training_coach.domain.connections import HEALTH, LABELS, OPT_IN, Scope, grant, parse, text


def test_scopes_are_parsed_in_a_fixed_order() -> None:
    assert parse("readiness:read training:read") == [Scope.TRAINING, Scope.READINESS]
    assert parse(None) == list(Scope)
    assert parse("  ") == list(Scope)


def test_an_unknown_scope_refuses_the_lot() -> None:
    assert parse("training:read log:write") is None
    assert parse("offline_access") is None


def test_a_grant_is_what_was_asked_for_and_ticked() -> None:
    asked = ["training:read", "body:read"]
    assert grant(asked, ["training:read", "readiness:read"]) == [Scope.TRAINING]
    assert grant(asked, []) == []
    assert text(grant(asked, asked)) == "training:read body:read"


def test_health_scopes_are_named_as_health_data() -> None:
    assert {Scope.BODY, Scope.READINESS} == HEALTH
    assert all("health data" in LABELS[s] for s in HEALTH)
    assert "health" not in LABELS[Scope.TRAINING]


def test_proposing_logs_is_opt_in_and_says_nothing_saves_without_a_tap() -> None:
    """ADR-0058: like the health scopes, ``log:propose`` starts unticked."""
    assert {Scope.BODY, Scope.READINESS, Scope.PROPOSE} == OPT_IN
    assert "Nothing is saved until you tap Save" in LABELS[Scope.PROPOSE]
