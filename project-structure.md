# Azure Automation Solution - Recommended Structure

```
azure-automation-solution/
├── runbooks/                          # All runbooks organized by category
│   ├── compute/                       # VM management runbooks
│   │   ├── vm-start-stop.py
│   │   ├── vm-backup.py
│   │   └── vm-monitoring.py
│   ├── networking/                    # Network-related runbooks
│   │   ├── update-nsg.py
│   │   ├── firewall-rules.py
│   │   └── dns-management.py
│   ├── storage/                       # Storage management runbooks
│   │   ├── blob-cleanup.py
│   │   ├── backup-automation.py
│   │   └── storage-monitoring.py
│   └── security/                      # Security-related runbooks
│       ├── key-vault-rotation.py
│       ├── certificate-renewal.py
│       └── compliance-check.py
├── shared/                            # Shared modules and utilities
│   ├── __init__.py
│   ├── azure_auth.py                 # Authentication utilities
│   ├── logging_utils.py              # Logging helpers
│   ├── config_manager.py             # Configuration management
│   └── common_operations.py          # Common Azure operations
├── config/                            # Configuration files
│   ├── dev.json
│   ├── staging.json
│   └── prod.json
├── tests/                             # Unit tests for runbooks
│   ├── test_compute/
│   ├── test_networking/
│   └── test_shared/
├── docs/                              # Documentation
│   ├── runbook-catalog.md
│   └── deployment-guide.md
├── .vscode/                           # VS Code settings
│   ├── settings.json
│   ├── launch.json
│   └── tasks.json
├── requirements.txt                   # Core dependencies
├── requirements-dev.txt               # Development dependencies
├── setup.py                          # Package setup
├── .env.template                     # Environment template
├── .gitignore
└── README.md
```