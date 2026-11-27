"""Reproduce the supplied Rasmee Thaana Noofaru-style v1.100 binary exactly."""
import hashlib
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "56980444a8add9e512fae56f015560a64f2400e543373e1243db7169053476e4"
MODIFIED_TIMESTAMP = 3878602811


def main():
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("RASMEE_", "FONT_")) and k != "NO_HINT"}
    env.update(SOURCE_DATE_EPOCH="1795737600", FONT_VERSION="1.007",
               RASMEE_ENTRY_ROUND="65,200")
    with tempfile.TemporaryDirectory(prefix="rasmee-noofaru-") as tmp:
        base = Path(tmp) / "rounded.ttf"
        candidate = Path(tmp) / "RasmeeThaana-NoofaruStyle.ttf"
        subprocess.run([sys.executable, str(ROOT / "tools/build.py"), str(base)],
                       cwd=ROOT, env=env, check=True)
        import fontTools.misc.timeTools
        original_clock = fontTools.misc.timeTools.timestampNow
        original_argv = sys.argv
        try:
            fontTools.misc.timeTools.timestampNow = lambda: MODIFIED_TIMESTAMP
            sys.argv = [str(ROOT / "tools/noofaru_slant.py"), str(base),
                        str(candidate), "--angle", "10", "--version", "1.100"]
            runpy.run_path(str(ROOT / "tools/noofaru_slant.py"), run_name="__main__")
        finally:
            fontTools.misc.timeTools.timestampNow = original_clock
            sys.argv = original_argv
        data = candidate.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != EXPECTED:
            raise SystemExit(f"Rebuild mismatch: expected {EXPECTED}, got {digest}")
        out = ROOT / "build/RasmeeThaana-NoofaruStyle.ttf"
        out.parent.mkdir(exist_ok=True)
        out.write_bytes(data)
        print(f"PASS: exact rebuild {digest}\nOutput: {out}")


if __name__ == "__main__":
    main()
