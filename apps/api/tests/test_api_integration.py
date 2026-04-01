from fastapi.testclient import TestClient

from app.main import app


def test_api_happy_path(monkeypatch):
    token_user = {"id": "u1", "organization_id": "o1", "role": "owner"}

    def fake_current_user():
        return token_user

    from app.api import deps
    app.dependency_overrides[deps.get_current_user] = fake_current_user

    from app.services import report_job_service

    monkeypatch.setattr(
        report_job_service,
        "create_report_job",
        lambda data, org, uid: {"id": "job-x", "status": "pending", "report_type": data["report_type"], "created_at": None},
    )
    monkeypatch.setattr(report_job_service, "run_report_job", lambda job_id, org_id: {"id": job_id, "status": "success"})
    monkeypatch.setattr(report_job_service, "get_report_job", lambda job_id, org_id: {"id": job_id, "status": "success", "report_type": "weekly"})
    monkeypatch.setattr(report_job_service, "get_report_markdown", lambda job_id, org_id: "## 本期聚焦\n\n- x")
    monkeypatch.setattr(report_job_service, "get_report_charts", lambda job_id, org_id: [{"chart_type": "bar", "title": "t", "labels": [], "values": [], "notes": ""}])
    monkeypatch.setattr(report_job_service, "get_report_citations", lambda job_id, org_id: [{"section_key": "focus", "source_url": "https://a.com"}])

    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/report-jobs",
        json={
            "report_type": "weekly",
            "keywords": ["AI"],
            "time_range_start": "2026-03-25T00:00:00Z",
            "time_range_end": "2026-04-01T00:00:00Z",
            "source_whitelist": ["https://example.com"],
            "template_name": "global-media-weekly-v1",
            "language": "zh-CN",
        },
    )
    assert create_resp.status_code == 200
    job_id = create_resp.json()["id"]

    run_resp = client.post(f"/api/v1/report-jobs/{job_id}/run")
    assert run_resp.status_code == 200
    assert run_resp.json()["status"] == "success"

    report_resp = client.get(f"/api/v1/reports/{job_id}/markdown")
    assert report_resp.status_code == 200
    assert "本期聚焦" in report_resp.json()["markdown"]

    app.dependency_overrides.clear()
