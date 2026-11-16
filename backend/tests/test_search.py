"""Search on the demo workspace: the right thing first, the same over REST and MCP."""

import pytest

from demo_workspace import seed_demo
from openings.interfaces.operation import without_empty


@pytest.fixture
def demo(app, client):
    seed_demo(app, client)
    return client


def titles(page):
    return [item.get("job", item).get("title") for item in page["items"]]


def test_an_exact_title_comes_first_in_both_groups(demo):
    jobs = demo.get("/api/v1/jobs", params={"q": "Python Backend Engineer", "limit": 5}).json()
    applications = demo.get(
        "/api/v1/applications", params={"q": "Python Backend Engineer", "limit": 5}
    ).json()
    assert titles(jobs)[0] == "Python Backend Engineer"
    assert titles(applications)[0] == "Python Backend Engineer"
    # A word of the title or the company ranks above a word only in a posting.
    by_company = demo.get("/api/v1/jobs", params={"q": "freightwise"}).json()
    assert by_company["items"][0]["company"] == "Freightwise"


def test_location_and_state_words_match(demo):
    dublin = demo.get("/api/v1/jobs", params={"q": "dublin"}).json()
    assert dublin["items"] and "Dublin" in dublin["items"][0]["location"]
    interview = demo.get("/api/v1/applications", params={"q": "interview"}).json()
    stages = [item["stage"] for item in interview["items"]]
    assert "interview" in stages and stages[: stages.count("interview")] == ["interview"] * (
        stages.count("interview")
    )
    dismissed = demo.get("/api/v1/jobs", params={"q": "dismissed"}).json()
    assert dismissed["items"][0]["triage"] == "dismissed"


def test_an_explicit_sort_keeps_its_order(demo):
    newest = demo.get("/api/v1/jobs", params={"q": "engineer", "sort": "newest"}).json()
    created = [item["created_at"] for item in newest["items"]]
    assert created == sorted(created, reverse=True)
    # Without words, relevance is the newest first.
    plain = demo.get("/api/v1/jobs").json()
    assert [i["id"] for i in plain["items"]] == [
        i["id"] for i in demo.get("/api/v1/jobs", params={"sort": "newest"}).json()["items"]
    ]


def test_rest_and_mcp_rank_alike(app, owner_token, mcp):
    demo = mcp.client
    demo.headers.update(owner_token["headers"])
    seed_demo(app, demo)
    for q in ("Python Backend Engineer", "interview", "dublin backend"):
        rest = demo.get("/api/v1/jobs", params={"q": q, "limit": 8}).json()
        listed, error = mcp.call("jobs_list", {"q": q, "limit": 8})
        assert error is None and listed == without_empty(rest)
        rest = demo.get("/api/v1/applications", params={"q": q, "limit": 8}).json()
        listed, error = mcp.call("applications_list", {"q": q, "limit": 8})
        assert error is None
        assert [i["id"] for i in listed["items"]] == [i["id"] for i in rest["items"]]
