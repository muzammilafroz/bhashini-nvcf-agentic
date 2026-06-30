import os
import yaml
from pathlib import Path
from mock_nvcf.models import DeploymentSpec, DeploymentSpecItem

class DeploymentPlanner:
    def __init__(self, repo_root: Path | str):
        self.repo_root = Path(repo_root)

    def resolve_image_tag(self, image_str: str) -> str:
        """Resolves ${GIT_SHA} in the image string."""
        if "${GIT_SHA}" in image_str:
            sha = os.environ.get("GIT_SHA")
            if not sha:
                # Fallback for local testing
                try:
                    import git
                    repo = git.Repo(self.repo_root)
                    sha = repo.head.commit.hexsha[:7]
                except Exception:
                    sha = "latest"
            return image_str.replace("${GIT_SHA}", sha)
        return image_str

    def plan_deployment(self, model_name: str) -> tuple[str, str, DeploymentSpec]:
        """
        Reads a model's model.yaml and translates it into an NVCF DeploymentSpec.
        Returns (name, image, spec)
        """
        yaml_path = self.repo_root / "models" / model_name / "model.yaml"
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        resolved_image = self.resolve_image_tag(data["image"])
        
        # Build the NVCF spec shape
        spec_item = DeploymentSpecItem(
            gpu=data["gpu"]["type"],
            minInstances=data["scaling"]["min_instances"],
            maxInstances=data["scaling"]["max_instances"],
            maxRequestConcurrency=data["scaling"]["concurrency"]
        )
        
        spec = DeploymentSpec(deploymentSpecifications=[spec_item])
        
        return data["name"], resolved_image, spec
