from .base import CloudProvider
from .gcp import GCPProvider
from .aws import AWSProvider
from .nvcf import NVCFProvider

def get_provider(provider_name: str) -> CloudProvider:
    provider_name = provider_name.upper()
    if provider_name == "GCP":
        return GCPProvider()
    elif provider_name == "AWS":
        return AWSProvider()
    elif provider_name == "NVCF":
        return NVCFProvider(mock=False)
    elif provider_name == "MOCK_NVCF":
        return NVCFProvider(mock=True)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
