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


def test_a_pulled_cable_is_noticed_at_once_and_the_cloud_tried_each_second_once_its_back():
    """November 3: the network-unplugged shot. Andy noticed only at its next look at the cloud, up to 10 s later, so
    the TV went on showing it online while it found the keys. The link is read on this computer every second now."""
    t = [0.0]
    links = iter([True, True, False, False, True, True, True, True, True, True])
    clouds = iter([True, False, False, True])  # back: the address takes a moment to come
    seen, asked, stop = [], [], threading.Event()

    def link():
        try:
            return next(links)
        except StopIteration:
            stop.set()
            return True

    def check():
        asked.append(t[0])
        return next(clouds)

    class Step(threading.Event):
        def wait(self, s):
            t[0] += s
            return stop.is_set()

    watch(seen.append, Step(), every_s=10, check=check, link=link, clock=lambda: t[0])
    assert seen == [True, False, True]
    # online: the cloud tried at the start only (not each second); pulled: no cloud try at all, offline at once
    # (t=2); back at t=4: tried each second until it answers (t=4, 5, 6), then left for 10 s again
    assert asked == [0.0, 4.0, 5.0, 6.0]


def test_where_the_link_cant_be_read_the_cloud_alone_decides_every_ten_seconds(tmp_path):
    from heyandy_meta.network import wired

    assert wired(routes=str(tmp_path / "none")) is None  # not Linux: no answer, not "unplugged"
    (tmp_path / "route").write_text("Iface\tDestination\tGateway\nenp7s0\t00000000\t0101A8C0\ndocker0\t000011AC\t0\n")
    (tmp_path / "enp7s0").mkdir()
    (tmp_path / "enp7s0" / "carrier").write_text("1\n")
    assert wired(routes=str(tmp_path / "route"), net=str(tmp_path)) is True
    (tmp_path / "enp7s0" / "carrier").write_text("0\n")
    assert wired(routes=str(tmp_path / "route"), net=str(tmp_path)) is False  # the cable out
    (tmp_path / "route").write_text("Iface\tDestination\tGateway\ndocker0\t000011AC\t0\n")
    assert wired(routes=str(tmp_path / "route"), net=str(tmp_path)) is False  # its route gone a moment later
    waits = []

    class Once(threading.Event):
        def wait(self, s):
            waits.append(s)
            return True

    watch(lambda on: None, Once(), every_s=10, check=lambda: True, link=lambda: None)
    assert waits == [10]
