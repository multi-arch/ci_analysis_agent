#!/bin/bash
set -e

# OpenShift cleanup script for CI Analysis Agent

echo "🧹 Cleaning up CI Analysis Agent from OpenShift..."

# Delete the entire namespace (this removes all resources)
echo "🗑️  Deleting namespace and all resources..."
oc delete namespace ci-analysis --ignore-not-found=true

# Wait for namespace to be fully deleted
echo "⏳ Waiting for namespace to be fully deleted..."
oc wait --for=delete namespace/ci-analysis --timeout=120s || true

# Clean up local Docker image
echo "🐳 Cleaning up local Docker image..."
docker rmi ci-analysis-agent:latest || true

echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources have been removed from OpenShift cluster." 