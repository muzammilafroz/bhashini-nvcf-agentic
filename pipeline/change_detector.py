import json
import logging
from pathlib import Path
from typing import Literal

import git

logger = logging.getLogger(__name__)

ChangeType = Literal["config-only", "rebuild", "ci-only"]

class ChangeDetector:
    def __init__(self, repo_path: Path | str):
        self.repo = git.Repo(repo_path)
        self.repo_path = Path(repo_path)
        
    def get_changed_files(self, commit_a="HEAD~1", commit_b="HEAD") -> list[str]:
        """Returns a list of changed file paths relative to repo root."""
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
            
    def analyze_changes(self, changed_files: list[str]) -> dict[str, ChangeType]:
        """
        Analyzes changed files and returns a dict mapping model names to their ChangeType.
        If non-model files changed (pipeline, actions), it might return a special mapping 
        or just log it. For this prototype, we'll map the specific model being touched.
        """
        model_changes = {}
        
        # In a real monorepo, we'd check all models. Here we just look at our main model directory.
        models_dir = "models"
        
        for file_path in changed_files:
            path_parts = Path(file_path).parts
            if path_parts[0] == models_dir and len(path_parts) > 2:
                model_name = path_parts[1]
                file_name = path_parts[-1]
                
                # Check what type of change this is
                if file_name == "model.yaml":
                    # We should technically parse the YAML and see if ONLY scaling/canary changed.
                    # For prototype simplicity, we'll assume any change to model.yaml is config-only
                    # IF no other files in that model's dir changed.
                    if model_name not in model_changes:
                        model_changes[model_name] = "config-only"
                else:
                    # Any other file (e.g. Dockerfile, weights, src) means rebuild
                    model_changes[model_name] = "rebuild"
                    
            elif path_parts[0] in ("pipeline", ".github"):
                # Global CI change, we don't map this to a specific model deploy
                pass
                
        return model_changes
        
    def generate_manifest(self, commit_a="HEAD~1", commit_b="HEAD", output_path: Path | None = None) -> dict:
        files = self.get_changed_files(commit_a, commit_b)
        changes = self.analyze_changes(files)
        
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
