import os
import time

import yaml

from openings.runtime import Runtime, get_runtime, set_runtime


def test_runtime_reloads_when_the_file_changes(runtime, settings_dict):
    assert runtime.config().scoring.notify_threshold == 20
    settings_dict["scoring"]["notify_threshold"] = 30
    runtime.config_path.write_text(yaml.safe_dump(settings_dict))
    # Force a different mtime even on coarse filesystems.
    stamp = time.time() + 5
    os.utime(runtime.config_path, (stamp, stamp))
    assert runtime.config().scoring.notify_threshold == 30


def test_runtime_keeps_previous_config_on_error(runtime):
    runtime.config()
    runtime.config_path.write_text("scoring: {save_threshold: 5, notify_threshold: 1}\n")
    stamp = time.time() + 5
    os.utime(runtime.config_path, (stamp, stamp))
    assert runtime.config().scoring.notify_threshold == 20


def test_runtime_singleton_and_close(runtime):
    assert get_runtime() is runtime
    runtime.db.count_jobs()
    runtime.close()
    assert runtime.db.count_jobs() == 0
    other = Runtime(data_dir=runtime.data_dir, config_path=runtime.config_path)
    set_runtime(other)
    assert get_runtime() is other
    set_runtime(None)


def test_runtime_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENINGS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("OPENINGS_CONFIG", raising=False)
    instance = Runtime.from_env()
    assert instance.data_dir == tmp_path.resolve()
    assert instance.config_path == tmp_path.resolve() / "config" / "settings.yaml"
