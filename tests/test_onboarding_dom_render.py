import subprocess
from pathlib import Path
import shutil
import pytest

ROOT = Path(__file__).resolve().parents[1]
DOM_JS = ROOT / "tests" / "test_onboarding_dom.js"

def shutil_which_node():
    return shutil.which("node")

@pytest.mark.skipif(shutil_which_node() is None, reason="node not available")
def test_onboarding_dom_render_next_and_finish():
    if shutil_which_node() is None:
        pytest.skip("node not available")

    proc = subprocess.run(
        ["node", str(DOM_JS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    assert proc.returncode == 0, f"Node execution failed: {proc.stderr}\nSTDOUT: {proc.stdout}"
    import json
    res = json.loads(proc.stdout.strip())
    assert res["step0_text"] == "Next"
    assert res["last_text"] == "Finish"
    assert res["step0_q"] == "What should I call you?"
