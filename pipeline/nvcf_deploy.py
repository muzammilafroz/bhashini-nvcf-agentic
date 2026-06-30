import logging
from mock_nvcf.deploy_client import NVCFDeployClient
from mock_nvcf.models import DeploymentSpec

logger = logging.getLogger(__name__)

class NVCFDeployer:
    def __init__(self, client: NVCFDeployClient):
        self.client = client
        
    async def deploy_model(self, name: str, image: str, spec: DeploymentSpec, change_type: str) -> tuple[str, str]:
        """
        Executes the deploy flow.
        Returns (function_id, version_id)
        """
        logger.info(f"Starting deploy for {name} (change: {change_type})")
        
        # 1. Get or create function
        fn_id = await self.client.get_or_create_function(name)
        logger.info(f"Function ID: {fn_id}")
        
        # In a real system, we'd need to find the CURRENT ACTIVE version if this is config-only.
        # For the prototype, we assume we create a new version even for config changes, OR 
        # we update the most recent one. Let's create a new version always for simplicity,
        # but in config-only we wouldn't have rebuilt the image.
        
        # 2. Create version
        version_name = "v-" + image.split(":")[-1] if ":" in image else "v-latest"
        v_id = await self.client.create_version(fn_id, version_name, image)
        logger.info(f"Version ID: {v_id}")
        
        # 3. Deploy
        # Note: If change_type was config-only, we might just PUT to an existing deployment.
        # But creating a new deployment is also valid.
        await self.client.deploy(fn_id, v_id, spec)
        
        # 4. Wait for ACTIVE
        logger.info("Waiting for deployment to become ACTIVE...")
        success = await self.client.poll_deployment(fn_id, v_id)
        
        if not success:
            logger.error("Deployment failed or timed out!")
            raise RuntimeError(f"Deployment of {name} failed.")
            
        logger.info(f"Deployment {fn_id}/{v_id} is ACTIVE.")
        return fn_id, v_id
