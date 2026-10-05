from fastapi.testclient import TestClient

from training_coach.services.seed import load_plan


def test_plan_endpoint_returns_the_week_in_queue_order(client: TestClient) -> None:
    body = client.get("/api/plan").json()
    plan = load_plan()
    assert [s["slug"] for s in body["sessions"]] == [s.slug for s in plan.sessions]
    assert [s["position"] for s in body["sessions"]] == list(range(len(plan.sessions)))
    assert {s["type"] for s in body["sessions"]} == {"strength", "conditioning", "recovery"}


def test_plan_endpoint_exercise_details(client: TestClient) -> None:
    torso = next(s for s in client.get("/api/plan").json()["sessions"] if s["slug"] == "torso")
    pull_up = next(e for e in torso["exercises"] if e["slug"] == "pull-up")
    assert pull_up["ladder"][pull_up["current_step"]] == "Strict pull-up"
    assert torso["total_sets"] == sum(e["sets"] for e in torso["exercises"])


def test_plan_endpoint_volume_excludes_qualities(client: TestClient) -> None:
    body = client.get("/api/plan").json()
    groups = {v["group"] for v in body["volume"]}
    assert "quads" in groups
    assert not groups & {"conditioning", "mobility", "power", "posture"}
    assert (body["volume_target_min"], body["volume_target_max"]) == (10, 20)


def test_plan_endpoint_has_security_headers(client: TestClient) -> None:
    response = client.get("/api/plan")
    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
