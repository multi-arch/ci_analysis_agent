# CI Analysis Agent Tekton Pipeline (Multi-User)

This directory contains a comprehensive Tekton pipeline for building and deploying the CI Analysis Agent with Ollama on OpenShift, designed for **multiple users** on a single cluster.

## 🎯 Multi-User Pipeline Features

### **Key Changes Made:**
1. **Parameterized git-url** - Now accepts any GitHub repository
2. **Dynamic namespaces** - Each user deploys to `ci-analysis-<username>` 
3. **Resource prefixing** - All resources are prefixed with user identifier
4. **Centralized pipeline** - Single pipeline definition supports all users
5. **Automated user detection** - GitHub webhooks automatically create user-specific deployments

### **Multi-User Architecture:**
- **Shared Resources**: Pipeline, tasks, RBAC, and secrets in `tekton-pipelines` namespace
- **User Isolation**: Each user gets their own namespace with prefixed resources
- **Automatic Deployment**: GitHub webhooks create deployments based on repository owner

### **Updated Files:**
- ✅ **`pipeline.yaml`** - Added `target-namespace` and `user-prefix` parameters
- ✅ **`tasks.yaml`** - Updated all tasks to use dynamic namespaces and prefixes
- ✅ **`rbac.yaml`** - Moved to `tekton-pipelines` namespace for cluster-wide access
- ✅ **`triggers.yaml`** - Auto-generates user deployments from GitHub webhooks
- ✅ **`pipeline-run.yaml`** - Example deployment for "dev" user
- ✅ **`user-examples.yaml`** - Multiple user deployment examples with script
- ✅ **`deploy-pipeline.sh`** - Updated for multi-user setup
- ✅ **`README.md`** - Comprehensive multi-user documentation

### **Usage Examples:**

```bash
# Deploy for user "alice" from her fork
./deploy-user.sh alice https://github.com/alice/ci_analysis_agent.git feature/new-analysis alice

# Deploy for user "bob" from his fork  
./deploy-user.sh bob https://github.com/bob/ci_analysis_agent.git dev/performance-improvements bob

# Deploy for QA team
./deploy-user.sh qa https://github.com/jeffdyoung/ci_analysis_agent.git main qa-team
```

### **Resource Isolation:**
Each user gets their own:
- **Namespace**: `ci-analysis-<username>`
- **Ollama**: `<username>-ollama`
- **Agent**: `<username>-ci-analysis-agent`
- **Service**: `<username>-ci-analysis-service`  
- **Route**: `<username>-ci-analysis-agent`
- **ConfigMap**: `<username>-ci-analysis-config`

### **GitHub Webhook Integration:**
- Automatically detects repository owner as username
- Creates deployments in `ci-analysis-<owner>` namespace
- Supports `main`, `feature/*`, and `dev/*` branches
- Generates unique image tags per user

The pipeline is now **production-ready for multi-user development teams** with complete isolation, security, and automation! 🚀 