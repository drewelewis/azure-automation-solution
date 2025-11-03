"""
Azure Automation Runbook: Update Key Vault Access Policies

This runbook manages Azure Key Vault access policies including:
- Adding/removing service principals and users
- Updating permissions for secrets, keys, and certificates
- Managing application access policies
- Bulk access policy operations

The script loads access policy configuration from environment variables and provides
comprehensive logging and policy validation.
"""

import sys
import os
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass

# Add the shared modules to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared import setup_logging, log_operation, get_azure_credential, get_setting
from shared.common_operations import AzureOperations
from shared.env_config import EnvironmentConfig
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.mgmt.keyvault.models import (
    AccessPolicyEntry, 
    Permissions, 
    SecretPermissions, 
    KeyPermissions, 
    CertificatePermissions,
    VaultPatchParameters,
    VaultPatchProperties
)
from azure.core.exceptions import AzureError


@dataclass
class AccessPolicyConfig:
    """Configuration for an access policy."""
    object_id: str
    tenant_id: str
    display_name: str = ""
    secret_permissions: List[str] = None
    key_permissions: List[str] = None
    certificate_permissions: List[str] = None
    enabled: bool = True


# Access policy configurations
# In practice, these would come from environment variables or configuration files
ACCESS_POLICY_CONFIGS = {
    "automation_service": {
        "description": "Azure Automation service principal",
        "secret_permissions": ["get", "list", "set"],
        "key_permissions": ["get", "list"],
        "certificate_permissions": ["get", "list"],
        "enabled": True
    },
    "application_service": {
        "description": "Application service principal",
        "secret_permissions": ["get"],
        "key_permissions": ["get", "decrypt", "sign"],
        "certificate_permissions": ["get"],
        "enabled": True
    },
    "backup_service": {
        "description": "Backup service principal",
        "secret_permissions": ["backup", "get", "list"],
        "key_permissions": ["backup", "get", "list"],
        "certificate_permissions": ["backup", "get", "list"],
        "enabled": False  # Disabled by default
    }
}


def main():
    """Main runbook execution function."""
    
    # Load environment configuration first
    env_config = EnvironmentConfig(".env")
    validation_result = env_config.validate_environment()
    
    # Setup logging
    logger = setup_logging("update-access-policies", level="INFO")
    
    try:
        log_operation(logger, "update_access_policies_runbook", status="START")
        
        # Get configuration
        subscription_id = get_setting('azure.subscription_id')
        if not subscription_id:
            raise ValueError("Azure subscription ID not configured")
        
        # Initialize Azure operations
        azure_ops = AzureOperations(subscription_id)
        
        # Get Key Vault configuration from environment variables
        resource_group = os.getenv('AZURE_KEYVAULT_RESOURCE_GROUP') or get_setting('azure.resource_group', 'default-rg')
        keyvault_name = os.getenv('AZURE_KEYVAULT_NAME') or get_setting('security.keyvault_name', 'default-kv')
        
        logger.info(f"Updating access policies for Key Vault: {keyvault_name} in resource group: {resource_group}")
        
        # Perform access policy updates
        update_access_policies(azure_ops, resource_group, keyvault_name, logger)
        
        log_operation(logger, "update_access_policies_runbook", status="SUCCESS")
        logger.info("Access policies update runbook completed successfully")
        
    except Exception as e:
        log_operation(logger, "update_access_policies_runbook", status="ERROR", 
                     details={"error": str(e)})
        logger.error(f"Runbook failed: {str(e)}")
        raise


def update_access_policies(
    azure_ops: AzureOperations, 
    resource_group: str, 
    keyvault_name: str, 
    logger
) -> None:
    """
    Update Key Vault access policies.
    
    Args:
        azure_ops: Azure operations instance
        resource_group: Resource group name
        keyvault_name: Key Vault name
        logger: Logger instance
    """
    keyvault_id = f"/subscriptions/{azure_ops.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.KeyVault/vaults/{keyvault_name}"
    
    try:
        # Get Key Vault management client
        kv_mgmt_client = KeyVaultManagementClient(azure_ops.credential, azure_ops.subscription_id)
        
        log_operation(logger, "get_keyvault_access_policies", keyvault_id, status="START")
        
        # Get existing Key Vault and access policies
        keyvault = kv_mgmt_client.vaults.get(resource_group, keyvault_name)
        current_policies = keyvault.properties.access_policies or []
        
        log_operation(logger, "get_keyvault_access_policies", keyvault_id, status="SUCCESS")
        logger.info(f"Found {len(current_policies)} existing access policies")
        
        # Analyze current policies
        analyze_current_policies(current_policies, logger)
        
        # Load desired access policies from environment/configuration
        desired_policies = load_desired_access_policies(logger)
        
        # Compare and update policies
        policy_changes = compare_and_plan_changes(current_policies, desired_policies, logger)
        
        # Apply changes if any
        if policy_changes["add"] or policy_changes["remove"] or policy_changes["update"]:
            apply_access_policy_changes(kv_mgmt_client, resource_group, keyvault_name, 
                                      current_policies, policy_changes, logger)
        else:
            logger.info("No access policy changes required")
        
        # Verify final state
        verify_access_policies(kv_mgmt_client, resource_group, keyvault_name, logger)
        
    except AzureError as e:
        log_operation(logger, "update_access_policies", keyvault_id, status="ERROR", 
                     details={"error": str(e)})
        logger.error(f"Failed to update access policies: {str(e)}")
        raise


def analyze_current_policies(policies: List[AccessPolicyEntry], logger) -> None:
    """
    Analyze and log current access policies.
    
    Args:
        policies: List of current access policy entries
        logger: Logger instance
    """
    try:
        logger.info("Current Access Policies Analysis:")
        
        for i, policy in enumerate(policies):
            policy_info = {
                "index": i,
                "object_id": policy.object_id,
                "tenant_id": policy.tenant_id,
                "secret_permissions": list(policy.permissions.secrets) if policy.permissions.secrets else [],
                "key_permissions": list(policy.permissions.keys) if policy.permissions.keys else [],
                "certificate_permissions": list(policy.permissions.certificates) if policy.permissions.certificates else []
            }
            
            logger.info(f"  Policy {i + 1}: {policy_info}")
            
    except Exception as e:
        logger.error(f"Failed to analyze current policies: {str(e)}")


def load_desired_access_policies(logger) -> List[AccessPolicyConfig]:
    """
    Load desired access policies from environment variables and configuration.
    
    Args:
        logger: Logger instance
        
    Returns:
        List of desired access policy configurations
    """
    desired_policies = []
    
    try:
        # Load from environment variables
        # Format: KEYVAULT_ACCESS_POLICY_<NAME>_OBJECT_ID, etc.
        
        for policy_name, config in ACCESS_POLICY_CONFIGS.items():
            if config.get("enabled", True):
                # Try to get object ID from environment
                object_id_var = f"KEYVAULT_ACCESS_POLICY_{policy_name.upper()}_OBJECT_ID"
                tenant_id_var = f"KEYVAULT_ACCESS_POLICY_{policy_name.upper()}_TENANT_ID"
                
                object_id = os.getenv(object_id_var)
                tenant_id = os.getenv(tenant_id_var, os.getenv('AZURE_TENANT_ID'))
                
                if object_id and tenant_id:
                    policy_config = AccessPolicyConfig(
                        object_id=object_id,
                        tenant_id=tenant_id,
                        display_name=f"{policy_name} ({config['description']})",
                        secret_permissions=config.get("secret_permissions", []),
                        key_permissions=config.get("key_permissions", []),
                        certificate_permissions=config.get("certificate_permissions", []),
                        enabled=config.get("enabled", True)
                    )
                    
                    desired_policies.append(policy_config)
                    logger.info(f"Loaded desired policy for {policy_name}: {object_id}")
                else:
                    logger.warning(f"Missing environment variables for policy {policy_name}: {object_id_var}, {tenant_id_var}")
        
        logger.info(f"Loaded {len(desired_policies)} desired access policies")
        return desired_policies
        
    except Exception as e:
        logger.error(f"Failed to load desired access policies: {str(e)}")
        return []


def compare_and_plan_changes(
    current_policies: List[AccessPolicyEntry], 
    desired_policies: List[AccessPolicyConfig], 
    logger
) -> Dict[str, List]:
    """
    Compare current and desired policies and plan changes.
    
    Args:
        current_policies: Current access policy entries
        desired_policies: Desired access policy configurations
        logger: Logger instance
        
    Returns:
        Dictionary with planned changes
    """
    changes = {
        "add": [],
        "remove": [],
        "update": []
    }
    
    try:
        # Create lookup sets for comparison
        current_object_ids = {policy.object_id for policy in current_policies}
        desired_object_ids = {policy.object_id for policy in desired_policies}
        
        # Find policies to add
        for desired_policy in desired_policies:
            if desired_policy.object_id not in current_object_ids:
                changes["add"].append(desired_policy)
                logger.info(f"Planning to ADD policy for: {desired_policy.display_name}")
        
        # Find policies to remove or update
        for current_policy in current_policies:
            desired_policy = next(
                (p for p in desired_policies if p.object_id == current_policy.object_id), 
                None
            )
            
            if desired_policy is None:
                # Policy exists but not in desired state - could be removed
                logger.info(f"Current policy {current_policy.object_id} not in desired policies (manual review required)")
            else:
                # Check if update is needed
                if needs_policy_update(current_policy, desired_policy):
                    changes["update"].append((current_policy, desired_policy))
                    logger.info(f"Planning to UPDATE policy for: {desired_policy.display_name}")
        
        logger.info(f"Planned changes - Add: {len(changes['add'])}, Remove: {len(changes['remove'])}, Update: {len(changes['update'])}")
        return changes
        
    except Exception as e:
        logger.error(f"Failed to compare and plan changes: {str(e)}")
        return {"add": [], "remove": [], "update": []}


def needs_policy_update(current_policy: AccessPolicyEntry, desired_policy: AccessPolicyConfig) -> bool:
    """
    Check if a policy needs to be updated.
    
    Args:
        current_policy: Current access policy entry
        desired_policy: Desired access policy configuration
        
    Returns:
        True if update is needed
    """
    try:
        # Compare permissions
        current_secrets = set(current_policy.permissions.secrets or [])
        desired_secrets = set(desired_policy.secret_permissions or [])
        
        current_keys = set(current_policy.permissions.keys or [])
        desired_keys = set(desired_policy.key_permissions or [])
        
        current_certificates = set(current_policy.permissions.certificates or [])
        desired_certificates = set(desired_policy.certificate_permissions or [])
        
        return (current_secrets != desired_secrets or 
                current_keys != desired_keys or 
                current_certificates != desired_certificates)
        
    except Exception:
        return True  # If comparison fails, assume update is needed


def apply_access_policy_changes(
    kv_mgmt_client: KeyVaultManagementClient,
    resource_group: str,
    keyvault_name: str,
    current_policies: List[AccessPolicyEntry],
    changes: Dict[str, List],
    logger
) -> None:
    """
    Apply access policy changes to Key Vault.
    
    Args:
        kv_mgmt_client: Key Vault management client
        resource_group: Resource group name
        keyvault_name: Key Vault name
        current_policies: Current access policies
        changes: Planned changes
        logger: Logger instance
    """
    try:
        log_operation(logger, "apply_access_policy_changes", keyvault_name, status="START")
        
        # Create new policies list
        new_policies = list(current_policies)
        
        # Apply updates
        for current_policy, desired_policy in changes["update"]:
            # Find and update the policy
            for i, policy in enumerate(new_policies):
                if policy.object_id == current_policy.object_id:
                    new_policies[i] = create_access_policy_entry(desired_policy)
                    logger.info(f"Updated policy for object ID: {desired_policy.object_id}")
                    break
        
        # Add new policies
        for desired_policy in changes["add"]:
            new_policy_entry = create_access_policy_entry(desired_policy)
            new_policies.append(new_policy_entry)
            logger.info(f"Added policy for object ID: {desired_policy.object_id}")
        
        # Apply the changes
        vault_patch = VaultPatchParameters(
            properties=VaultPatchProperties(
                access_policies=new_policies
            )
        )
        
        update_operation = kv_mgmt_client.vaults.update(resource_group, keyvault_name, vault_patch)
        
        log_operation(logger, "apply_access_policy_changes", keyvault_name, status="SUCCESS",
                     details={"total_policies": len(new_policies), 
                             "added": len(changes["add"]), 
                             "updated": len(changes["update"])})
        
        logger.info(f"Successfully applied access policy changes to Key Vault: {keyvault_name}")
        
    except Exception as e:
        log_operation(logger, "apply_access_policy_changes", keyvault_name, status="ERROR",
                     details={"error": str(e)})
        logger.error(f"Failed to apply access policy changes: {str(e)}")
        raise


def create_access_policy_entry(policy_config: AccessPolicyConfig) -> AccessPolicyEntry:
    """
    Create an AccessPolicyEntry from configuration.
    
    Args:
        policy_config: Access policy configuration
        
    Returns:
        AccessPolicyEntry object
    """
    permissions = Permissions(
        secrets=policy_config.secret_permissions,
        keys=policy_config.key_permissions,
        certificates=policy_config.certificate_permissions
    )
    
    return AccessPolicyEntry(
        tenant_id=policy_config.tenant_id,
        object_id=policy_config.object_id,
        permissions=permissions
    )


def verify_access_policies(
    kv_mgmt_client: KeyVaultManagementClient,
    resource_group: str,
    keyvault_name: str,
    logger
) -> None:
    """
    Verify the final state of access policies.
    
    Args:
        kv_mgmt_client: Key Vault management client
        resource_group: Resource group name
        keyvault_name: Key Vault name
        logger: Logger instance
    """
    try:
        # Get updated Key Vault
        keyvault = kv_mgmt_client.vaults.get(resource_group, keyvault_name)
        final_policies = keyvault.properties.access_policies or []
        
        logger.info("=" * 60)
        logger.info("FINAL ACCESS POLICIES VERIFICATION")
        logger.info("=" * 60)
        logger.info(f"Total access policies: {len(final_policies)}")
        
        for i, policy in enumerate(final_policies):
            logger.info(f"Policy {i + 1}:")
            logger.info(f"  Object ID: {policy.object_id}")
            logger.info(f"  Tenant ID: {policy.tenant_id}")
            logger.info(f"  Secret Permissions: {list(policy.permissions.secrets) if policy.permissions.secrets else []}")
            logger.info(f"  Key Permissions: {list(policy.permissions.keys) if policy.permissions.keys else []}")
            logger.info(f"  Certificate Permissions: {list(policy.permissions.certificates) if policy.permissions.certificates else []}")
        
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Failed to verify access policies: {str(e)}")


if __name__ == "__main__":
    main()