import argparse
import json
import sys
from pathlib import Path

import jsonschema
import yaml

# Adjust this path based on where the script is executed
SCHEMA_PATH = Path(__file__).parent / "schemas" / "model_yaml_v1.json"

def load_schema(schema_path: Path) -> dict:
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)

def validate_model_yaml(yaml_path: str | Path, schema_path: Path | None = None) -> bool:
    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        print(f"FAIL: File not found: {yaml_path}")
        return False
    
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"FAIL: YAML parsing error in {yaml_path}:\n{e}")
        return False
        
    schema_file = schema_path or SCHEMA_PATH
    try:
        schema = load_schema(schema_file)
    except Exception as e:
        print(f"FAIL: Could not load schema from {schema_file}:\n{e}")
        return False

    try:
        jsonschema.validate(instance=data, schema=schema)
        print(f"PASS: {yaml_path} is valid")
        return True
    except jsonschema.ValidationError as e:
        print(f"FAIL: Schema validation error in {yaml_path}:")
        print(f"  Path: {' -> '.join(str(p) for p in e.absolute_path)}")
        print(f"  Message: {e.message}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Validate a model.yaml file against the schema.")
    parser.add_argument("yaml_path", type=str, help="Path to the model.yaml file")
    parser.add_argument("--schema", type=str, help="Path to the JSON schema file (optional)", default=None)
    args = parser.parse_args()
    
    schema_path = Path(args.schema) if args.schema else None
    
    is_valid = validate_model_yaml(args.yaml_path, schema_path)
    sys.exit(0 if is_valid else 1)

if __name__ == "__main__":
    main()
