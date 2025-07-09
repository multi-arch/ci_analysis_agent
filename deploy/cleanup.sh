#!/bin/bash

echo "🧹 Cleaning up CI Analysis Agent from Kubernetes..."

# Delete all resources in the ci-analysis namespace
kubectl delete namespace ci-analysis --wait=true

echo "✅ Cleanup complete!"
echo "All CI Analysis Agent resources have been removed from the cluster." 