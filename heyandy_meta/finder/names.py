"""Names for everyday things: what to ask SAM 3.1 for, and what a misheard word probably was.

People and speech-to-text don't always use the name SAM knows best: a coffee mug asked for as "cup", "cop" heard for
"cup". The finder asks for a few close names in the same request (one encoding of the frame), and the request rules
snap a word that isn't a known thing to the nearest one that is, one letter away.
"""
ALSO = {  # what else to look for, in the same request
    "cup": ["mug", "coffee cup"], "mug": ["cup", "coffee mug"], "glasses": ["eyeglasses", "spectacles"],
    "reading glasses": ["glasses", "eyeglasses"], "sunglasses": ["glasses"], "phone": ["cell phone", "smartphone"],
    "mobile": ["cell phone", "phone"], "remote": ["remote control", "tv remote"], "keys": ["keychain", "key"],
    "wallet": ["purse"], "purse": ["wallet", "handbag"], "glass": ["drinking glass", "cup"], "book": ["notebook"],
    "pills": ["pill bottle"], "watch": ["wristwatch"], "bottle": ["water bottle"], "pen": ["pencil"],
    "hat": ["cap"], "bag": ["handbag", "backpack"], "slippers": ["shoes"], "charger": ["phone charger", "cable"],
}
KNOWN = sorted(set(ALSO) | {n for names in ALSO.values() for n in names} | {
    "laptop", "keyboard", "mouse", "tablet", "scarf", "gloves", "umbrella", "plate", "bowl", "spoon", "fork", "knife",
    "towel", "blanket", "pillow", "lamp", "clock", "plant", "box", "jacket", "coat", "shoes", "sock", "toy", "ball",
    "headphones", "earbuds", "magazine", "newspaper", "letter", "card", "ring", "necklace", "bracelet", "hearing aid",
    "kettle", "teapot", "jar", "camera", "notebook", "scissors", "tape", "brush", "comb", "lipstick", "medicine"})


def also(label: str) -> list[str]:
    return [label] + [n for n in ALSO.get(label, []) if n != label][:2]


def _one_off(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1 or a == b:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def snap(thing: str) -> str:
    """"cop" -> "cup": a last word that isn't a known thing but is one letter from exactly one (common ones first)."""
    words = thing.split()
    if not words or thing in KNOWN or words[-1] in KNOWN or len(words[-1]) < 3:
        return thing
    for pool in (ALSO, KNOWN):  # the things people most often ask for win a tie ("cop": cup, not cap)
        near = [k for k in pool if " " not in k and _one_off(words[-1], k)]
        if len(near) == 1:
            return " ".join(words[:-1] + near)
    return thing
