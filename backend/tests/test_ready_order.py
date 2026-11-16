from openings.app import create_app
from openings.demo import seed_demo


def test_most_urgent_first_ranks_ready_by_priority_then_deadline(tmp_path):
    app = create_app(tmp_path / "demo.sqlite", start_worker=False, demo=True)
    seed_demo(app)
    items = app.state.workspace.list_applications(sort="needs", limit=50)["items"]
    ready = [item for item in items if item["ready"]]
    assert ready == items[: len(ready)]
    keys = [(item["priority"] is None, item["priority"], item["deadline"]) for item in ready]
    assert keys == sorted(keys)
