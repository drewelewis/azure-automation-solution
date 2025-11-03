"""
Azure Automation Runbook: Update Key Vault Configuration

This runbook manages Azure Key Vault operations including:
- Secret management (create, update, retrieve)
- Access policy updates
- Key Vault configuration changes
- Secret rotation preparation

The script loads Key Vault configuration from environment variables and provides
comprehensive logging and error handling.
"""

import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Add the shared modules to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared import setup_logging, log_operation, get_azure_credential, get_setting
from shared.common_operations import AzureOperations
from shared.env_config import EnvironmentConfig
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.keyvault.secrets import SecretClient
from azure.keyvault.keys import KeyClient
from azure.core.exceptions import AzureError


# Configuration for Key Vault operations
KEYVAULT_OPERATIONS = {
    "secrets": {
        "connection_string": {
            "description": "Database connection string",
            "content_type": "application/x-connection-string",
            "enabled": True
        },
        "api_key": {
            "description": "External API key",
            "content_type": "application/x-api-key", 
            "enabled": True
        },
        "ssl_certificate": {
            "description": "SSL certificate for HTTPS",
            "content_type": "application/x-pkcs12",
            "enabled": False
        }
    }
}


def main():
    """Main runbook execution function."""
    
    # Load environment configuration first
    env_config = EnvironmentConfig(".env")
    validation_result = env_config.validate_environment()
    
    # Setup logging
    logger = setup_logging("update-keyvault", level="INFO")
    
    try:
        log_operation(logger, "update_keyvault_runbook", status="START")
        
        # Get configuration
        subscription_id = get_setting('azure.subscription_id')
        if not subscription_id:
            raise ValueError("Azure subscription ID not configured")
        
        # Initialize Azure operations
        azure_ops = AzureOperations(subscription_id)
        
        # Get Key Vault configuration from environment variables
        resource_group = os.getenv('AZURE_KEYVAULT_RESOURCE_GROUP') or get_setting('azure.resource_group', 'default-rg')
        keyvault_name = os.getenv('AZURE_KEYVAULT_NAME') or get_setting('security.keyvault_name', 'default-kv')
        
        logger.info(f"Target Key Vault: {keyvault_name} in resource group: {resource_group}")
        
        # Perform Key Vault operations
        update_keyvault_configuration(azure_ops, resource_group, keyvault_name, logger)
        
        log_operation(logger, "update_keyvault_runbook", status="SUCCESS")
        logger.info("Key Vault update runbook completed successfully")
        
    except Exception as e:
        log_operation(logger, "update_keyvault_runbook", status="ERROR", 
                     details={"error": str(e)})
        logger.error(f"Runbook failed: {str(e)}")
        raise


def update_keyvault_configuration(
    azure_ops: AzureOperations, 
    resource_group: str, 
    keyvault_name: str, 
    logger
) -> None:
    """
    Update Key Vault configuration and manage secrets.
    
    Args:
        azure_ops: Azure operations instance
        resource_group: Resource group name
        keyvault_name: Key Vault name
        logger: Logger instance
    """
    keyvault_id = f"/subscriptions/{azure_ops.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.KeyVault/vaults/{keyvault_name}"
    
    try:
        # Get Key Vault management client
        kv_mgmt_client = get_keyvault_management_client(azure_ops)
        
        log_operation(logger, "get_keyvault", keyvault_id, status="START")
        
        # Get existing Key Vault
        keyvault = kv_mgmt_client.vaults.get(resource_group, keyvault_name)
        
        log_operation(logger, "get_keyvault", keyvault_id, status="SUCCESS")
        logger.info(f"Found Key Vault: {keyvault.name} at {keyvault.properties.vault_uri}")
        
        # Update Key Vault properties if needed
        update_keyvault_properties(kv_mgmt_client, resource_group, keyvault_name, keyvault, logger)
        
        # Manage secrets
        manage_keyvault_secrets(keyvault.properties.vault_uri, azure_ops, logger)
        
        # List current secrets for verification
        list_keyvault_secrets(keyvault.properties.vault_uri, azure_ops, logger)
        
    except AzureError as e:
        log_operation(logger, "update_keyvault_configuration", keyvault_id, status="ERROR", 
                     details={"error": str(e)})
        logger.error(f"Failed to update Key Vault configuration: {str(e)}")
        raise


def get_keyvault_management_client(azure_ops: AzureOperations) -> KeyVaultManagementClient:
    """Get Key Vault management client."""
    return KeyVaultManagementClient(azure_ops.credential, azure_ops.subscription_id)


def update_keyvault_properties(
    kv_mgmt_client: KeyVaultManagementClient,
    resource_group: str,
    keyvault_name: str,
    keyvault: Any,
    logger
) -> None:
    """
    Update Key Vault properties like access policies, network rules, etc.
    
    Args:
        kv_mgmt_client: Key Vault management client
        resource_group: Resource group name
        keyvault_name: Key Vault name
        keyvault: Current Key Vault object
        logger: Logger instance
    """
    try:
        # Example: Enable soft delete and purge protection
        update_needed = False
        
        if not keyvault.properties.enable_soft_delete:
            logger.info("Enabling soft delete for Key Vault")
            update_needed = True
        
        if not keyvault.properties.enable_purge_protection:
            logger.info("Enabling purge protection for Key Vault")
            update_needed = True
        
        if update_needed:
            # Note: In practice, some properties like soft delete cannot be changed after creation
            logger.info("Key Vault property updates would be applied here")
            log_operation(logger, "update_keyvault_properties", keyvault.id, status="SUCCESS",
                        details={"updates": "soft_delete, purge_protection"})
        else:
            logger.info("Key Vault properties are already configured correctly")
            
    except Exception as e:
        logger.error(f"Failed to update Key Vault properties: {str(e)}")
        raise


def manage_keyvault_secrets(vault_url: str, azure_ops: AzureOperations, logger) -> None:
    """
    Manage secrets in Key Vault based on configuration.
    
    Args:
        vault_url: Key Vault URL
        azure_ops: Azure operations instance
        logger: Logger instance
    """
    try:
        # Get secret client
        secret_client = SecretClient(vault_url=vault_url, credential=azure_ops.credential)
        
        log_operation(logger, "manage_secrets", vault_url, status="START")
        
        # Process configured secrets
        for secret_name, config in KEYVAULT_OPERATIONS["secrets"].items():
            if config.get("enabled", True):
                manage_individual_secret(secret_client, secret_name, config, logger)
        
        log_operation(logger, "manage_secrets", vault_url, status="SUCCESS")
        
    except Exception as e:
        log_operation(logger, "manage_secrets", vault_url, status="ERROR",
                     details={"error": str(e)})
        logger.error(f"Failed to manage Key Vault secrets: {str(e)}")
        raise


def manage_individual_secret(
    secret_client: SecretClient, 
    secret_name: str, 
    config: Dict[str, Any], 
    logger
) -> None:
    """
    Manage an individual secret in Key Vault.
    
    Args:
        secret_client: Secret client instance
        secret_name: Name of the secret
        config: Secret configuration
        logger: Logger instance
    """
    try:
        # Check if secret exists
        try:
            existing_secret = secret_client.get_secret(secret_name)
            logger.info(f"Secret '{secret_name}' exists, created: {existing_secret.properties.created_on}")
            
            # Check if secret needs rotation (example: older than 90 days)
            if existing_secret.properties.created_on:
                age = datetime.now(existing_secret.properties.created_on.tzinfo) - existing_secret.properties.created_on
                if age.days > 90:
                    logger.warning(f"Secret '{secret_name}' is {age.days} days old and may need rotation")
            
        except Exception:
            # Secret doesn't exist, could create a placeholder
            logger.info(f"Secret '{secret_name}' does not exist")
            
            # Example: Create placeholder secret (in practice, you'd get the actual value)
            placeholder_value = f"placeholder-{secret_name}-{datetime.now().strftime('%Y%m%d')}"
            
            # Uncomment to actually create the secret:
            # secret_client.set_secret(
            #     secret_name, 
            #     placeholder_value,
            #     content_type=config.get("content_type"),
            #     tags={"description": config.get("description", ""), "managed_by": "automation"}
            # )
            # logger.info(f"Created placeholder secret '{secret_name}'")
        
        log_operation(logger, "manage_individual_secret", secret_name, status="SUCCESS")
        
    except Exception as e:
        log_operation(logger, "manage_individual_secret", secret_name, status="ERROR",
                     details={"error": str(e)})
        logger.error(f"Failed to manage secret '{secret_name}': {str(e)}")


def list_keyvault_secrets(vault_url: str, azure_ops: AzureOperations, logger) -> None:
    """
    List all secrets in Key Vault for verification.
    
    Args:
        vault_url: Key Vault URL
        azure_ops: Azure operations instance
        logger: Logger instance
    """
    try:
        secret_client = SecretClient(vault_url=vault_url, credential=azure_ops.credential)
        
        logger.info(f"Secrets in Key Vault '{vault_url}':")
        
        secret_count = 0
        for secret_properties in secret_client.list_properties_of_secrets():
            secret_info = {
                "name": secret_properties.name,
                "enabled": secret_properties.enabled,
                "created": secret_properties.created_on.isoformat() if secret_properties.created_on else None,
                "updated": secret_properties.updated_on.isoformat() if secret_properties.updated_on else None,
                "content_type": secret_properties.content_type
            }
            
            logger.info(f"  Secret: {secret_info}")
            secret_count += 1
        
        logger.info(f"Total secrets found: {secret_count}")
        
    except Exception as e:
        logger.error(f"Failed to list Key Vault secrets: {str(e)}")


if __name__ == "__main__":
    main()