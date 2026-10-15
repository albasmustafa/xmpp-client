"""after_alive: yok edilen pencerenin bekleyen zamanlayıcısı iptal edilir."""

import os
import sys
import tkinter as tk

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.timers import after_alive  # noqa: E402


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("ekran yok")
    r.withdraw()
    yield r
    r.destroy()


def _pump(root, ms):
    import time
    end = time.time() + ms / 1000
    while time.time() < end:
        root.update()


def test_destroy_cancels_pending_timer(root):
    calls = []
    top = tk.Toplevel(root)
    aid = after_alive(top, 100, lambda: calls.append(1))
    top.destroy()
    assert aid not in root.tk.splitlist(root.tk.call("after", "info"))
    _pump(root, 200)
    assert calls == []


def test_timer_fires_while_alive_and_loops_do_not_pile_up_bindings(root):
    calls = []
    top = tk.Toplevel(root)

    def loop():
        calls.append(1)
        if len(calls) < 3:
            after_alive(top, 10, loop)

    after_alive(top, 10, loop)
    _pump(root, 200)
    assert calls == [1, 1, 1]
    assert top._after_alive_ids == set()
    assert len(top.bind("<Destroy>").strip().splitlines()) == 1
    top.destroy()
