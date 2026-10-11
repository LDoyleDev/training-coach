"""The OAuth server for "Connect my AI" (ADR-0047 C): discovery, bounded registration,
authorization with PKCE and resource indicators, the passkey-gated consent page and the token
endpoint. Requirements 4-10, 16 and 18 of docs/security/mcp-threat-model.md."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests import oauth_flow as flow
from tests.oauth_flow import ALL, CALLBACK, MCP, ORIGIN
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.session import make_session_factory
from training_coach.services import auth
from training_coach.services.users import OWNER


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    with flow.app_client(engine) as test_client:
        yield test_client


@pytest.fixture
def proved(client: TestClient, engine: Engine) -> TestClient:
    """Signed in with a passkey just now: the consent page may be approved."""
    flow.sign_in_with_passkey(client, flow.add_passkey(client, engine))
    return client


# ----------------------------------------------------------------------- discovery


def test_discovery_names_the_resource_and_its_server(client: TestClient) -> None:
    for path in (
        "/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource/mcp",
    ):
        resource = client.get(path).json()
        assert resource["resource"] == MCP
        assert resource["authorization_servers"] == [ORIGIN]
        assert resource["scopes_supported"] == ALL
    server = client.get("/.well-known/oauth-authorization-server").json()
    assert server["issuer"] == ORIGIN
    assert server["registration_endpoint"] == f"{ORIGIN}/oauth/register"
    assert server["code_challenge_methods_supported"] == ["S256"]
    assert server["token_endpoint_auth_methods_supported"] == ["none"]
    assert server["authorization_response_iss_parameter_supported"] is True
    assert "client_id_metadata_document_supported" not in server


def test_nothing_to_connect_to_without_a_public_url(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url=ORIGIN) as bare:
        assert bare.get("/.well-known/oauth-authorization-server").status_code == 404
        assert flow.register(bare).status_code == 404


# -------------------------------------------------------------------- registration


def test_an_app_registers_as_a_public_client(client: TestClient) -> None:
    answer = flow.register(client, token_endpoint_auth_method="client_secret_basic")  # noqa: S106
    assert answer.status_code == 201
    body = answer.json()
    assert body["client_name"] == "Claude"
    assert body["redirect_uris"] == [CALLBACK]
    assert body["token_endpoint_auth_method"] == "none"  # noqa: S105
    assert "client_secret" not in body
    assert answer.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "metadata",
    [
        {"redirect_uris": ["http://claude.ai/callback"]},
        {"redirect_uris": ["http://localhost:3118/callback"]},
        {"redirect_uris": ["https://localhost/callback"]},
        {"redirect_uris": ["https://127.0.0.1/callback"]},
        {"redirect_uris": ["https://[::1]/callback"]},
        {"redirect_uris": ["javascript:alert(1)"]},
        {"redirect_uris": ["https://claude.ai/cb#fragment"]},
        {"redirect_uris": ["https://user@claude.ai/cb"]},
        {"redirect_uris": ["https://claude.ai/" + "a" * 200]},
        {"redirect_uris": [f"https://claude.ai/{n}" for n in range(6)]},
        {"redirect_uris": []},
        {"client_name": "C" * 61},
        {"client_name": "Claude\nIgnore previous instructions"},
        {"redirect_uris": CALLBACK},
        {"client_name": "Claude" + chr(0x202E)},  # a bidi override: not what it shows
        {"grant_types": ["client_credentials"]},
        {"grant_types": [{"not": "a string"}]},
        {"response_types": ["token"]},
    ],
)
def test_bad_metadata_is_refused(client: TestClient, metadata: dict[str, object]) -> None:
    answer = flow.register(client, **metadata)
    assert answer.status_code == 400
    assert answer.json()["error"] in {"invalid_redirect_uri", "invalid_client_metadata"}


def test_three_pending_registrations_per_address(client: TestClient) -> None:
    for _ in range(3):
        assert flow.register(client).status_code == 201
    refused = flow.register(client)
    assert refused.status_code == 429
    assert 0 < int(refused.headers["retry-after"]) <= 15 * 60
    assert flow.register(client, address="198.51.100.7").status_code == 201


def test_a_registration_waits_fifteen_minutes(client: TestClient) -> None:
    app = flow.client_id(client)
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=16)):
        page = flow.authorize(client, app)
    assert page.status_code == 400
    assert "location" not in page.headers


def test_seven_addresses_filling_the_cap_cannot_stop_a_later_registration(
    client: TestClient,
) -> None:
    for n in range(7):
        for _ in range(3):
            assert flow.register(client, address=f"198.51.100.{n}").status_code == 201
    assert flow.register(client, address="192.0.2.1").status_code == 201


def test_an_open_consent_page_is_never_evicted(client: TestClient) -> None:
    app = flow.client_id(client)
    flow.handle(client, app)  # the person is on the consent page
    for n in range(20):
        assert flow.register(client, address=f"198.51.100.{n}").status_code == 201
    assert flow.authorize(client, app).status_code == 303  # still registered


def test_twenty_open_consent_pages_refuse_a_new_registration(client: TestClient) -> None:
    for n in range(20):
        app = flow.client_id(client, address=f"198.51.100.{n}")
        flow.handle(client, app, browser=f"198.51.100.{n}")
    refused = flow.register(client, address="192.0.2.1")
    assert refused.status_code == 429
    assert 0 < int(refused.headers["retry-after"]) <= 10 * 60


def test_approved_apps_do_not_count_toward_the_cap(proved: TestClient) -> None:
    app = flow.client_id(proved)
    assert flow.approve(proved, flow.handle(proved, app), app).status_code == 200
    for n in range(19):
        app = flow.client_id(proved, address=f"198.51.100.{n}")
        flow.handle(proved, app, browser=f"198.51.100.{n}")
    assert flow.register(proved, address="192.0.2.1").status_code == 201  # the 20th waiting


# ------------------------------------------------------------- open consent pages (M11)


def test_one_app_at_its_cap_does_not_stop_another(client: TestClient) -> None:
    """A fourth page for one app replaces its oldest unbound one; another app is unaffected."""
    busy, other = flow.client_id(client), flow.client_id(client, address="198.51.100.1")
    first = flow.handle(client, busy, browser="192.0.2.1")
    for n in range(2, 5):
        flow.handle(client, busy, browser=f"192.0.2.{n}")
    assert client.post("/api/connect/details", json={"handle": first}).status_code == 404
    assert flow.authorize(client, other, browser="192.0.2.9").status_code == 303


def test_a_page_the_person_has_bound_is_never_replaced(proved: TestClient) -> None:
    app = flow.client_id(proved)
    mine = flow.handle(proved, app)
    assert proved.post("/api/connect/bind", json={"handle": mine}).status_code == 204
    for n in range(1, 6):  # someone who knows the app's id keeps opening pages for it
        flow.handle(proved, app, browser=f"192.0.2.{n}")
    assert flow.approve(proved, mine, app).status_code == 200


def test_an_app_whose_three_pages_are_all_bound_is_refused(proved: TestClient) -> None:
    app = flow.client_id(proved)
    for n in range(3):
        consent = flow.handle(proved, app, browser=f"192.0.2.{n}")
        assert proved.post("/api/connect/bind", json={"handle": consent}).status_code == 204
    refused = flow.authorize(proved, app, browser="192.0.2.9")
    assert refused.status_code == 429
    assert "location" not in refused.headers


def test_one_address_cannot_fill_the_overall_cap(client: TestClient) -> None:
    """Three open pages per address: the fourth is refused, so one caller holds at most 3 of
    the 40, and keeps at most 3 waiting registrations safe from eviction."""
    apps = [flow.client_id(client, address=f"198.51.100.{n}") for n in range(5)]
    for app in apps[:3]:
        flow.handle(client, app, browser="192.0.2.66")
    refused = flow.authorize(client, apps[3], browser="192.0.2.66")
    assert refused.status_code == 429
    assert "location" not in refused.headers
    assert flow.authorize(client, apps[4]).status_code == 303  # the person still can


def test_an_open_page_protects_a_registration_for_a_bounded_time(client: TestClient) -> None:
    """New pages need a registration still in its 15 minutes, and a page lasts 10: a flood of
    pages can't keep a registration from eviction for more than 25 minutes."""
    start = datetime.now(UTC)
    held = flow.client_id(client)
    with time_machine.travel(start + timedelta(minutes=14)):
        flow.handle(client, held)
    with time_machine.travel(start + timedelta(minutes=16)):
        assert flow.authorize(client, held).status_code == 400  # expired: no new page
    with time_machine.travel(start + timedelta(minutes=25)):
        for n in range(20):
            assert flow.register(client, address=f"198.51.100.{n}").status_code == 201
        assert flow.authorize(client, held).status_code == 400  # evicted with its pages


# ----------------------------------------------------------------------- authorize


def test_an_authorization_request_opens_the_consent_page(client: TestClient) -> None:
    answer = flow.authorize(client, flow.client_id(client))
    assert answer.status_code == 303
    assert answer.headers["location"].startswith("/connect#")
    assert answer.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "redirect",
    [
        CALLBACK + "/",
        CALLBACK + "x",
        CALLBACK[:-1],
        CALLBACK + "?next=evil",
        CALLBACK + "#frag",
        CALLBACK.replace("https", "http"),
        "https://evil.example/api/mcp/auth_callback",
        "javascript:alert(1)",
        "http://localhost:3118/callback",
        None,
    ],
)
def test_an_unregistered_address_gets_an_error_page_and_no_redirect(
    client: TestClient, redirect: str | None
) -> None:
    page = flow.authorize(client, flow.client_id(client), redirect_uri=redirect)
    assert page.status_code == 400
    assert "location" not in page.headers
    assert "Nothing was shared" in page.text
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]


def test_an_unknown_app_gets_an_error_page(client: TestClient) -> None:
    page = flow.authorize(client, "nobody-registered-this")
    assert page.status_code == 400
    assert "location" not in page.headers


def test_a_hostile_name_is_escaped_on_the_error_page(client: TestClient) -> None:
    page = flow.authorize(client, "<script>alert(1)</script>")
    assert "<script>" not in page.text


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"code_challenge_method": None}, "invalid_request"),
        ({"code_challenge_method": "plain"}, "invalid_request"),
        ({"code_challenge": None}, "invalid_request"),
        ({"code_challenge": "too-short"}, "invalid_request"),
        ({"resource": None}, "invalid_target"),
        ({"resource": "https://other.example/mcp"}, "invalid_target"),
        ({"scope": "training:read log:propose"}, "invalid_scope"),
        ({"response_type": "token"}, "unsupported_response_type"),
    ],
)
def test_a_bad_request_is_sent_back_to_the_registered_address(
    client: TestClient, change: dict[str, str | None], error: str
) -> None:
    answer = flow.authorize(client, flow.client_id(client), **change)
    assert answer.status_code == 302
    location = answer.headers["location"]
    assert location.startswith(CALLBACK + "?")
    assert flow.query(location) == {"error": error, "state": "st-1", "iss": ORIGIN}


def test_authorize_is_limited_per_address(client: TestClient) -> None:
    for _ in range(30):
        client.get("/oauth/authorize", headers={"cf-connecting-ip": "192.0.2.9"})
    limited = client.get("/oauth/authorize", headers={"cf-connecting-ip": "192.0.2.9"})
    assert limited.status_code == 429
    assert "retry-after" in limited.headers
    assert (
        client.get("/oauth/authorize", headers={"cf-connecting-ip": "192.0.2.10"}).status_code
        == 400
    )


# --------------------------------------------------------------------- consent page


def test_the_consent_page_names_the_app_as_a_claim_and_where_it_goes(client: TestClient) -> None:
    app = flow.client_id(client)
    details = client.post("/api/connect/details", json={"handle": flow.handle(client, app)})
    assert details.status_code == 200
    assert details.json() == {
        "client_id": app,
        "client_name": "Claude",
        "redirect_uri": CALLBACK,
        "redirect_host": "claude.ai",
        "scopes": [
            {
                "scope": "training:read",
                "label": details.json()["scopes"][0]["label"],
                "health": False,
            },
            {"scope": "body:read", "label": details.json()["scopes"][1]["label"], "health": True},
            {
                "scope": "readiness:read",
                "label": details.json()["scopes"][2]["label"],
                "health": True,
            },
        ],
    }
    gone = client.post("/api/connect/details", json={"handle": "x" * 43})
    assert gone.status_code == 404


def test_approving_sends_the_code_state_and_issuer_back(proved: TestClient) -> None:
    app = flow.client_id(proved)
    approved = flow.approve(proved, flow.handle(proved, app), app)
    assert approved.status_code == 200
    redirect = approved.json()["redirect"]
    assert redirect.startswith(CALLBACK + "?")
    sent = flow.query(redirect)
    assert set(sent) == {"code", "state", "iss"}
    assert (sent["state"], sent["iss"]) == ("st-1", ORIGIN)


def test_health_scopes_are_granted_only_when_ticked(proved: TestClient) -> None:
    app = flow.client_id(proved)
    approved = flow.approve(proved, flow.handle(proved, app), app, ["training:read"])
    code = flow.query(approved.json()["redirect"])["code"]
    with flow.no_cookies(proved):
        assert flow.exchange(proved, app, code).json()["scope"] == "training:read"


def test_ticks_cannot_add_what_the_app_did_not_ask_for(proved: TestClient) -> None:
    app = flow.client_id(proved)
    consent = flow.handle(proved, app, scope="training:read")
    approved = flow.approve(proved, consent, app, ALL)
    code = flow.query(approved.json()["redirect"])["code"]
    with flow.no_cookies(proved):
        assert flow.exchange(proved, app, code).json()["scope"] == "training:read"


def test_nothing_ticked_is_refused(proved: TestClient) -> None:
    app = flow.client_id(proved)
    assert flow.approve(proved, flow.handle(proved, app), app, []).status_code == 400


def test_a_session_from_a_bot_link_cannot_approve(client: TestClient, engine: Engine) -> None:
    flow.sign_in_with_link(client, engine)
    app = flow.client_id(client)
    consent = flow.handle(client, app)
    assert client.post("/api/connect/bind", json={"handle": consent}).status_code == 403


def test_a_session_from_recover_cannot_approve(client: TestClient, engine: Engine) -> None:
    flow.add_passkey(client, engine)
    with make_session_factory(engine, user_id=OWNER)() as bound:
        link = auth.create_link(bound, datetime.now(UTC), purpose=auth.RECOVER)
        bound.commit()
    assert client.post("/api/auth/redeem", json={"token": link}).status_code == 204
    consent = flow.handle(client, flow.client_id(client))
    assert client.post("/api/connect/bind", json={"handle": consent}).status_code == 403


def test_a_stale_passkey_sign_in_cannot_approve(proved: TestClient) -> None:
    app = flow.client_id(proved)
    consent = flow.handle(proved, app)
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=11)):
        assert proved.post("/api/connect/bind", json={"handle": consent}).status_code == 403


def test_signed_out_cannot_approve(client: TestClient) -> None:
    consent = flow.handle(client, flow.client_id(client))
    assert client.post("/api/connect/bind", json={"handle": consent}).status_code == 401


def test_a_handle_bound_to_another_browser_is_refused(proved: TestClient, engine: Engine) -> None:
    app = flow.client_id(proved)
    consent = flow.handle(proved, app)
    assert proved.post("/api/connect/bind", json={"handle": consent}).status_code == 204
    with make_session_factory(engine, user_id=OWNER)() as bound:
        other = auth.start_session(bound, OWNER, datetime.now(UTC), "Other", passkey_id=1)
        bound.commit()
    mine = proved.cookies.get("__Host-tc_session")
    proved.cookies.set("__Host-tc_session", other)
    assert proved.post("/api/connect/bind", json={"handle": consent}).status_code == 409
    body = {"handle": consent, "client_id": app, "redirect_uri": CALLBACK, "scopes": ALL}
    assert proved.post("/api/connect/approve", json=body).status_code == 400
    proved.cookies.set("__Host-tc_session", mine or "")


@pytest.mark.parametrize(
    "change", [{"client_id": "someone-else"}, {"redirect_uri": CALLBACK + "?x=1"}]
)
def test_a_handle_replayed_with_changed_parameters_is_refused(
    proved: TestClient, change: dict[str, str]
) -> None:
    app = flow.client_id(proved)
    consent = flow.handle(proved, app)
    assert flow.approve(proved, consent, app, **change).status_code == 400
    assert flow.approve(proved, consent, app).status_code == 200  # the real one still can


def test_a_handle_is_single_use(proved: TestClient) -> None:
    app = flow.client_id(proved)
    consent = flow.handle(proved, app)
    assert flow.approve(proved, consent, app).status_code == 200
    body = {"handle": consent, "client_id": app, "redirect_uri": CALLBACK, "scopes": ALL}
    assert proved.post("/api/connect/approve", json=body).status_code == 400


def test_a_cross_site_approval_is_refused(proved: TestClient) -> None:
    app = flow.client_id(proved)
    consent = flow.handle(proved, app)
    body = {"handle": consent, "client_id": app, "redirect_uri": CALLBACK, "scopes": ALL}
    for headers in ({"origin": "https://evil.example"}, {"sec-fetch-site": "cross-site"}):
        answer = proved.post("/api/connect/approve", json=body, headers=headers)
        assert answer.status_code == 403


def test_a_new_connection_is_alerted_with_its_claimed_name_and_host(proved: TestClient) -> None:
    sent = flow.alerts(proved)
    app = flow.client_id(proved)
    flow.approve(proved, flow.handle(proved, app), app)
    assert len(sent) == 1
    assert 'calls itself "Claude"' in sent[0]
    assert "claude.ai" in sent[0]


def test_turning_it_down_sends_access_denied(client: TestClient) -> None:
    consent = flow.handle(client, flow.client_id(client))
    denied = client.post("/api/connect/deny", json={"handle": consent})
    assert flow.query(denied.json()["redirect"]) == {
        "error": "access_denied",
        "state": "st-1",
        "iss": ORIGIN,
    }
    assert client.post("/api/connect/deny", json={"handle": consent}).status_code == 404


# --------------------------------------------------------------------------- token


def test_the_whole_flow_gives_tokens(client: TestClient, engine: Engine) -> None:
    _, tokens = flow.connect(client, engine)
    assert tokens["token_type"] == "Bearer"  # noqa: S105
    assert tokens["expires_in"] == 3600
    assert tokens["scope"] == "training:read"


def _code(proved: TestClient) -> tuple[str, str]:
    app = flow.client_id(proved)
    approved = flow.approve(proved, flow.handle(proved, app), app)
    return app, flow.query(approved.json()["redirect"])["code"]


@pytest.mark.parametrize(
    "change",
    [
        {"code_verifier": "cd" * 22},
        {"redirect_uri": CALLBACK + "?x=1"},
        {"resource": "https://other.example/mcp"},
    ],
)
def test_a_code_needs_its_verifier_address_and_resource(
    proved: TestClient, change: dict[str, str]
) -> None:
    app, code = _code(proved)
    with flow.no_cookies(proved):
        answer = flow.exchange(proved, app, code, **change)
    assert answer.status_code == 400
    assert answer.json()["error"] in {"invalid_grant", "invalid_target"}


def test_a_code_exchanged_by_another_client_is_refused(proved: TestClient) -> None:
    app, code = _code(proved)
    other = flow.client_id(proved, address="198.51.100.1")
    with flow.no_cookies(proved):
        assert flow.exchange(proved, other, code).json() == {"error": "invalid_grant"}
        assert flow.exchange(proved, app, code).status_code == 400  # used up


def test_an_unknown_client_is_refused(proved: TestClient) -> None:
    _, code = _code(proved)
    with flow.no_cookies(proved):
        answer = flow.exchange(proved, "nobody", code)
    assert answer.status_code == 401
    assert answer.json() == {"error": "invalid_client"}


def test_the_token_endpoint_takes_a_form_only(proved: TestClient) -> None:
    app, code = _code(proved)
    with flow.no_cookies(proved):
        as_json = proved.post("/oauth/token", json={"grant_type": "authorization_code"})
        twice = proved.post(
            "/oauth/token",
            content=f"grant_type=authorization_code&code={code}&code={code}&client_id={app}",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        odd = flow.exchange(proved, app, code, grant_type="password")
    assert as_json.json() == {"error": "invalid_request"}
    assert twice.json() == {"error": "invalid_request"}
    assert odd.json() == {"error": "unsupported_grant_type"}


def test_a_refresh_rotates_and_a_reused_one_revokes_and_alerts(
    client: TestClient, engine: Engine
) -> None:
    app, tokens = flow.connect(client, engine)
    sent = flow.alerts(client)
    with flow.no_cookies(client):
        rotated = flow.refresh(client, app, tokens["refresh_token"])
        assert rotated.status_code == 200
        assert rotated.headers["cache-control"] == "no-store"
        assert rotated.json()["refresh_token"] != tokens["refresh_token"]
        reused = flow.refresh(client, app, tokens["refresh_token"])
        assert reused.json() == {"error": "invalid_grant"}
        assert flow.refresh(client, app, rotated.json()["refresh_token"]).status_code == 400
    assert len(sent) == 1
    assert "used twice" in sent[0]


def test_a_refresh_by_another_client_revokes_and_alerts(client: TestClient, engine: Engine) -> None:
    app, tokens = flow.connect(client, engine)
    other = flow.client_id(client, address="198.51.100.1")
    sent = flow.alerts(client)
    with flow.no_cookies(client):
        stolen = flow.refresh(client, other, tokens["refresh_token"])
        assert stolen.json() == {"error": "invalid_grant"}
        assert "access_token" not in stolen.json()
        assert flow.refresh(client, app, tokens["refresh_token"]).status_code == 400
    assert len(sent) == 1


def test_token_requests_are_limited_per_address(client: TestClient) -> None:
    for _ in range(30):
        flow.refresh(client, "nobody", "x")
    assert flow.refresh(client, "nobody", "x").status_code == 429
    other = client.post(
        "/oauth/token", data={"grant_type": "x"}, headers={"cf-connecting-ip": "192.0.2.10"}
    )
    assert other.status_code == 401  # another address isn't limited
