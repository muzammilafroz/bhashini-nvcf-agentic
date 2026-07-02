from pathlib import Path
from pipeline.change_detector import ChangeDetector

def test_change_detector_logic():
    # Since we can't easily mock a full git repo history without complex setup in pytest,
    # we'll test the analysis logic directly.
    cd = ChangeDetector(Path.cwd())
    
    # Without commit refs/content, model.yaml changes must be classified conservatively.
    files = ["models/en-hi-indictrans/model.yaml"]
    changes = cd.analyze_changes(files)
    assert changes["en-hi-indictrans"] == "rebuild"
    
    # Simulate an image/code change
    files = ["models/en-hi-indictrans/Dockerfile", "models/en-hi-indictrans/model.yaml"]
    changes = cd.analyze_changes(files)
    assert changes["en-hi-indictrans"] == "rebuild"
    
    # Simulate a pipeline only change
    files = ["pipeline/validate.py"]
    changes = cd.analyze_changes(files)
    assert "en-hi-indictrans" not in changes
