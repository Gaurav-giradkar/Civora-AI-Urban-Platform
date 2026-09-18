from datetime import datetime, timedelta, timezone

import pytest

from app.models import Incident, IssueReobservation
from app.utils.security import create_access_token


@pytest.fixture
def admin_headers(db_session):
    from app.models import User
    from app.utils.security import hash_password

    user = User(
        name="Civora Control Room",
        email="civora-control@example.com",
        role="admin",
        password_hash=hash_password("test-password"),
    )
    db_session.add(user)
    db_session.commit()
    return {"Authorization": f"Bearer {create_access_token(str(user.id), user.role)}"}


def _payload(bus_id: str, event_id: str, observed_at: datetime, latitude: float = 19.2183, longitude: float = 72.9781):
    return {
        "event_id": event_id,
        "bus_id": bus_id,
        "route_id": "R-12",
        "observed_at": observed_at.isoformat(),
        "latitude": latitude,
        "longitude": longitude,
        "detected_class": "pothole",
        "confidence": 0.80,
        "source_metadata": {"source": "software_bus_simulator"},
        "gnss_accuracy_meters": 4.5,
    }


def test_bus_observations_create_and_corroborate_one_urban_issue(client, admin_headers):
    timestamp = datetime.now(timezone.utc)

    first = client.post("/api/observations", headers=admin_headers, json=_payload("Bus-017", "evt-017", timestamp))
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["correlation_type"] == "new_issue"
    assert first_body["observation_count"] == 1
    assert first_body["distinct_bus_count"] == 1

    second = client.post(
        "/api/observations",
        headers=admin_headers,
        json=_payload("Bus-024", "evt-024", timestamp + timedelta(minutes=2), 19.21835, 72.97815),
    )
    assert second.status_code == 201
    second_body = second.json()
    assert second_body["correlation_type"] == "corroboration"
    assert second_body["urban_issue_id"] == first_body["urban_issue_id"]
    assert second_body["observation_count"] == 2
    assert second_body["distinct_bus_count"] == 2

    third = client.post(
        "/api/observations",
        headers=admin_headers,
        json=_payload("Bus-031", "evt-031", timestamp + timedelta(minutes=4), 19.21832, 72.97812),
    )
    assert third.status_code == 201
    third_body = third.json()
    assert third_body["correlation_type"] == "corroboration"
    assert third_body["urban_issue_id"] == first_body["urban_issue_id"]
    assert third_body["observation_count"] == 3
    assert third_body["distinct_bus_count"] == 3


def test_later_observation_is_recorded_as_reobservation(client, admin_headers, db_session):
    timestamp = datetime.now(timezone.utc)
    first = client.post("/api/observations", headers=admin_headers, json=_payload("Bus-017", "evt-original", timestamp))
    issue_id = first.json()["urban_issue_id"]
    issue = db_session.get(Incident, issue_id)
    issue.status = "resolved"
    db_session.commit()

    revisit = client.post(
        "/api/observations",
        headers=admin_headers,
        json=_payload("Bus-024", "evt-revisit", timestamp + timedelta(days=2), 19.21831, 72.97811),
    )
    assert revisit.status_code == 201
    body = revisit.json()
    assert body["correlation_type"] == "reobservation"
    assert body["urban_issue_id"] == issue_id
    assert body["observation_count"] == 2
    assert db_session.query(Incident).count() == 1
    assert db_session.query(IssueReobservation).filter(IssueReobservation.urban_issue_id == issue_id).count() == 1


def test_priority_is_recalculated_after_corroboration(client, admin_headers):
    timestamp = datetime.now(timezone.utc)
    first = client.post("/api/observations", headers=admin_headers, json=_payload("Bus-017", "evt-priority-1", timestamp))
    first_body = first.json()
    second = client.post(
        "/api/observations",
        headers=admin_headers,
        json=_payload("Bus-024", "evt-priority-2", timestamp + timedelta(minutes=1)),
    )
    second_body = second.json()
    assert second_body["urban_issue_id"] == first_body["urban_issue_id"]
    assert second_body["priority_score"] > first_body["priority_score"]
    assert second_body["priority_level"] in {"low", "medium", "high", "critical"}


def test_observation_rejects_missing_token(client):
    res = client.post(
        "/api/observations",
        json=_payload("Bus-017", "evt-noauth", datetime.now(timezone.utc)),
    )
    assert res.status_code == 401


def test_observation_rejects_unauthorized_role(client, db_session):
    from app.models import User
    from app.utils.security import hash_password

    citizen = User(
        name="Citizen Jane",
        email="jane@example.com",
        role="citizen",
        password_hash=hash_password("password"),
    )
    db_session.add(citizen)
    db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(str(citizen.id), citizen.role)}"}

    res = client.post(
        "/api/observations",
        headers=headers,
        json=_payload("Bus-017", "evt-forbidden", datetime.now(timezone.utc)),
    )
    assert res.status_code == 403


def test_observation_rejects_invalid_detected_class(client, admin_headers):
    payload = _payload("Bus-017", "evt-invalid-class", datetime.now(timezone.utc))
    payload["detected_class"] = "flying_car"
    res = client.post("/api/observations", headers=admin_headers, json=payload)
    assert res.status_code == 422


def test_observation_rejects_invalid_coordinates(client, admin_headers):
    payload = _payload("Bus-017", "evt-invalid-coords", datetime.now(timezone.utc), latitude=190.0, longitude=200.0)
    res = client.post("/api/observations", headers=admin_headers, json=payload)
    assert res.status_code == 422


def test_observation_rejects_duplicate_event_id(client, admin_headers):
    t = datetime.now(timezone.utc)
    res1 = client.post("/api/observations", headers=admin_headers, json=_payload("Bus-017", "evt-dup-1", t))
    assert res1.status_code == 201

    res2 = client.post("/api/observations", headers=admin_headers, json=_payload("Bus-017", "evt-dup-1", t))
    assert res2.status_code == 409
    assert "already been ingested" in res2.json()["detail"]


def test_observation_allows_missing_optional_fields(client, admin_headers):
    minimal_payload = {
        "event_id": "evt-minimal",
        "bus_id": "Bus-999",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "latitude": 19.2183,
        "longitude": 72.9781,
        "detected_class": "pothole",
        "confidence": 0.85,
    }
    res = client.post("/api/observations", headers=admin_headers, json=minimal_payload)
    assert res.status_code == 201
    assert res.json()["correlation_type"] == "new_issue"


def test_distinct_bus_count_does_not_increment_for_same_bus(client, admin_headers):
    t = datetime.now(timezone.utc)
    first = client.post("/api/observations", headers=admin_headers, json=_payload("Bus-017", "evt-same-bus-1", t))
    assert first.status_code == 201
    assert first.json()["distinct_bus_count"] == 1
    assert first.json()["observation_count"] == 1

    second = client.post(
        "/api/observations",
        headers=admin_headers,
        json=_payload("Bus-017", "evt-same-bus-2", t + timedelta(minutes=1), 19.21831, 72.97811),
    )
    assert second.status_code == 201
    assert second.json()["distinct_bus_count"] == 1
    assert second.json()["observation_count"] == 2


def test_command_summary_and_buses_endpoints(client, admin_headers):
    summary_res = client.get("/api/observations/summary", headers=admin_headers)
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert "active_buses_count" in summary
    assert "total_observations" in summary
    assert "total_urban_issues" in summary

    buses_res = client.get("/api/observations/buses", headers=admin_headers)
    assert buses_res.status_code == 200
    assert isinstance(buses_res.json(), list)

