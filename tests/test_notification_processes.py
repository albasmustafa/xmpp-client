"""Bildirim alt süreçlerinin gerçek süreçlerle reaping regresyonları."""
import subprocess

import pytest

import xmpp


@pytest.fixture()
def processes(monkeypatch):
    launched = []
    workers = []
    real_popen = subprocess.Popen

    def popen(*args, **kwargs):
        process = real_popen(["/bin/true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        launched.append(process)
        return process

    class Thread:
        def __init__(self, target, **kwargs):
            workers.append(target)

        def start(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(xmpp.threading, "Thread", Thread)
    monkeypatch.setattr(xmpp.time, "sleep", lambda seconds: None)
    try:
        yield launched, workers
    finally:
        for process in launched:
            process.wait(timeout=2)


def test_notification_player_is_reaped_before_tempfile_cleanup(processes):
    launched, workers = processes
    win = object.__new__(xmpp.MainWindow)
    win._temp_files = []
    win._closing = False
    try:
        win._play_notification_sound()
        assert len(workers) == 1
        workers[0]()
        assert launched[0].returncode == 0
        assert win._temp_files == []
    finally:
        win._cleanup_temp_registry()


def test_desktop_notification_process_is_owned_and_reaped(monkeypatch, processes):
    launched, workers = processes
    monkeypatch.setattr(xmpp, "_HAS_NOTIFY", True)
    xmpp._desktop_notify("Test", "Message")

    assert len(workers) == 1
    workers[0]()
    assert launched[0].returncode == 0
