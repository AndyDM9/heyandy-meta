import socket
import threading

from heyandy_meta.network import reachable, watch


def test_reachable_means_a_connection_opens():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    try:
        assert reachable("127.0.0.1", srv.getsockname()[1])
    finally:
        srv.close()
    assert not reachable("127.0.0.1", 9, timeout=0.5)


def test_watch_reports_the_start_and_each_change_only():
    states = iter([True, True, False, False, True])
    seen, stop = [], threading.Event()

    def check():
        try:
            return next(states)
        except StopIteration:
            stop.set()
            return True

    watch(seen.append, stop, every_s=0, check=check)
    assert seen == [True, False, True]


def test_unplugged_andy_says_offline_on_the_tv(tmp_path):
    from tests.test_app import andy

    a, _, _ = andy(tmp_path=tmp_path)
    a.set_online(False)
    assert a.screen.snapshot()["online"] is False and a.online is False
    assert "not connected" in a.hear("what's the weather tomorrow?")
