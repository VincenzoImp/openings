from unittest.mock import MagicMock, patch

from openings import cli


def test_parser_lists_commands():
    parser = cli.build_parser()
    help_text = parser.format_help()
    for command in ("run", "scheduler", "web", "healthcheck"):
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
