"""Azure authentication utilities for runbooks."""

import os
import logging
from typing import Optional, Union
from azure.identity import (
    DefaultAzureCredential,
    ManagedIdentityCredential,
    ClientSecretCredential,
    EnvironmentCredential
)
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.network import NetworkManagementClient


def get_azure_credential(use_managed_identity: bool = None) -> Union[DefaultAzureCredential, ManagedIdentityCredential]:
    """
    Get Azure credential for authentication.
    
    Args:
        use_managed_identity: Whether to use managed identity. If None, checks environment variables.
        
    Returns:
        Azure credential object
    """
    try:
        # Check environment variable if not explicitly specified
        if use_managed_identity is None:
            use_managed_identity = os.getenv('USE_MANAGED_IDENTITY', 'true').lower() == 'true'
        
        if use_managed_identity:
            # Use managed identity for Azure Automation
            logging.info("Using ManagedIdentityCredential for authentication")
            return ManagedIdentityCredential()
        else:
            # Use default credential chain for local development
            logging.info("Using DefaultAzureCredential for authentication")
            return DefaultAzureCredential()
    except Exception as e:
        logging.error(f"Failed to get Azure credential: {str(e)}")
        raise


def get_management_client(service_type: str, subscription_id: str, credential=None):
    """
    Get Azure management client for specific service.
    
    Args:
        service_type: Type of service (resource, compute, storage, network)
        subscription_id: Azure subscription ID
        credential: Azure credential (optional, will create if not provided)
        
    Returns:
        Management client for the specified service
    """
    if credential is None:
        credential = get_azure_credential()
    
    clients = {
        'resource': ResourceManagementClient,
        'compute': ComputeManagementClient,
        'storage': StorageManagementClient,
        'network': NetworkManagementClient
    }
    
    if service_type not in clients:
        raise ValueError(f"Unsupported service type: {service_type}")
    
    try:
        return clients[service_type](credential, subscription_id)
    except Exception as e:
        logging.error(f"Failed to create {service_type} client: {str(e)}")
        raise


def get_subscription_id() -> str:
    """
    Get subscription ID from environment or automation variable.
    
    Returns:
        Azure subscription ID
    """
    # Try to get from environment variable first
    subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
    
    if not subscription_id:
        # In Azure Automation, you would get this from automation variables
        # For now, we'll raise an error if not found
        raise ValueError("AZURE_SUBSCRIPTION_ID environment variable not set")
    
    return subscription_id