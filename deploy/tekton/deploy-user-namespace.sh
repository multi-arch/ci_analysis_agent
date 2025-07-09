#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if username is provided
if [ -z "$1" ]; then
    echo -e "${RED}❌ Usage: $0 <username>${NC}"
    echo -e "${YELLOW}Example: $0 alice${NC}"
    exit 1
fi

USERNAME=$1
NAMESPACE="ci-analysis-$USERNAME"

echo -e "${GREEN}🚀 Deploying CI Analysis Agent Pipeline for user: $USERNAME${NC}"
echo -e "${GREEN}📦 Target namespace: $NAMESPACE${NC}"

# Check if user is logged in to OpenShift
if ! oc whoami &> /dev/null; then
    echo -e "${RED}❌ Not logged in to OpenShift. Please run 'oc login' first.${NC}"
    exit 1
fi

# Check if Tekton is installed
if ! oc get crd pipelines.tekton.dev &> /dev/null; then
    echo -e "${RED}❌ Tekton Pipelines not found. Please install Tekton first.${NC}"
    echo -e "${YELLOW}You can install it with: oc apply -f https://storage.googleapis.com/tekton-releases/pipeline/latest/release.yaml${NC}"
    exit 1
fi

# Check if Tekton Triggers is installed
if ! oc get crd eventlisteners.triggers.tekton.dev &> /dev/null; then
    echo -e "${YELLOW}⚠️  Tekton Triggers not found. Installing...${NC}"
    oc apply -f https://storage.googleapis.com/tekton-releases/triggers/latest/release.yaml
    oc apply -f https://storage.googleapis.com/tekton-releases/triggers/latest/interceptors.yaml
fi

# Create user namespace if it doesn't exist
echo -e "${GREEN}📦 Creating namespace: $NAMESPACE${NC}"
if ! oc get namespace $NAMESPACE &> /dev/null; then
    oc create namespace $NAMESPACE
else
    echo -e "${YELLOW}Namespace '$NAMESPACE' already exists${NC}"
fi

# Function to deploy a file with namespace replacement
deploy_with_namespace() {
    local file=$1
    local description=$2
    
    echo -e "${GREEN}$description${NC}"
    sed "s/NAMESPACE_PLACEHOLDER/$NAMESPACE/g" $file | oc apply -f -
}

# Deploy all pipeline resources
deploy_with_namespace "rbac.yaml" "🔐 Deploying RBAC..."
deploy_with_namespace "tasks.yaml" "📝 Deploying Tasks..."
deploy_with_namespace "pipeline.yaml" "🔄 Deploying Pipeline..."
deploy_with_namespace "triggers.yaml" "⚡ Deploying Triggers..."
deploy_with_namespace "pipeline-run.yaml" "📄 Deploying Pipeline Run template..."

# Check if docker registry secret exists
if ! oc get secret docker-registry-secret -n $NAMESPACE &> /dev/null; then
    echo -e "${YELLOW}⚠️  Docker registry secret not found in namespace $NAMESPACE${NC}"
    echo -e "${YELLOW}Please create it with:${NC}"
    echo -e "${YELLOW}kubectl create secret docker-registry docker-registry-secret \\${NC}"
    echo -e "${YELLOW}  --docker-server=quay.io \\${NC}"
    echo -e "${YELLOW}  --docker-username=<your-username> \\${NC}"
    echo -e "${YELLOW}  --docker-password=<your-password> \\${NC}"
    echo -e "${YELLOW}  --docker-email=<your-email> \\${NC}"
    echo -e "${YELLOW}  -n $NAMESPACE${NC}"
fi

echo -e "${GREEN}✅ Pipeline deployment completed for user: $USERNAME${NC}"
echo -e "${GREEN}🎯 Next steps:${NC}"
echo -e "1. Create docker registry secret (if not already done)"
echo -e "2. Update GitHub webhook secret in namespace $NAMESPACE"
echo -e "3. Run the pipeline with examples from user-examples.yaml"
echo -e "4. Monitor the pipeline with: tkn pipelinerun logs --last -f -n $NAMESPACE"

# Get webhook URL if triggers are deployed
if oc get route ci-analysis-agent-webhook -n $NAMESPACE &> /dev/null; then
    WEBHOOK_URL=$(oc get route ci-analysis-agent-webhook -n $NAMESPACE -o jsonpath='{.spec.host}')
    echo -e "${GREEN}🔗 Webhook URL: https://${WEBHOOK_URL}${NC}"
    echo -e "Configure this URL in your GitHub repository webhooks"
fi

echo -e "${GREEN}📊 Resources deployed to namespace: $NAMESPACE${NC}"
echo -e "${GREEN}🔍 View deployment: oc get all -n $NAMESPACE${NC}" 