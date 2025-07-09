#!/bin/bash
set -e

# OpenShift deployment script for CI Analysis Agent
# This script deploys the CI Analysis Agent with Ollama on OpenShift 4.19+

echo "🚀 Deploying CI Analysis Agent on OpenShift 4.19+"
echo "This will only schedule on linux/amd64 nodes"

# Build the Docker image
echo "📦 Building Docker image..."
docker build -t ci-analysis-agent:latest ..

# Create namespace
echo "🏗️  Creating namespace..."
oc apply -f k8s/namespace.yaml

# Apply ConfigMap
echo "⚙️  Applying ConfigMap..."
oc apply -f k8s/configmap.yaml

# Deploy Ollama
echo "🤖 Deploying Ollama..."
oc apply -f k8s/ollama-deployment.yaml
oc apply -f k8s/ollama-service.yaml

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to be ready..."
oc wait --for=condition=ready pod -l app=ollama -n ci-analysis --timeout=300s

# Pull the model
echo "📥 Pulling Ollama model..."
oc apply -f k8s/ollama-model-job.yaml
oc wait --for=condition=complete job/ollama-model-pull -n ci-analysis --timeout=600s

# Deploy CI Analysis Agent
echo "🧠 Deploying CI Analysis Agent..."
oc apply -f k8s/ci-analysis-deployment.yaml
oc apply -f k8s/ci-analysis-service.yaml

# Create OpenShift Route
echo "🌐 Creating OpenShift Route..."
oc apply -f k8s/route.yaml

# Wait for deployment to be ready
echo "⏳ Waiting for CI Analysis Agent to be ready..."
oc wait --for=condition=ready pod -l app=ci-analysis-agent -n ci-analysis --timeout=300s

# Get route URL
echo "✅ Deployment completed successfully!"
echo ""
echo "📋 Deployment Summary:"
echo "- Namespace: ci-analysis"
echo "- Pods are scheduled only on linux/amd64 nodes"
echo "- Running with OpenShift security contexts"
echo "- Using non-root user (UID: 1001)"
echo ""

# Check if route exists and get URL
if oc get route ci-analysis-agent-route -n ci-analysis >/dev/null 2>&1; then
    ROUTE_URL=$(oc get route ci-analysis-agent-route -n ci-analysis -o jsonpath='{.spec.host}')
    echo "🔗 Access the application at: https://${ROUTE_URL}"
else
    echo "⚠️  Route not found. You can create one manually or access via port-forward:"
    echo "   oc port-forward svc/ci-analysis-service 8000:8000 -n ci-analysis"
fi

echo ""
echo "🔍 To check the status:"
echo "   oc get pods -n ci-analysis"
echo "   oc logs -f deployment/ci-analysis-agent -n ci-analysis"
echo ""
echo "🧹 To clean up:"
echo "   oc delete namespace ci-analysis" 