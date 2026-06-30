import argparse
import asyncio
import logging
from pathlib import Path
import sys

from pipeline.change_detector import ChangeDetector
from pipeline.deployment_planner import DeploymentPlanner
from pipeline.nvcf_deploy import NVCFDeployer
from mock_nvcf.deploy_client import NVCFDeployClient
from pipeline.agents.canary_health import check_canary_health

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_pipeline(mode: str, repo_root: Path):
    cd = ChangeDetector(repo_root)
    planner = DeploymentPlanner(repo_root)
    
    # We are using mock client
    client = NVCFDeployClient(mock=True)
    deployer = NVCFDeployer(client)
    
    logger.info(f"Running pipeline in {mode} mode...")
    
    # 1. Detect Changes
    if mode in ("full", "config-only"):
        # We would normally diff HEAD~1..HEAD, but for the prototype local run we'll fake it
        # and assume en-hi-indictrans has changed.
        changes = {"en-hi-indictrans": "rebuild" if mode == "full" else "config-only"}
        logger.info(f"Detected changes: {changes}")
    else:
        changes = {"en-hi-indictrans": "ci-only"} # e.g. smoke test only
        
    for model_name, change_type in changes.items():
        if change_type == "ci-only":
            logger.info(f"Skipping deploy for {model_name} (ci-only)")
            continue
            
        # 2. Plan
        name, image, spec = planner.plan_deployment(model_name)
        logger.info(f"Planned deploy for {name} with image {image}")
        
        # 3. Deploy
        fn_id, v_id = await deployer.deploy_model(name, image, spec, change_type)
        
        # 4. Canary Gate (reading settings from plan, hardcoded router url for prototype)
        # Ideally we'd parse canary settings from model.yaml inside the planner
        import yaml
        yaml_path = repo_root / "models" / model_name / "model.yaml"
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        if data.get("canary", {}).get("enabled", False):
            canary = data["canary"]
            await check_canary_health(
                model_name=name,
                fn_id=fn_id,
                version_id=v_id,
                image_tag=image,
                promote_after_seconds=canary.get("promote_after_seconds", 120),
                rollback_on=canary.get("rollback_on", {})
            )
            
    logger.info("Pipeline completed.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "config-only", "smoke-only"], default="full")
    args = parser.parse_args()
    
    repo_root = Path(__file__).parent.parent
    asyncio.run(run_pipeline(args.mode, repo_root))

if __name__ == "__main__":
    main()
