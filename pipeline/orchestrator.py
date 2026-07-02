import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from pipeline.change_detector import ChangeDetector
from pipeline.deployment_planner import DeploymentPlanner
from pipeline.agents.canary_health import check_canary_health
from pipeline.providers import get_provider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_pipeline(mode: str, repo_root: Path):
    from dotenv import load_dotenv
    load_dotenv(repo_root / ".env")
    
    cd = ChangeDetector(repo_root)
    planner = DeploymentPlanner(repo_root)
    
    provider_name = os.getenv("CLOUD_PROVIDER", "MOCK_NVCF")
    logger.info(f"Using Cloud Provider: {provider_name}")
    provider = get_provider(provider_name)
    
    logger.info(f"Running pipeline in {mode} mode...")
    
    hotfix_model_name = os.getenv("HOTFIX_MODEL_NAME")
    hotfix_image_tag = os.getenv("HOTFIX_IMAGE_TAG")
    hotfix_skip_canary = os.getenv("HOTFIX_SKIP_CANARY", "false").lower() == "true"
    
    changes = {}
    
    if hotfix_model_name:
        logger.warning(f"HOTFIX MODE active for model {hotfix_model_name}")
        changes = {hotfix_model_name: "rebuild"}
    else:
        # 1. Detect Changes
        try:
            changed_files = cd.get_changed_files("HEAD~1", "HEAD")
            changes = cd.analyze_changes(changed_files)
        except Exception as e:
            logger.warning(f"Failed to detect changes via git: {e}")
            
        if not changes:
            logger.info("No model changes detected.")
            # For prototype local run without full git history, fallback if mode is full
            if mode in ("full", "config-only"):
                logger.info("Fallback: treating en-hi-indictrans as changed for prototype run")
                changes = {"en-hi-indictrans": "rebuild" if mode == "full" else "config-only"}
                
    for model_name, change_type in changes.items():
        if change_type == "ci-only":
            logger.info(f"Skipping deploy for {model_name} (ci-only)")
            continue
            
        # 2. Plan
        name, image, spec = planner.plan_deployment(model_name)
        if hotfix_image_tag:
            image = hotfix_image_tag
            logger.info(f"Using hotfix image tag: {image}")
            
        logger.info(f"Planned deploy for {name} with image {image}")
        
        # 3. Deploy
        fn_id, v_id = await provider.deploy_model(name, image, spec)
            
        # 4. Canary Gate (reading settings from plan)
        import yaml
        yaml_path = repo_root / "models" / model_name / "model.yaml"
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        if data.get("canary", {}).get("enabled", False):
            canary = data["canary"]
            
            if hotfix_skip_canary:
                logger.warning("HOTFIX: Skipping canary health check, promoting immediately to 100%")
                await provider.promote(fn_id, v_id, name, image)
            else:
                # Route initial traffic
                await provider.route_traffic(fn_id, v_id, canary.get("weight", 10))
                
                kong_admin = os.getenv("KONG_ADMIN_URL", "http://142.93.209.191:8001")
                prom_url = kong_admin.replace(":8001", ":9090") # derive prom url
                
                healthy, reason = await check_canary_health(
                    model_name=name,
                    fn_id=fn_id,
                    version_id=v_id,
                    image_tag=image,
                    promote_after_seconds=canary.get("promote_after_seconds", 120),
                    rollback_on=canary.get("rollback_on", {}),
                    router_url=kong_admin,
                    prometheus_url=prom_url
                )
                
                if healthy:
                    await provider.promote(fn_id, v_id, name, image)
                else:
                    await provider.rollback(fn_id, v_id, name, image, reason)
                    
    await provider.close()
    logger.info("Pipeline completed.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "config-only", "smoke-only"], default="full")
    args = parser.parse_args()
    
    repo_root = Path(__file__).parent.parent
    asyncio.run(run_pipeline(args.mode, repo_root))

if __name__ == "__main__":
    main()
