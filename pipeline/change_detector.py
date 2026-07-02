import json
import logging
from pathlib import Path
from typing import Literal

import git
import yaml

logger = logging.getLogger(__name__)

ChangeType = Literal["config-only", "rebuild", "ci-only"]

class ChangeDetector:
    def __init__(self, repo_path: Path | str):
        self.repo = git.Repo(repo_path)
        self.repo_path = Path(repo_path)
        self._last_commit_a: str | None = None
        self._last_commit_b: str | None = None
        
    def get_changed_files(self, commit_a="HEAD~1", commit_b="HEAD") -> list[str]:
        """Returns a list of changed file paths relative to repo root."""
        self._last_commit_a = commit_a
        self._last_commit_b = commit_b
        try:
            diff_index = self.repo.commit(commit_a).diff(self.repo.commit(commit_b))
            changed = []
            for d in diff_index:
                if d.a_path: changed.append(d.a_path)
                if d.b_path and d.b_path not in changed: changed.append(d.b_path)
            return changed
        except git.exc.GitCommandError as e:
            logger.warning(f"Could not compute diff {commit_a}..{commit_b}: {e}")
            return []
            
    def _load_yaml_at_ref(self, ref: str, file_path: str) -> dict | None:
        try:
            blob = self.repo.git.show(f"{ref}:{file_path}")
            data = yaml.safe_load(blob)
            return data if isinstance(data, dict) else None
        except Exception as e:
            logger.warning(f"Could not load {file_path} at {ref}: {e}")
            return None

    def _is_config_only_model_yaml_change(self, file_path: str, commit_a: str, commit_b: str) -> bool:
        old = self._load_yaml_at_ref(commit_a, file_path)
        new = self._load_yaml_at_ref(commit_b, file_path)
        if old is None or new is None:
            return False

        config_only_keys = {"scaling", "canary"}
        old_non_config = {k: v for k, v in old.items() if k not in config_only_keys}
        new_non_config = {k: v for k, v in new.items() if k not in config_only_keys}
        return old_non_config == new_non_config

    def analyze_changes(
        self,
        changed_files: list[str],
        commit_a: str | None = None,
        commit_b: str | None = None,
    ) -> dict[str, ChangeType]:
        """
        Analyzes changed files and returns a dict mapping model names to their ChangeType.
        If non-model files changed (pipeline, actions), it might return a special mapping 
        or just log it. For this prototype, we'll map the specific model being touched.
        """
        model_changes = {}
        
        # In a real monorepo, we'd check all models. Here we just look at our main model directory.
        models_dir = "models"
        
        commit_a = commit_a or self._last_commit_a
        commit_b = commit_b or self._last_commit_b

        for file_path in changed_files:
            path_parts = Path(file_path).parts
            if not path_parts:
                continue

            if path_parts[0] == models_dir and len(path_parts) > 2:
                model_name = path_parts[1]
                file_name = path_parts[-1]

                # Check what type of change this is
                if file_name == "model.yaml":
                    if model_changes.get(model_name) == "rebuild":
                        continue
                    if commit_a and commit_b and self._is_config_only_model_yaml_change(file_path, commit_a, commit_b):
                        model_changes[model_name] = "config-only"
                    else:
                        # Safe fallback: if we cannot prove the change only touched
                        # scaling/canary knobs, require a rebuild/deploy path.
                        model_changes[model_name] = "rebuild"
                else:
                    # Any other file (e.g. Dockerfile, weights, src) means rebuild
                    model_changes[model_name] = "rebuild"
                    
            elif path_parts[0] in ("pipeline", ".github"):
                # Global CI change, we don't map this to a specific model deploy
                pass
                
        return model_changes
        
    def generate_manifest(self, commit_a="HEAD~1", commit_b="HEAD", output_path: Path | None = None) -> dict:
        files = self.get_changed_files(commit_a, commit_b)
        changes = self.analyze_changes(files, commit_a, commit_b)
        
        manifest = {
            "commit_a": commit_a,
            "commit_b": commit_b,
            "changed_files": files,
            "models": changes
        }
        
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
                
        return manifest
