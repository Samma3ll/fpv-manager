import math

from app.workers.tasks import sanitize_for_json, test_task


def test_sanitize_for_json_replaces_non_finite_floats_recursively():
    payload = {
        "ok": 1.5,
        "nan": math.nan,
        "nested": [1, math.inf, {"neg_inf": -math.inf}],
    }

    result = sanitize_for_json(payload)

    assert result["ok"] == 1.5
    assert result["nan"] is None
    assert result["nested"][1] is None
    assert result["nested"][2]["neg_inf"] is None


def test_test_task_returns_sum():
    assert test_task.run(2, 3) == 5
