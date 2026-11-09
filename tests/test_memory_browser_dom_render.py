import subprocess
from pathlib import Path
import shutil
import pytest
import json

ROOT = Path(__file__).resolve().parents[1]
DOM_JS = ROOT / "tests" / "test_memory_browser_dom.js"

def shutil_which_node():
    return shutil.which("node")

@pytest.mark.skipif(shutil_which_node() is None, reason="node not available")
def test_memory_browser_dom_render():
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
    res = json.loads(proc.stdout.strip())

    assert res["domainLabels"]["project"]["label"] == "Projects"
    assert res["domainLabels"]["person"]["label"] == "People"
    assert res["domainLabels"]["topic"]["label"] == "Topics"
    assert res["domainLabels"]["self"]["label"] == "Self"
    assert res["hasCorePortrait"] is True
    assert res["hasJournal"] is True
    assert res["hasDDLs"] is True
    assert res["hasProjectsTab"] is True
    assert res["hasPeopleTab"] is True
    assert "No People memories yet" in res["emptyStateText"]
    assert res["archivedSummaryText"] is True
    assert res["lastActiveText"] is True
    assert res["pinnedTooltip"] is True
    assert res["pausedTooltip"] is True
    assert res["archivedTooltip"] is True
    assert res["activeTooltip"] is True
    assert res["detailActiveStatus"] is True
    assert res["detailSummary"] is True
    assert res["detailAliases"] is True
    assert res["detailCreated"] is True
    assert res["detailLastActive"] is True
    assert res["detailDeleteBtn"] is True
    assert res["detailRelatedDdl"] is True
    assert res["detailContentHeader"] is True
