# ⚠️ DEPRECATED: Manual Kubernetes/OpenShift Deployment

**This directory contains outdated manual deployment manifests that have been replaced.**

## 🚨 Notice

This deployment approach has been **deprecated** and replaced with the **Tekton Pipeline** approach for better CI/CD integration and multi-user support.

## 🚀 Please Use Instead

For production deployment, please use the **Tekton Pipeline** approach:

```bash
# Navigate to Tekton pipeline directory
cd ../tekton

# Deploy for a specific user
chmod +x deploy-user-namespace.sh
./deploy-user-namespace.sh <username>

# Example: Deploy for user "alice"
./deploy-user-namespace.sh alice
```

## 📖 Documentation

See the comprehensive documentation:
- [Tekton Pipeline README](../tekton/README.md)
- [Deployment Overview](../README.md)

## 🏗️ Why We Moved to Tekton

The Tekton pipeline approach provides:
- **Multi-User Support**: Complete isolation per user
- **CI/CD Integration**: Automated build and deployment
- **GitHub Webhooks**: Automatic deployment on code changes
- **Better Security**: Proper RBAC and security contexts
- **Scalability**: Support for unlimited users on single cluster
- **Monitoring**: Built-in pipeline monitoring and logging

## 🗑️ Legacy Files

The files in this directory are kept for reference only and should not be used for new deployments. They include:
- `namespace.yaml` - Single namespace approach (now user-specific)
- `*-deployment.yaml` - Manual deployments (now automated)
- `*-service.yaml` - Service definitions (now templated)
- `route.yaml` - Single route (now per-user routes)

Use the Tekton pipeline approach for all new deployments. 