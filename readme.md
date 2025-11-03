# Azure Automation Solution

A comprehensive Azure Automation solution for managing cloud infrastructure through runbooks, featuring environment-based configuration, robust logging, and common Azure operations.

## 🏗️ Architecture Overview

This solution provides a structured approach to Azure Automation with:

- **Environment-based Configuration**: Uses `.env` files instead of JSON configs for flexibility
- **Modular Runbooks**: Organized by service category (compute, networking, security, storage)
- **Shared Utilities**: Reusable authentication, logging, and common operations
- **Local Development Support**: Test and develop runbooks locally before deployment

## 📁 Project Structure

```
azure-automation-solution/
├── .env                        # Environment configuration
├── requirements.txt            # Python dependencies
├── setup.py                   # Package setup
├── shared/                    # Shared utilities
│   ├── __init__.py
│   ├── azure_auth.py          # Authentication utilities
│   ├── common_operations.py   # Common Azure operations
│   ├── config_manager.py      # Configuration management
│   ├── env_config.py          # Environment variable loading
│   ├── logging_utils.py       # Logging utilities
│   └── simple_config.py       # Simple configuration loader
├── runbooks/                  # Azure Automation runbooks
│   ├── compute/               # VM and compute operations
│   ├── networking/            # Network security and configuration
│   │   └── update-nsg.py     # NSG security rule management
│   ├── security/              # Security and compliance
│   └── storage/               # Storage account operations
├── config/                    # JSON config files (optional)
│   ├── dev.json              # Development environment (optional)
│   └── prod.json             # Production environment (optional)
├── tests/                     # Unit and integration tests
└── docs/                      # Documentation
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Azure CLI installed and authenticated
- Azure subscription with appropriate permissions

### 1. Clone and Setup

```bash
git clone <repository-url>
cd azure-automation-solution
python -m venv .venv
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. Configure Environment

Create or update your `.env` file with your Azure configuration:

```bash
# Azure Core Configuration
AZURE_SUBSCRIPTION_ID=your-subscription-id
AZURE_TENANT_ID=your-tenant-id

# Azure Automation Configuration
AZURE_AUTOMATION_ACCOUNT=your-automation-account
AZURE_AUTOMATION_RESOURCE_GROUP=your-automation-rg
AZURE_AUTOMATION_REGION=eastus2

# Environment Configuration
AZURE_ENVIRONMENT=dev
LOG_LEVEL=INFO

# Authentication Settings
USE_MANAGED_IDENTITY=false
AZURE_CLI_AUTH=true

# Network Security Group Configuration
AZURE_NSG_RESOURCE_GROUP=your-nsg-resource-group
AZURE_NSG_NAME=your-nsg-name
EDGE_GATEWAY_IP=203.0.113.10
```

### 3. Authenticate with Azure

```bash
az login
az account set --subscription "your-subscription-id"
```

### 4. Test Configuration

```bash
python test_config_env_only.py
```

## 🔧 Configuration System

The solution uses a flexible configuration system that prioritizes environment variables over JSON files:

### Environment Variables (Recommended)

All configuration is loaded from `.env` file with these key variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID | ✅ |
| `AZURE_TENANT_ID` | Azure tenant ID | ✅ |
| `AZURE_AUTOMATION_ACCOUNT` | Automation account name | ✅ |
| `AZURE_AUTOMATION_RESOURCE_GROUP` | Automation account resource group | ✅ |
| `USE_MANAGED_IDENTITY` | Use managed identity (true/false) | ✅ |
| `AZURE_CLI_AUTH` | Use Azure CLI authentication (true/false) | ✅ |
| `EDGE_GATEWAY_IP` | Edge gateway IP for NSG rules | ❌ |
| `AZURE_NSG_RESOURCE_GROUP` | NSG resource group | ❌ |
| `AZURE_NSG_NAME` | NSG name | ❌ |

### JSON Configuration Files (Optional)

The system supports optional JSON config files in the `config/` directory, but environment variables take precedence.

## 📚 Runbooks

### Network Security Group (NSG) Management

**File**: `runbooks/networking/update-nsg.py`

Manages Network Security Group rules to allow traffic from specified edge gateway IPs.

**Features**:
- Loads edge gateway IP from environment variables
- Creates security rules for HTTPS (443), SSH (22), and HTTP (80)
- Updates existing rules if source IP changes
- Comprehensive logging and error handling

**Usage**:
```python
from shared import setup_logging, get_azure_credential
from runbooks.networking.update_nsg import main

# Configure your .env file with NSG details
# Run the script
main()
```

**Created Security Rules**:
- `AllowEdgeGatewayHTTPS`: Allow HTTPS traffic from edge gateway
- `AllowEdgeGatewaySSH`: Allow SSH management from edge gateway  
- `AllowEdgeGatewayHTTP`: Allow HTTP traffic from edge gateway

## 🔐 Authentication

The solution supports multiple authentication methods:

### Local Development
- **Azure CLI**: Set `AZURE_CLI_AUTH=true` and `USE_MANAGED_IDENTITY=false`
- **Service Principal**: Set environment variables for `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`

### Azure Automation
- **Managed Identity**: Set `USE_MANAGED_IDENTITY=true` when running in Azure Automation

## 🛠️ Shared Utilities

### Azure Authentication (`azure_auth.py`)
- Handles multiple authentication methods
- Automatic credential selection based on environment
- Support for local development and Azure Automation

### Common Operations (`common_operations.py`)
- Reusable Azure operations wrapper
- Resource group management
- Virtual machine operations
- Client caching for performance

### Configuration Management (`config_manager.py`)
- Environment variable priority over JSON files
- Dot notation support for nested configuration
- Automatic environment variable mapping

### Logging (`logging_utils.py`)
- Structured logging with operation tracking
- Azure-specific log formatting
- Performance and error monitoring

## 🧪 Testing

### Environment Configuration Test
```bash
python test_config_env_only.py
```

### NSG Connection Test
```bash
python test_nsg_connection.py
```

### Simple Environment Loading Test
```bash
python test_simple_env.py
```

## � Deployment

### Deployment Options

This solution supports multiple deployment approaches depending on your needs:

1. **Azure Automation Account** - Traditional Azure Automation runbooks
2. **Azure Functions** - Serverless execution with HTTP triggers
3. **Azure Container Instances** - Containerized deployment
4. **Local/On-Premises** - Direct execution with Azure CLI authentication

### Option 1: Azure Automation Account Deployment

#### Prerequisites
- Azure Automation Account created
- Managed Identity enabled on the Automation Account
- Required Azure RBAC permissions assigned to the managed identity

#### Step 1: Prepare the Deployment Package

```bash
# Create deployment directory
mkdir deployment
cd deployment

# Copy required files
cp -r ../runbooks .
cp -r ../shared .
cp ../requirements.txt .

# Create automation-specific requirements.txt (remove local dev dependencies)
cat > requirements.txt << EOF
azure-identity>=1.15.0
azure-mgmt-resource>=23.0.0
azure-mgmt-compute>=30.0.0
azure-mgmt-storage>=21.0.0
azure-mgmt-network>=25.0.0
azure-mgmt-keyvault>=10.3.0
azure-mgmt-automation>=1.0.0,<2.0.0
azure-storage-blob>=12.19.0
azure-keyvault-secrets>=4.7.0
requests>=2.31.0
python-dateutil>=2.8.2
EOF

# Create deployment zip
zip -r azure-automation-runbooks.zip runbooks/ shared/ requirements.txt
```

#### Step 2: Deploy via Azure Portal

1. **Navigate to your Azure Automation Account**
2. **Import Runbooks**:
   - Go to "Runbooks" → "Import a runbook"
   - Upload each Python file from `runbooks/` directory
   - Set runbook type to "Python 3"
3. **Install Python Packages**:
   - Go to "Python packages" → "Add a Python package"
   - Upload packages from `requirements.txt` or install from PyPI

#### Step 3: Deploy via Azure CLI

```bash
# Set variables
RESOURCE_GROUP="your-automation-rg"
AUTOMATION_ACCOUNT="your-automation-account"
SUBSCRIPTION_ID="your-subscription-id"

# Import runbooks
az automation runbook import \
  --automation-account-name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --name "UpdateNSGRules" \
  --type "Python3" \
  --source-file "runbooks/networking/update-nsg.py"

# Install Python packages
az automation python3-package install \
  --automation-account-name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --name "azure-identity" \
  --package-version "1.15.0"

# Add more packages as needed...
```

#### Step 4: Configure Automation Variables

```bash
# Set automation variables
az automation variable set \
  --automation-account-name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --name "AZURE_SUBSCRIPTION_ID" \
  --value $SUBSCRIPTION_ID

az automation variable set \
  --automation-account-name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --name "USE_MANAGED_IDENTITY" \
  --value "true"

az automation variable set \
  --automation-account-name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --name "AZURE_NSG_RESOURCE_GROUP" \
  --value "your-nsg-rg"

az automation variable set \
  --automation-account-name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --name "AZURE_NSG_NAME" \
  --value "your-nsg-name"

az automation variable set \
  --automation-account-name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --name "EDGE_GATEWAY_IP" \
  --value "203.0.113.10"
```

#### Step 5: Configure Managed Identity Permissions

```bash
# Get the managed identity object ID
MANAGED_IDENTITY_ID=$(az automation account show \
  --name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query "identity.principalId" -o tsv)

# Assign Network Contributor role for NSG management
az role assignment create \
  --assignee $MANAGED_IDENTITY_ID \
  --role "Network Contributor" \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/your-nsg-resource-group"

# Assign Reader role for resource discovery
az role assignment create \
  --assignee $MANAGED_IDENTITY_ID \
  --role "Reader" \
  --scope "/subscriptions/$SUBSCRIPTION_ID"
```

### Option 2: Azure Functions Deployment

#### Step 1: Create Function App

```bash
# Create resource group
az group create --name "rg-automation-functions" --location "eastus2"

# Create storage account
az storage account create \
  --name "stautomationfunc$(date +%s)" \
  --resource-group "rg-automation-functions" \
  --location "eastus2" \
  --sku "Standard_LRS"

# Create function app
az functionapp create \
  --name "func-automation-$(date +%s)" \
  --resource-group "rg-automation-functions" \
  --storage-account "stautomationfunc$(date +%s)" \
  --runtime "python" \
  --runtime-version "3.9" \
  --functions-version "4"
```

#### Step 2: Prepare Function Code

Create `function_app/` structure:

```
function_app/
├── host.json
├── requirements.txt
├── shared/                 # Copy from main project
└── UpdateNSGRules/
    ├── function.json
    └── __init__.py
```

**host.json**:
```json
{
  "version": "2.0",
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[3.*, 4.0.0)"
  }
}
```

**UpdateNSGRules/function.json**:
```json
{
  "scriptFile": "__init__.py",
  "bindings": [
    {
      "authLevel": "function",
      "type": "httpTrigger",
      "direction": "in",
      "name": "req",
      "methods": ["post"]
    },
    {
      "type": "http",
      "direction": "out",
      "name": "$return"
    }
  ]
}
```

#### Step 3: Deploy Function

```bash
# Deploy function app
cd function_app
func azure functionapp publish func-automation-$(date +%s)
```

### Option 3: Azure Container Instances Deployment

#### Step 1: Create Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY shared/ ./shared/
COPY runbooks/ ./runbooks/

# Set environment variables
ENV PYTHONPATH=/app
ENV USE_MANAGED_IDENTITY=true

# Run the application
CMD ["python", "runbooks/networking/update-nsg.py"]
```

#### Step 2: Build and Deploy Container

```bash
# Build container
docker build -t azure-automation-solution .

# Tag for Azure Container Registry
docker tag azure-automation-solution your-acr.azurecr.io/azure-automation-solution:latest

# Push to ACR
az acr login --name your-acr
docker push your-acr.azurecr.io/azure-automation-solution:latest

# Deploy to ACI
az container create \
  --resource-group "rg-automation" \
  --name "aci-automation-nsg" \
  --image "your-acr.azurecr.io/azure-automation-solution:latest" \
  --assign-identity \
  --environment-variables \
    AZURE_SUBSCRIPTION_ID="your-subscription-id" \
    USE_MANAGED_IDENTITY="true" \
    AZURE_NSG_RESOURCE_GROUP="your-nsg-rg" \
    AZURE_NSG_NAME="your-nsg-name" \
    EDGE_GATEWAY_IP="203.0.113.10"
```

### Option 4: GitHub Actions CI/CD Pipeline

Create `.github/workflows/deploy-automation.yml`:

```yaml
name: Deploy Azure Automation Solution

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

env:
  AZURE_AUTOMATION_ACCOUNT: ${{ secrets.AUTOMATION_ACCOUNT }}
  AZURE_RESOURCE_GROUP: ${{ secrets.RESOURCE_GROUP }}
  AZURE_SUBSCRIPTION_ID: ${{ secrets.SUBSCRIPTION_ID }}

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        python -m pytest tests/ -v
    
    - name: Azure Login
      uses: azure/login@v1
      with:
        creds: ${{ secrets.AZURE_CREDENTIALS }}
    
    - name: Deploy runbooks
      run: |
        # Import runbooks to Azure Automation
        az automation runbook import \
          --automation-account-name $AZURE_AUTOMATION_ACCOUNT \
          --resource-group $AZURE_RESOURCE_GROUP \
          --name "UpdateNSGRules" \
          --type "Python3" \
          --source-file "runbooks/networking/update-nsg.py"
    
    - name: Update automation variables
      run: |
        # Update variables if needed
        az automation variable set \
          --automation-account-name $AZURE_AUTOMATION_ACCOUNT \
          --resource-group $AZURE_RESOURCE_GROUP \
          --name "LAST_DEPLOYMENT" \
          --value "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

### Deployment Validation

After deployment, validate your setup:

#### Test Runbook Execution
```bash
# Test via Azure CLI
az automation runbook start \
  --automation-account-name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --name "UpdateNSGRules"

# Check job status
az automation job list \
  --automation-account-name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query "[0].{Name:runbookName,Status:status,StartTime:startTime}"
```

#### Monitor Logs
```bash
# Get job output
JOB_ID=$(az automation job list \
  --automation-account-name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query "[0].jobId" -o tsv)

az automation job output \
  --automation-account-name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --job-id $JOB_ID
```

### Deployment Rollback

If you need to rollback a deployment:

```bash
# Stop running jobs
az automation job stop \
  --automation-account-name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --job-id $JOB_ID

# Revert runbook to previous version
az automation runbook import \
  --automation-account-name $AUTOMATION_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --name "UpdateNSGRules" \
  --type "Python3" \
  --source-file "backup/update-nsg-v1.py"
```

### Deployment Best Practices

1. **Environment Separation**: Use different Automation Accounts for dev/staging/prod
2. **Version Control**: Tag releases and maintain backup copies of runbooks
3. **Testing**: Always test in development environment first
4. **Monitoring**: Set up alerts for failed runbook executions
5. **Security**: Use least privilege access and secure variable storage
6. **Documentation**: Keep deployment procedures documented and up-to-date

## 🚨 Security Best Practices

- **Never commit secrets**: Use environment variables or Azure Key Vault
- **Least privilege**: Grant minimum required permissions to managed identity
- **Network security**: Use NSG rules to restrict access to specific IPs
- **Logging**: Enable comprehensive logging for audit trails
- **Testing**: Test runbooks in development environment first

## 🔍 Troubleshooting

### Authentication Issues
```
ManagedIdentityCredential authentication unavailable
```
**Solution**: Set `USE_MANAGED_IDENTITY=false` for local development

### Missing Dependencies
```
ModuleNotFoundError: No module named 'azure.mgmt.network'
```
**Solution**: Install requirements: `pip install -r requirements.txt`

### Configuration Not Found
```
Azure subscription ID not configured
```
**Solution**: Verify your `.env` file contains `AZURE_SUBSCRIPTION_ID`

## 📈 Monitoring and Logging

The solution provides comprehensive logging:

- **Operation Tracking**: Each Azure operation is logged with status and details
- **Performance Metrics**: Timing information for operations
- **Error Details**: Detailed error messages and stack traces
- **Azure Integration**: Compatible with Azure Monitor and Log Analytics

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-runbook`
3. Make your changes
4. Add tests for new functionality
5. Commit your changes: `git commit -am 'Add new runbook'`
6. Push to the branch: `git push origin feature/new-runbook`
7. Create a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For issues and questions:
- Create an issue in this repository
- Check the troubleshooting section above
- Review Azure Automation documentation

---

**Built with ❤️ for Azure Automation**