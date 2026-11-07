"""The eval harness itself must keep working (CI runs it with the offline baseline)."""

from evals.run_evals import IMAGES, load_dataset, run, same_taxon


def test_dataset_size_images_and_control_case():
    dataset = load_dataset()
    assert 8 <= len(dataset.cases) <= 10
    assert len(dataset.evaluators) >= 3
    for case in dataset.cases:
        assert (IMAGES / case.inputs).is_file(), case.inputs
    assert any(not case.metadata["is_plant"] for case in dataset.cases)  # control flow


def test_same_taxon_rules():
    assert same_taxon("Citrus × limon", "Citrus limon")
    assert same_taxon("Bougainvillea", "Bougainvillea glabra")  # genus is enough
    assert not same_taxon("Ocimum basilicum", "Ocimum tenuiflorum")


def test_baseline_run_scores_every_case():
    report = run("test")
    assert report.failures == []  # no case crashed
    assert len(report.cases) == len(load_dataset().cases)
    assert report.averages() is not None
    rosemary = next(c for c in report.cases if c.name == "rosemary")
    assert rosemary.assertions["Top1Species"].value is True
    control = next(c for c in report.cases if c.name == "not_a_plant")
    assert (
        control.assertions["PlantDecision"].value is False
    )  # the baseline always says "plant"
