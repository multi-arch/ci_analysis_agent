#!/bin/bash

set -e

echo "🚀 Deploying CI Analysis Agent to Kubernetes..."

# Build and tag the Docker image
echo "📦 Building Docker image..."
docker build -t ci-analysis-agent:latest ..

# If using a registry, push the image
# echo "📤 Pushing image to registry..."
# docker tag ci-analysis-agent:latest your-registry/ci-analysis-agent:latest
# docker push your-registry/ci-analysis-agent:latest

echo "🏗️  Creating Kubernetes resources..."

# Apply all manifests in order
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/ollama-deployment.yaml
kubectl apply -f k8s/ollama-service.yaml

echo "⏳ Waiting for Ollama to be ready..."
kubectl wait --for=condition=ready pod -l app=ollama -n ci-analysis --timeout=300s

echo "📥 Pulling qwen3:4b model..."
kubectl apply -f k8s/ollama-model-job.yaml

echo "⏳ Waiting for model pull to complete..."
kubectl wait --for=condition=complete job/ollama-pull-model -n ci-analysis --timeout=600s

echo "🤖 Deploying CI Analysis Agent..."
kubectl apply -f k8s/ci-analysis-deployment.yaml
kubectl apply -f k8s/ci-analysis-service.yaml

# Optional: Apply ingress
# kubectl apply -f k8s/ingress.yaml

echo "⏳ Waiting for CI Analysis Agent to be ready..."
kubectl wait --for=condition=ready pod -l app=ci-analysis-agent -n ci-analysis --timeout=300s

echo "✅ Deployment complete!"
echo ""
echo "📋 To access your CI Analysis Agent:"
echo "   Local access: kubectl port-forward svc/ci-analysis-service 8000:8000 -n ci-analysis"
echo "   Then open: http://localhost:8000/dev-ui/?app=ci_analysis_agent"
echo ""
echo "📊 To check status:"
echo "   kubectl get pods -n ci-analysis"
echo "   kubectl logs -f deployment/ci-analysis-agent -n ci-analysis" 