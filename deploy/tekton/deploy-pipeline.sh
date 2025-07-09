#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying CI Analysis Agent Tekton Pipeline${NC}"

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

# Function to check if a resource exists
resource_exists() {
    oc get $1 $2 -n $3 &> /dev/null
}

# Create tekton-pipelines namespace if it doesn't exist
echo -e "${GREEN}📦 Creating tekton-pipelines namespace...${NC}"
if ! resource_exists namespace tekton-pipelines ""; then
    oc create namespace tekton-pipelines
else
    echo -e "${YELLOW}Namespace 'tekton-pipelines' already exists${NC}"
fi

# Apply RBAC
echo -e "${GREEN}🔐 Applying RBAC...${NC}"
oc apply -f rbac.yaml

# Apply Tasks
echo -e "${GREEN}📝 Applying Tasks...${NC}"
oc apply -f tasks.yaml

# Apply Pipeline
echo -e "${GREEN}🔄 Applying Pipeline...${NC}"
oc apply -f pipeline.yaml

# Apply Triggers (optional)
echo -e "${GREEN}⚡ Applying Triggers...${NC}"
oc apply -f triggers.yaml

# Check if docker registry secret exists
if ! resource_exists secret docker-registry-secret tekton-pipelines; then
    echo -e "${YELLOW}⚠️  Docker registry secret not found.${NC}"
    echo -e "${YELLOW}Please create it with:${NC}"
    echo -e "${YELLOW}kubectl create secret docker-registry docker-registry-secret \\${NC}"
    echo -e "${YELLOW}  --docker-server=quay.io \\${NC}"
    echo -e "${YELLOW}  --docker-username=<your-username> \\${NC}"
    echo -e "${YELLOW}  --docker-password=<your-password> \\${NC}"
    echo -e "${YELLOW}  --docker-email=<your-email> \\${NC}"
    echo -e "${YELLOW}  -n tekton-pipelines${NC}"
fi

# Check if GitHub webhook secret exists
if ! resource_exists secret github-webhook-secret tekton-pipelines; then
    echo -e "${YELLOW}⚠️  GitHub webhook secret not found.${NC}"
    echo -e "${YELLOW}Please update the secret in triggers.yaml with your actual webhook secret.${NC}"
fi

echo -e "${GREEN}✅ Pipeline deployment completed!${NC}"
echo -e "${GREEN}🎯 Next steps:${NC}"
echo -e "1. Create docker registry secret (if not already done)"
echo -e "2. Update GitHub webhook secret in triggers.yaml"
echo -e "3. Run the pipeline with: oc apply -f pipeline-run.yaml"
echo -e "4. Monitor the pipeline with: tkn pipelinerun logs --last -f -n tekton-pipelines"
echo -e "5. Each user will deploy to their own namespace: ci-analysis-<username>"

# Get webhook URL if triggers are deployed
if resource_exists route ci-analysis-agent-webhook tekton-pipelines; then
    WEBHOOK_URL=$(oc get route ci-analysis-agent-webhook -n tekton-pipelines -o jsonpath='{.spec.host}')
    echo -e "${GREEN}🔗 Webhook URL: https://${WEBHOOK_URL}${NC}"
    echo -e "Configure this URL in your GitHub repository webhooks"
fi 