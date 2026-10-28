"""Writing what Andy keeps about the person: readable by them only, from the first byte, and never half-written."""
import os
from pathlib import Path


def write_private(path: Path, text: str) -> None:
    """Write text to path (mode 600, in a folder only the person can open), all at once."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o600)  # an old file left from before keeps its mode otherwise
    tmp.replace(path)
