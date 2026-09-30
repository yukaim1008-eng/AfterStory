from scripts.evaluate_response_policy import evaluate_quality, evaluate_result


def test_response_policy_evaluation_checks_hard_requirements_and_effects():
    scenario = {
        "hard_required_all": ["开场"],
        "hard_required_any": ["收尾", "结尾"],
        "forbidden": ["memory_id"],
        "max_questions": 1,
        "expected_effect_actions": ["remember"],
    }
    assert evaluate_result(scenario, "开场先讲故事，收尾回到主题。", ["remember"]) == []
    failures = evaluate_result(
        scenario,
        "只说开场？还要问一次？memory_id",
        [],
    )
    assert "missing_any:收尾|结尾" in failures
    assert "forbidden:memory_id" in failures
    assert "missing_effect:remember" in failures
    assert "internal_leak:memory_id" in failures


def test_response_policy_evaluation_reports_question_count_as_quality_warning():
    scenario = {
        "required_all": ["具体"],
        "required_any": ["事实", "例子"],
        "max_questions": 1,
    }
    assert evaluate_quality(scenario, "给一个具体事实？") == []
    assert evaluate_quality(scenario, "问这个？再问那个？") == [
        "missing:具体",
        "missing_any:事实|例子",
        "questions:2",
    ]
