# CI Analysis Agent Deployment

This directory contains all the deployment scripts and Kubernetes/OpenShift manifests for the CI Analysis Agent.

## 📁 Directory Structure

```
deploy/
├── k8s/                            # Kubernetes/OpenShift manifests
│   ├── namespace.yaml              # Namespace definition
│   ├── configmap.yaml              # Environment variables
│   ├── ollama-deployment.yaml      # Ollama deployment + PVC
│   ├── ollama-service.yaml         # Ollama service
│   ├── ollama-model-job.yaml       # Model pulling job
│   ├── ci-analysis-deployment.yaml # Main app deployment
│   ├── ci-analysis-service.yaml    # Main app service
│   ├── ingress.yaml                # Kubernetes ingress (optional)
│   └── route.yaml                  # OpenShift route
├── deploy.sh                       # Kubernetes deployment script
├── deploy-openshift.sh             # OpenShift deployment script
├── cleanup.sh                      # Kubernetes cleanup script
├── cleanup-openshift.sh            # OpenShift cleanup script
└── README.md                       # This file
```

## 🚀 Quick Start

### For Kubernetes

```bash
# Deploy to Kubernetes
chmod +x deploy/deploy.sh
./deploy/deploy.sh

# Cleanup
chmod +x deploy/cleanup.sh
./deploy/cleanup.sh
```

### For OpenShift 4.19+

```bash
# Deploy to OpenShift
chmod +x deploy/deploy-openshift.sh
./deploy/deploy-openshift.sh

# Cleanup
chmod +x deploy/cleanup-openshift.sh
./deploy/cleanup-openshift.sh
```

## 📋 Prerequisites

- **Node Architecture**: linux/amd64 nodes (required for Ollama)
- Docker/Podman for building images
- kubectl (for Kubernetes) or oc (for OpenShift)
- At least 10GB available storage for model data

## 🔧 Key Features

- **Node Selection**: Only schedules on linux/amd64 nodes
- **Security**: Non-root containers (OpenShift compatible)
- **Persistence**: Model data persisted across restarts
- **Health Checks**: Readiness and liveness probes
- **External Access**: Ingress (K8s) or Route (OpenShift)

## 📖 Full Documentation

For complete documentation including troubleshooting, production considerations, and advanced configuration, see:

- [KUBERNETES.md](../KUBERNETES.md) - Complete deployment guide

## 🆘 Support

If you encounter issues:
1. Check pod logs: `kubectl logs -f deployment/ci-analysis-agent -n ci-analysis`
2. Verify node requirements: `kubectl get nodes --show-labels | grep -E "(arch|os)"`
3. Check the main documentation: [KUBERNETES.md](../KUBERNETES.md) 