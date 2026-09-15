from unittest.mock import MagicMock, patch

from openings import cli
from tests.conftest import make_job


def test_parser_lists_commands():
    parser = cli.build_parser()
    help_text = parser.format_help()
    for command in ("run", "scheduler", "web", "healthcheck", "rescore"):
        assert command in help_text


def test_default_command_is_scheduler(runtime):
    with patch.object(cli, "_cmd_scheduler", return_value=0) as scheduler:
        assert cli.main([]) == 0
    scheduler.assert_called_once()


def test_run_command_collects_once(runtime):
    scheduler = MagicMock()
    scheduler.run_once.return_value = True
    with (
        patch("openings.pipeline.prepare_runtime", return_value=runtime.config()),
        patch("openings.scheduler.create_scheduler", return_value=scheduler),
    ):
        assert cli.main(["run"]) == 0
    scheduler.run_once.assert_called_once()


def test_web_command_starts_the_server(runtime):
    with patch("openings.web.app.main") as web_main:
        assert cli.main(["web"]) == 0
    web_main.assert_called_once()


def test_healthcheck_passes_in_a_prepared_data_dir(runtime, capsys):
    assert cli.main(["healthcheck"]) == 0
    out = capsys.readouterr().out
    assert "OK   imports" in out and "OK   directories" in out


def test_rescore_updates_stored_scores_and_reports(runtime, capsys):
    job = make_job(relevance_score=0)
    runtime.db.upsert_jobs([job])

    assert cli.main(["rescore"]) == 0

    out = capsys.readouterr().out
    assert "Thresholds: save=0 notify=20" in out
    assert "Scored 1 job(s); changed 1" in out
    assert "before: min=0 q1=0 median=0 q3=0 max=0 >=save:1 >=notify:0" in out
    assert "after:  min=35 q1=35 median=35 q3=35 max=35 >=save:1 >=notify:1" in out
    assert runtime.db.get_job(job.job_id).relevance_score == 35


def test_rescore_dry_run_reports_without_writing(runtime, capsys):
    job = make_job(relevance_score=0)
    runtime.db.upsert_jobs([job])

    assert cli.main(["rescore", "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "Scored 1 job(s); would change 1" in out
    assert "Dry run: nothing was written." in out
    assert runtime.db.get_job(job.job_id).relevance_score == 0


def test_rescore_reports_a_broken_configuration_instead_of_raising(runtime, capsys):
    runtime.config_path.write_text("scoring:\n  weights: 3\n", encoding="utf-8")

    assert cli.main(["rescore"]) == 1
    assert "Configuration error:" in capsys.readouterr().out
