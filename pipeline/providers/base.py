from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class CloudProvider(ABC):
    """
    Abstract Base Class for all cloud deployment providers.
    Allows seamlessly swapping between GCP, AWS, Azure, NVCF, etc.
    """
    
    @abstractmethod
    def deploy_model(self, model_id: str, image_uri: str, config: Dict[str, Any]) -> str:
        """
        Deploys a model image to the cloud provider.
        Returns a version_id or deployment_id representing the new deployment.
        """
        pass

    @abstractmethod
    def get_deployment_status(self, deployment_id: str) -> str:
        """
        Checks the status of the deployment.
        Must return one of: 'DEPLOYING', 'ACTIVE', 'FAILED'
        """
        pass
    
    @abstractmethod
    def route_traffic(self, deployment_id: str, weight: int):
        """
        Updates the API Gateway to route `weight` % of traffic to this deployment.
        """
        pass

    @abstractmethod
    def delete_deployment(self, deployment_id: str):
        """
        Tears down the deployment resources.
        """
        pass
