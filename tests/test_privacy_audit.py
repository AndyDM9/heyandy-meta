"""The privacy audit's own checks (evals/privacy.py) catch what they're for: a missing receipt line, an image."""
import base64
import json

from evals.privacy import IMAGE, HOME, Recorder, camera_picture, on_receipt, pieces


def test_what_a_request_carried_is_found():
    body = {"messages": [{"role": "system", "content": f"You are Andy. The person lives in {HOME}."},
                         {"role": "user", "content": "find my keys"},
                         {"role": "assistant", "content": "On it.", "tool_calls": [{"id": "1"}]},  # the cloud's own
                         {"role": "tool", "content": "I see your keys, to my left."}]}
    found, fixed = pieces(body)
    assert found == ["find my keys", "I see your keys, to my left.", HOME] and len(fixed) == 1
    found, _ = pieces({"input": [{"type": "function_call_output", "output": "Reminder set for 5 o'clock."}],
                       "instructions": "Answer briefly."})
    assert found == ["Reminder set for 5 o'clock."]


def test_a_piece_missing_from_the_receipt_is_caught():
    receipt = ["find my keys", "find: I see your keys, to my left.", "a long sentence that was cut wh…"]
    assert on_receipt("I see your keys, to my left.", receipt)
    assert on_receipt("a long sentence that was cut where the TV says so", receipt)
    assert not on_receipt("my daughter's address is 12 Elm Street", receipt)


def test_images_are_counted_once_each_and_camera_bytes_are_recognised():
    shot = base64.b64encode(camera_picture(1)).decode()
    body = json.dumps({"input": [{"type": "computer_call_output", "output": {"type": "input_image",
                                                                             "image_url": f"data:image/jpeg;base64,{shot}"}}]})
    assert len(IMAGE.findall(body.encode())) == 1
    assert base64.b64encode(camera_picture(1))[:120] in body.encode()
    assert camera_picture(1) != camera_picture(2)  # each picture its own bytes


def test_the_recorder_sees_what_the_openai_client_sends():
    from openai import OpenAI

    r = Recorder()
    r.install()
    c = OpenAI(api_key="x", base_url="http://127.0.0.1:9/v1", max_retries=0)
    try:
        c.chat.completions.create(model="m", messages=[{"role": "user", "content": "hello"}])
    except Exception:  # noqa: BLE001 - nothing listens there; the request was still made
        pass
    finally:
        r.uninstall()
    assert r.requests and r.requests[-1][0] == "127.0.0.1" and b"hello" in r.requests[-1][1]
