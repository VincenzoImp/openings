from unittest.mock import patch

from openings import cli


def test_parser_lists_commands():
    parser = cli.build_parser()
    help_text = parser.format_help()
    for command in ("run", "scheduler", "web", "healthcheck"):
        assert command in help_text


def test_default_command_is_scheduler():
    with patch.object(cli, "_cmd_scheduler", return_value=0) as scheduler:
        assert cli.main([]) == 0
    scheduler.assert_called_once()


def test_run_dispatch():
    with patch.object(cli, "_cmd_run", return_value=1) as run:
        assert cli.main(["run"]) == 1
    run.assert_called_once()


def test_run_command_collects_once(env):
    from unittest.mock import MagicMock

    scheduler = MagicMock()
    scheduler.run_once.return_value = True
    with (
        patch("openings.pipeline.prepare_runtime", return_value=(MagicMock(), MagicMock())),
        patch("openings.scheduler.create_scheduler", return_value=scheduler),
    ):
        assert cli.main(["run"]) == 0
    scheduler.run_once.assert_called_once()


def test_web_command_starts_the_server():
    with patch("openings.web.app.main") as web_main:
        assert cli.main(["web"]) == 0
    web_main.assert_called_once()


def test_healthcheck_passes_in_a_prepared_data_dir(env):
    from openings.healthcheck import main

    assert main() == 0
