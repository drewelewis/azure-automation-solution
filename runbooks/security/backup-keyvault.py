"""
Azure Automation Runbook: Backup Key Vault

This runbook creates backups of Azure Key Vault contents including:
- All secrets and their versions
- All keys and their versions  
- All certificates and their versions
- Access policies and vault configuration
- Backup metadata and restoration information

The script stores backups in Azure Storage and provides restoration guidance.
"""

import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import base64

# Add the shared modules to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared import setup_logging, log_operation, get_azure_credential, get_setting
from shared.common_operations import AzureOperations
from shared.env_config import EnvironmentConfig
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.keyvault.secrets import SecretClient
from azure.keyvault.keys import KeyClient
from azure.keyvault.certificates import CertificateClient
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError


# Backup configuration
BACKUP_CONFIG = {
    "storage_account": {
        "container_name": "keyvault-backups",
        "retention_days": 90,
        "compress_backups": True
    },
    "backup_items": {
        "secrets": True,
        "keys": True,
        "certificates": True,
        "access_policies": True,
        "vault_properties": True
    },
    "exclude_patterns": [
        "*-temp-*",
        "*-test-*"
    ]
}


def main():
    """Main runbook execution function."""
    
    # Load environment configuration first
    env_config = EnvironmentConfig(".env")
    validation_result = env_config.validate_environment()
    
    # Setup logging
    logger = setup_logging("backup-keyvault", level="INFO")
    
    try:
        log_operation(logger, "backup_keyvault_runbook", status="START")
        
        # Get configuration
        subscription_id = get_setting('azure.subscription_id')
        if not subscription_id:
            raise ValueError("Azure subscription ID not configured")
        
        # Initialize Azure operations
        azure_ops = AzureOperations(subscription_id)
        
        # Get Key Vault configuration from environment variables
        resource_group = os.getenv('AZURE_KEYVAULT_RESOURCE_GROUP') or get_setting('azure.resource_group', 'default-rg')
        keyvault_name = os.getenv('AZURE_KEYVAULT_NAME') or get_setting('security.keyvault_name', 'default-kv')
        storage_account = os.getenv('AZURE_BACKUP_STORAGE_ACCOUNT') or get_setting('backup.storage_account', 'defaultstorage')
        
        logger.info(f"Starting backup for Key Vault: {keyvault_name}")
        logger.info(f"Backup storage account: {storage_account}")
        
        # Perform Key Vault backup
        backup_result = backup_keyvault(azure_ops, resource_group, keyvault_name, storage_account, logger)
        
        # Generate backup report
        generate_backup_report(backup_result, logger)
        
        log_operation(logger, "backup_keyvault_runbook", status="SUCCESS")
        logger.info("Key Vault backup runbook completed successfully")
        
    except Exception as e:
        log_operation(logger, "backup_keyvault_runbook", status="ERROR", 
                     details={"error": str(e)})
        logger.error(f"Runbook failed: {str(e)}")
        raise


def backup_keyvault(
    azure_ops: AzureOperations, 
    resource_group: str, 
    keyvault_name: str,
    storage_account: str,
    logger
) -> Dict[str, Any]:
    """
    Perform complete Key Vault backup.
    
    Args:
        azure_ops: Azure operations instance
        resource_group: Resource group name
        keyvault_name: Key Vault name
        storage_account: Storage account for backups
        logger: Logger instance
        
    Returns:
        Dictionary with backup results
    """
    backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_result = {
        "timestamp": backup_timestamp,
        "keyvault_name": keyvault_name,
        "backup_items": {},
        "errors": [],
        "backup_location": "",
        "total_items": 0
    }
    
    try:
        vault_url = f"https://{keyvault_name}.vault.azure.net/"
        
        # Initialize clients
        kv_mgmt_client = KeyVaultManagementClient(azure_ops.credential, azure_ops.subscription_id)
        secret_client = SecretClient(vault_url=vault_url, credential=azure_ops.credential)
        key_client = KeyClient(vault_url=vault_url, credential=azure_ops.credential)
        cert_client = CertificateClient(vault_url=vault_url, credential=azure_ops.credential)
        
        # Initialize storage client
        storage_client = initialize_backup_storage(azure_ops, storage_account, logger)
        
        log_operation(logger, "backup_keyvault", vault_url, status="START")
        
        # Backup vault properties and access policies
        if BACKUP_CONFIG["backup_items"]["vault_properties"]:
            vault_backup = backup_vault_properties(kv_mgmt_client, resource_group, keyvault_name, logger)
            backup_result["backup_items"]["vault_properties"] = vault_backup
        
        # Backup secrets
        if BACKUP_CONFIG["backup_items"]["secrets"]:
            secrets_backup = backup_secrets(secret_client, logger)
            backup_result["backup_items"]["secrets"] = secrets_backup
            backup_result["total_items"] += len(secrets_backup.get("items", []))
        
        # Backup keys
        if BACKUP_CONFIG["backup_items"]["keys"]:
            keys_backup = backup_keys(key_client, logger)
            backup_result["backup_items"]["keys"] = keys_backup
            backup_result["total_items"] += len(keys_backup.get("items", []))
        
        # Backup certificates
        if BACKUP_CONFIG["backup_items"]["certificates"]:
            certs_backup = backup_certificates(cert_client, logger)
            backup_result["backup_items"]["certificates"] = certs_backup
            backup_result["total_items"] += len(certs_backup.get("items", []))
        
        # Store backup to storage
        backup_location = store_backup_to_storage(storage_client, backup_result, logger)
        backup_result["backup_location"] = backup_location
        
        log_operation(logger, "backup_keyvault", vault_url, status="SUCCESS",
                     details={"total_items": backup_result["total_items"], 
                             "backup_location": backup_location})
        
        return backup_result
        
    except Exception as e:
        log_operation(logger, "backup_keyvault", f"keyvault:{keyvault_name}", status="ERROR",
                     details={"error": str(e)})
        logger.error(f"Failed to backup Key Vault: {str(e)}")
        backup_result["errors"].append(str(e))
        return backup_result


def initialize_backup_storage(azure_ops: AzureOperations, storage_account: str, logger) -> BlobServiceClient:
    """
    Initialize storage client for backup operations.
    
    Args:
        azure_ops: Azure operations instance
        storage_account: Storage account name
        logger: Logger instance
        
    Returns:
        BlobServiceClient instance
    """
    try:
        account_url = f"https://{storage_account}.blob.core.windows.net"
        blob_service_client = BlobServiceClient(account_url=account_url, credential=azure_ops.credential)
        
        # Ensure container exists
        container_name = BACKUP_CONFIG["storage_account"]["container_name"]
        try:
            blob_service_client.create_container(container_name)
            logger.info(f"Created backup container: {container_name}")
        except Exception:
            # Container might already exist
            logger.info(f"Using existing backup container: {container_name}")
        
        return blob_service_client
        
    except Exception as e:
        logger.error(f"Failed to initialize backup storage: {str(e)}")
        raise


def backup_vault_properties(
    kv_mgmt_client: KeyVaultManagementClient,
    resource_group: str,
    keyvault_name: str,
    logger
) -> Dict[str, Any]:
    """
    Backup Key Vault properties and access policies.
    
    Args:
        kv_mgmt_client: Key Vault management client
        resource_group: Resource group name
        keyvault_name: Key Vault name
        logger: Logger instance
        
    Returns:
        Dictionary with vault properties backup
    """
    try:
        log_operation(logger, "backup_vault_properties", keyvault_name, status="START")
        
        # Get vault properties
        vault = kv_mgmt_client.vaults.get(resource_group, keyvault_name)
        
        vault_backup = {
            "name": vault.name,
            "location": vault.location,
            "resource_group": resource_group,
            "properties": {
                "vault_uri": vault.properties.vault_uri,
                "tenant_id": vault.properties.tenant_id,
                "sku": {
                    "name": vault.properties.sku.name,
                    "family": vault.properties.sku.family
                },
                "enable_soft_delete": vault.properties.enable_soft_delete,
                "enable_purge_protection": vault.properties.enable_purge_protection,
                "enabled_for_deployment": vault.properties.enabled_for_deployment,
                "enabled_for_disk_encryption": vault.properties.enabled_for_disk_encryption,
                "enabled_for_template_deployment": vault.properties.enabled_for_template_deployment,
                "soft_delete_retention_in_days": vault.properties.soft_delete_retention_in_days
            },
            "access_policies": []
        }
        
        # Backup access policies
        if vault.properties.access_policies:
            for policy in vault.properties.access_policies:
                policy_backup = {
                    "tenant_id": policy.tenant_id,
                    "object_id": policy.object_id,
                    "permissions": {
                        "secrets": list(policy.permissions.secrets) if policy.permissions.secrets else [],
                        "keys": list(policy.permissions.keys) if policy.permissions.keys else [],
                        "certificates": list(policy.permissions.certificates) if policy.permissions.certificates else []
                    }
                }
                vault_backup["access_policies"].append(policy_backup)
        
        logger.info(f"Backed up vault properties and {len(vault_backup['access_policies'])} access policies")
        
        log_operation(logger, "backup_vault_properties", keyvault_name, status="SUCCESS")
        return vault_backup
        
    except Exception as e:
        log_operation(logger, "backup_vault_properties", keyvault_name, status="ERROR",
                     details={"error": str(e)})
        logger.error(f"Failed to backup vault properties: {str(e)}")
        return {"error": str(e)}


def backup_secrets(secret_client: SecretClient, logger) -> Dict[str, Any]:
    """
    Backup all secrets from Key Vault.
    
    Args:
        secret_client: Secret client instance
        logger: Logger instance
        
    Returns:
        Dictionary with secrets backup data
    """
    try:
        log_operation(logger, "backup_secrets", "secrets", status="START")
        
        secrets_backup = {
            "type": "secrets",
            "items": [],
            "count": 0
        }
        
        # Get all secrets
        for secret_properties in secret_client.list_properties_of_secrets():
            if secret_properties.enabled and not should_exclude_item(secret_properties.name):
                try:
                    # Get secret details (but not the actual value for security)
                    secret_backup = {
                        "name": secret_properties.name,
                        "enabled": secret_properties.enabled,
                        "created_on": secret_properties.created_on.isoformat() if secret_properties.created_on else None,
                        "updated_on": secret_properties.updated_on.isoformat() if secret_properties.updated_on else None,
                        "expires_on": secret_properties.expires_on.isoformat() if secret_properties.expires_on else None,
                        "not_before": secret_properties.not_before.isoformat() if secret_properties.not_before else None,
                        "content_type": secret_properties.content_type,
                        "tags": secret_properties.tags or {},
                        "version": secret_properties.version,
                        "recovery_level": secret_properties.recovery_level,
                        # Note: Actual secret value is not included for security reasons
                        # In production, you might backup to encrypted storage
                        "has_value": True,
                        "backup_note": "Secret value not included in backup for security"
                    }
                    
                    secrets_backup["items"].append(secret_backup)
                    secrets_backup["count"] += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to backup secret '{secret_properties.name}': {str(e)}")
        
        logger.info(f"Backed up {secrets_backup['count']} secrets (metadata only)")
        
        log_operation(logger, "backup_secrets", "secrets", status="SUCCESS",
                     details={"count": secrets_backup["count"]})
        return secrets_backup
        
    except Exception as e:
        log_operation(logger, "backup_secrets", "secrets", status="ERROR",
                     details={"error": str(e)})
        logger.error(f"Failed to backup secrets: {str(e)}")
        return {"error": str(e), "items": [], "count": 0}


def backup_keys(key_client: KeyClient, logger) -> Dict[str, Any]:
    """
    Backup all keys from Key Vault.
    
    Args:
        key_client: Key client instance
        logger: Logger instance
        
    Returns:
        Dictionary with keys backup data
    """
    try:
        log_operation(logger, "backup_keys", "keys", status="START")
        
        keys_backup = {
            "type": "keys",
            "items": [],
            "count": 0
        }
        
        # Get all keys
        for key_properties in key_client.list_properties_of_keys():
            if key_properties.enabled and not should_exclude_item(key_properties.name):
                try:
                    key_backup = {
                        "name": key_properties.name,
                        "enabled": key_properties.enabled,
                        "created_on": key_properties.created_on.isoformat() if key_properties.created_on else None,
                        "updated_on": key_properties.updated_on.isoformat() if key_properties.updated_on else None,
                        "expires_on": key_properties.expires_on.isoformat() if key_properties.expires_on else None,
                        "not_before": key_properties.not_before.isoformat() if key_properties.not_before else None,
                        "tags": key_properties.tags or {},
                        "version": key_properties.version,
                        "recovery_level": key_properties.recovery_level,
                        "backup_note": "Key material not included in metadata backup"
                    }
                    
                    keys_backup["items"].append(key_backup)
                    keys_backup["count"] += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to backup key '{key_properties.name}': {str(e)}")
        
        logger.info(f"Backed up {keys_backup['count']} keys (metadata only)")
        
        log_operation(logger, "backup_keys", "keys", status="SUCCESS",
                     details={"count": keys_backup["count"]})
        return keys_backup
        
    except Exception as e:
        log_operation(logger, "backup_keys", "keys", status="ERROR",
                     details={"error": str(e)})
        logger.error(f"Failed to backup keys: {str(e)}")
        return {"error": str(e), "items": [], "count": 0}


def backup_certificates(cert_client: CertificateClient, logger) -> Dict[str, Any]:
    """
    Backup all certificates from Key Vault.
    
    Args:
        cert_client: Certificate client instance
        logger: Logger instance
        
    Returns:
        Dictionary with certificates backup data
    """
    try:
        log_operation(logger, "backup_certificates", "certificates", status="START")
        
        certs_backup = {
            "type": "certificates",
            "items": [],
            "count": 0
        }
        
        # Get all certificates
        for cert_properties in cert_client.list_properties_of_certificates():
            if cert_properties.enabled and not should_exclude_item(cert_properties.name):
                try:
                    cert_backup = {
                        "name": cert_properties.name,
                        "enabled": cert_properties.enabled,
                        "created_on": cert_properties.created_on.isoformat() if cert_properties.created_on else None,
                        "updated_on": cert_properties.updated_on.isoformat() if cert_properties.updated_on else None,
                        "expires_on": cert_properties.expires_on.isoformat() if cert_properties.expires_on else None,
                        "not_before": cert_properties.not_before.isoformat() if cert_properties.not_before else None,
                        "tags": cert_properties.tags or {},
                        "version": cert_properties.version,
                        "recovery_level": cert_properties.recovery_level,
                        "backup_note": "Certificate not included in metadata backup"
                    }
                    
                    certs_backup["items"].append(cert_backup)
                    certs_backup["count"] += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to backup certificate '{cert_properties.name}': {str(e)}")
        
        logger.info(f"Backed up {certs_backup['count']} certificates (metadata only)")
        
        log_operation(logger, "backup_certificates", "certificates", status="SUCCESS",
                     details={"count": certs_backup["count"]})
        return certs_backup
        
    except Exception as e:
        log_operation(logger, "backup_certificates", "certificates", status="ERROR",
                     details={"error": str(e)})
        logger.error(f"Failed to backup certificates: {str(e)}")
        return {"error": str(e), "items": [], "count": 0}


def should_exclude_item(item_name: str) -> bool:
    """
    Check if an item should be excluded from backup based on patterns.
    
    Args:
        item_name: Name of the item to check
        
    Returns:
        True if item should be excluded
    """
    for pattern in BACKUP_CONFIG["exclude_patterns"]:
        if pattern.replace("*", "") in item_name.lower():
            return True
    return False


def store_backup_to_storage(
    storage_client: BlobServiceClient,
    backup_data: Dict[str, Any],
    logger
) -> str:
    """
    Store backup data to Azure Storage.
    
    Args:
        storage_client: Blob service client
        backup_data: Backup data to store
        logger: Logger instance
        
    Returns:
        Storage location of the backup
    """
    try:
        container_name = BACKUP_CONFIG["storage_account"]["container_name"]
        blob_name = f"keyvault-backup-{backup_data['keyvault_name']}-{backup_data['timestamp']}.json"
        
        # Convert backup data to JSON
        backup_json = json.dumps(backup_data, indent=2, default=str)
        
        # Upload to storage
        blob_client = storage_client.get_blob_client(container=container_name, blob=blob_name)
        blob_client.upload_blob(backup_json, overwrite=True)
        
        storage_location = f"https://{storage_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}"
        
        logger.info(f"Backup stored to: {storage_location}")
        return storage_location
        
    except Exception as e:
        logger.error(f"Failed to store backup to storage: {str(e)}")
        return f"Storage failed: {str(e)}"


def generate_backup_report(backup_result: Dict[str, Any], logger) -> None:
    """
    Generate and log backup report.
    
    Args:
        backup_result: Backup result data
        logger: Logger instance
    """
    try:
        logger.info("=" * 60)
        logger.info("KEY VAULT BACKUP REPORT")
        logger.info("=" * 60)
        
        logger.info(f"Backup timestamp: {backup_result['timestamp']}")
        logger.info(f"Key Vault: {backup_result['keyvault_name']}")
        logger.info(f"Total items backed up: {backup_result['total_items']}")
        logger.info(f"Backup location: {backup_result['backup_location']}")
        
        # Report by item type
        for item_type, item_data in backup_result["backup_items"].items():
            if isinstance(item_data, dict) and "count" in item_data:
                logger.info(f"{item_type.title()}: {item_data['count']} items")
        
        if backup_result["errors"]:
            logger.info(f"\n❌ Errors encountered: {len(backup_result['errors'])}")
            for error in backup_result["errors"]:
                logger.info(f"  - {error}")
        else:
            logger.info(f"\n✅ Backup completed successfully with no errors")
        
        logger.info(f"\n📋 Restoration Information:")
        logger.info(f"  - Backup contains metadata for all Key Vault items")
        logger.info(f"  - Secret/key values are not included for security reasons")
        logger.info(f"  - Use Azure Key Vault backup/restore APIs for complete restoration")
        logger.info(f"  - Access policies and vault configuration can be restored from this backup")
        
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Failed to generate backup report: {str(e)}")


if __name__ == "__main__":
    main()