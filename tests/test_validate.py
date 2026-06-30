import json
from pathlib import Path

import pytest
import yaml

from pipeline.validate import validate_model_yaml

# Get paths relative to this file
TESTS_DIR = Path(__file__).parent
PROJECT_ROOT = TESTS_DIR.parent
SCHEMA_PATH = PROJECT_ROOT / "pipeline" / "schemas" / "model_yaml_v1.json"
REAL_MODEL_YAML = PROJECT_ROOT / "models" / "en-hi-indictrans" / "model.yaml"

def test_real_model_yaml_is_valid():
    """Test that the actual model.yaml used in the prototype is valid."""
    assert validate_model_yaml(REAL_MODEL_YAML, SCHEMA_PATH) is True

def test_missing_required_field(tmp_path):
    """Test that omitting a required field fails validation."""
    yaml_path = tmp_path / "model.yaml"
    # Missing 'scaling' block
    data = {
        "schema_version": "1.0",
        "name": "test-model",
        "type": "hf-mt",
        "image": "ghcr.io/test/image",
        "gpu": {"type": "CPU", "count": 0},
        "ports": {"http": 8000}
    }
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
        
    assert validate_model_yaml(yaml_path, SCHEMA_PATH) is False

def test_invalid_type_enum(tmp_path):
    """Test that an invalid 'type' value fails validation."""
    yaml_path = tmp_path / "model.yaml"
    data = {
        "schema_version": "1.0",
        "name": "test-model",
        "type": "unsupported-type", # Invalid type
        "image": "ghcr.io/test/image",
        "gpu": {"type": "CPU", "count": 0},
        "ports": {"http": 8000},
        "scaling": {"min_instances": 1, "max_instances": 2, "concurrency": 4}
    }
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
        
    assert validate_model_yaml(yaml_path, SCHEMA_PATH) is False
