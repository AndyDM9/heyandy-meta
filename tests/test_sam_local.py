import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from heyandy_meta.models.sam_local import LocalSam31, LocalUnavailable, NotLocal
from heyandy_meta.robot.body import Frame

REPLY = {"masks": [{"box": [10, 20, 74, 60], "score": 0.91, "center": [42.5, 40.0], "area": 1800,
                    "outline": "M 0 0 L 32 0 L 32 20 Z", "outline_scale": [2.0, 2.0]}], "seconds": 0.27}


@pytest.fixture
def server():
    got = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            got.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            body = got[-1][1]
            data = json.dumps(REPLY if "query" in body else {"masks": {q: REPLY["masks"] for q in body["queries"]},
                                                              "seconds": 0.4}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    s = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}", got
    s.shutdown()


def test_reads_masks_from_the_local_server(server):
    url, got = server
    masks = LocalSam31(url).find(Frame(b"\xff\xd8jpeg", 1920, 1080, 0.0, 15.0), "glasses")
    assert got[0][0] == "/segment" and got[0][1]["query"] == "glasses" and got[0][1]["min_score"] == 0.3
    m = masks[0]
    assert (m.label, m.box, m.score, m.center, m.area) == ("glasses", (10, 20, 74, 60), 0.91, (42.5, 40.0), 1800)
    assert m.outline_scale == (2.0, 2.0)


def test_refuses_a_cloud_address():
    with pytest.raises(NotLocal):
        LocalSam31("https://api.meta.ai/v1")


def test_a_stopped_server_is_reported_not_hidden():
    with pytest.raises(LocalUnavailable):
        LocalSam31("http://127.0.0.1:9", timeout=1).find(b"x", "keys")


def test_several_things_in_one_frame(server):
    url, got = server
    out = LocalSam31(url).find_many(b"\xff\xd8jpeg", ["keys", "glasses"])
    assert got[0][0] == "/segment_many" and got[0][1]["queries"] == ["keys", "glasses"]
    assert [m.label for m in out["keys"]] == ["keys"] and [m.label for m in out["glasses"]] == ["glasses"]
