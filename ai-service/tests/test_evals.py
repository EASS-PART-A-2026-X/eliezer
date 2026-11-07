"""The eval harness itself must keep working (CI runs it with the offline baseline)."""

from evals.run_evals import load_dataset, regex_baseline, run


def test_dataset_has_enough_cases():
    assert 8 <= len(load_dataset().cases) <= 10


def test_dataset_has_at_least_three_evaluators():
    assert len(load_dataset().evaluators) >= 3


def test_baseline_run_scores_every_case():
    report = run("test")
    assert report.failures == []  # no case crashed
    assert len(report.cases) == len(load_dataset().cases)
    assert report.averages() is not None


def test_regex_baseline_is_naive_on_purpose():
    out = regex_baseline("URGENT: send the report")
    assert (out["title"], out["priority"], out["tags"]) == ("URGENT", 5, ["work"])
