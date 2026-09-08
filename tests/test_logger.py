import logging

from openings.logger import (
    ColoredFormatter,
    DedupeFilter,
    ProgressLogger,
    _timezone_converter,
    get_logger,
    log_section,
    setup_logging,
)


def test_get_logger_names():
    assert get_logger().name == "openings"
    assert get_logger("scoring").name == "openings.scoring"


def test_setup_logging_installs_console_and_file_handlers(config):
    logger = setup_logging(config)
    kinds = {type(handler).__name__ for handler in logger.handlers}
    assert kinds == {"StreamHandler", "RotatingFileHandler"}
    assert logger.propagate is False
    assert config.log_file.parent.is_dir()
    # Calling again replaces the handlers instead of stacking them.
    again = setup_logging(config)
    assert len(again.handlers) == 2


def test_setup_logging_console_only(config):
    logger = setup_logging(config, console_only=True)
    assert [type(handler).__name__ for handler in logger.handlers] == ["StreamHandler"]


def test_timezone_converter_renders_in_zone():
    convert = _timezone_converter("Europe/Zurich")
    summer = convert(1788739200)  # 2026-09-07T00:00:00Z
    assert (summer.tm_hour, summer.tm_mday) == (2, 7)
    assert _timezone_converter("Not/AZone")(0).tm_year >= 1969


def test_dedupe_filter_only_affects_prefixed_loggers():
    dedupe = DedupeFilter(name_prefix="JobSpy")
    record = logging.LogRecord("JobSpy:Indeed", logging.WARNING, "", 0, "same", None, None)
    other = logging.LogRecord("openings.x", logging.WARNING, "", 0, "same", None, None)
    assert dedupe.filter(record) is True
    assert dedupe.filter(record) is False
    assert dedupe.filter(other) is True and dedupe.filter(other) is True


def test_colored_formatter_without_tty_is_plain(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    formatter = ColoredFormatter("%(levelname)s %(message)s")
    record = logging.LogRecord("x", logging.INFO, "", 0, "hello", None, None)
    assert formatter.format(record) == "INFO hello"


def test_progress_logger_and_section(caplog):
    logger = logging.getLogger("progress-test")
    with caplog.at_level(logging.INFO, logger="progress-test"):
        progress = ProgressLogger(logger, 2, "Work")
        progress.update(True, "one")
        progress.update(False, "two")
        progress.summary()
        log_section(logger, "TITLE")
    messages = [record.getMessage() for record in caplog.records]
    assert "[1/2] (50%) one" in messages
    assert "Work complete: 1 succeeded, 1 failed out of 2 total" in messages
    assert "  TITLE" in messages
