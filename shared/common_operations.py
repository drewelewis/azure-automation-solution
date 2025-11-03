"""Common Azure operations for runbooks."""

import logging
from typing import List, Dict, Any, Optional
from azure.core.exceptions import AzureError
from shared.azure_auth import get_azure_credential, get_management_client
from shared.logging_utils import log_operation, log_azure_operation_result
from shared.config_manager import get_setting


logger = logging.getLogger(__name__)


class AzureOperations:
    """Common Azure operations wrapper."""
    
    def __init__(self, subscription_id: Optional[str] = None):
        """
        Initialize Azure operations.
        
        Args:
            subscription_id: Azure subscription ID
        """
        self.subscription_id = subscription_id or get_setting('azure.subscription_id')
        if not self.subscription_id:
            raise ValueError("Azure subscription ID is required")
            
        self.credential = get_azure_credential()
        self._clients = {}
    
    def get_client(self, service_type: str):
        """Get or create management client for service type."""
        if service_type not in self._clients:
            self._clients[service_type] = get_management_client(
                service_type, self.subscription_id, self.credential
            )
        return self._clients[service_type]
    
    def list_resource_groups(self) -> List[Dict[str, Any]]:
        """
        List all resource groups in subscription.
        
        Returns:
            List of resource group dictionaries
        """
        log_operation(logger, "list_resource_groups", status="START")
        
        try:
            resource_client = self.get_client('resource')
            resource_groups = []
            
            for rg in resource_client.resource_groups.list():
                resource_groups.append({
                    'name': rg.name,
                    'location': rg.location,
                    'id': rg.id,
                    'tags': rg.tags or {}
                })
            
            log_operation(logger, "list_resource_groups", status="SUCCESS", 
                        details={"count": len(resource_groups)})
            return resource_groups
            
        except AzureError as e:
            log_operation(logger, "list_resource_groups", status="ERROR", 
                        details={"error": str(e)})
            raise
    
    def get_resource_group(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get specific resource group.
        
        Args:
            name: Resource group name
            
        Returns:
            Resource group dictionary or None if not found
        """
        log_operation(logger, "get_resource_group", name, status="START")
        
        try:
            resource_client = self.get_client('resource')
            rg = resource_client.resource_groups.get(name)
            
            result = {
                'name': rg.name,
                'location': rg.location,
                'id': rg.id,
                'tags': rg.tags or {}
            }
            
            log_operation(logger, "get_resource_group", name, status="SUCCESS")
            return result
            
        except AzureError as e:
            if "ResourceGroupNotFound" in str(e):
                log_operation(logger, "get_resource_group", name, status="WARNING", 
                            details={"error": "Resource group not found"})
                return None
            else:
                log_operation(logger, "get_resource_group", name, status="ERROR", 
                            details={"error": str(e)})
                raise
    
    def list_vms_in_resource_group(self, resource_group: str) -> List[Dict[str, Any]]:
        """
        List virtual machines in a resource group.
        
        Args:
            resource_group: Resource group name
            
        Returns:
            List of VM dictionaries
        """
        log_operation(logger, "list_vms_in_resource_group", resource_group, status="START")
        
        try:
            compute_client = self.get_client('compute')
            vms = []
            
            for vm in compute_client.virtual_machines.list(resource_group):
                vm_dict = {
                    'name': vm.name,
                    'id': vm.id,
                    'location': vm.location,
                    'vm_size': vm.hardware_profile.vm_size,
                    'provisioning_state': vm.provisioning_state,
                    'tags': vm.tags or {}
                }
                
                # Get power state if available
                instance_view = compute_client.virtual_machines.instance_view(
                    resource_group, vm.name
                )
                if instance_view.statuses:
                    power_state = next(
                        (status.display_status for status in instance_view.statuses 
                         if status.code.startswith('PowerState')), 
                        'Unknown'
                    )
                    vm_dict['power_state'] = power_state
                
                vms.append(vm_dict)
            
            log_operation(logger, "list_vms_in_resource_group", resource_group, 
                        status="SUCCESS", details={"count": len(vms)})
            return vms
            
        except AzureError as e:
            log_operation(logger, "list_vms_in_resource_group", resource_group, 
                        status="ERROR", details={"error": str(e)})
            raise
    
    def start_vm(self, resource_group: str, vm_name: str) -> bool:
        """
        Start a virtual machine.
        
        Args:
            resource_group: Resource group name
            vm_name: Virtual machine name
            
        Returns:
            True if operation initiated successfully
        """
        vm_id = f"/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Compute/virtualMachines/{vm_name}"
        log_operation(logger, "start_vm", vm_id, status="START")
        
        try:
            compute_client = self.get_client('compute')
            operation = compute_client.virtual_machines.begin_start(resource_group, vm_name)
            
            log_operation(logger, "start_vm", vm_id, status="SUCCESS", 
                        details={"operation_id": operation.polling_method()._initial_response.headers.get('Azure-AsyncOperation')})
            return True
            
        except AzureError as e:
            log_operation(logger, "start_vm", vm_id, status="ERROR", 
                        details={"error": str(e)})
            raise
    
    def stop_vm(self, resource_group: str, vm_name: str, deallocate: bool = True) -> bool:
        """
        Stop a virtual machine.
        
        Args:
            resource_group: Resource group name
            vm_name: Virtual machine name
            deallocate: Whether to deallocate the VM (releases compute resources)
            
        Returns:
            True if operation initiated successfully
        """
        vm_id = f"/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Compute/virtualMachines/{vm_name}"
        operation_name = "deallocate_vm" if deallocate else "stop_vm"
        log_operation(logger, operation_name, vm_id, status="START")
        
        try:
            compute_client = self.get_client('compute')
            
            if deallocate:
                operation = compute_client.virtual_machines.begin_deallocate(resource_group, vm_name)
            else:
                operation = compute_client.virtual_machines.begin_power_off(resource_group, vm_name)
            
            log_operation(logger, operation_name, vm_id, status="SUCCESS")
            return True
            
        except AzureError as e:
            log_operation(logger, operation_name, vm_id, status="ERROR", 
                        details={"error": str(e)})
            raise