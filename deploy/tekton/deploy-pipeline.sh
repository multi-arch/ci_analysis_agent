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

# Note: Resources will be deployed to user namespaces (ci-analysis-<username>)
# No centralized namespace required
echo -e "${GREEN}📦 Pipeline resources will be deployed to user namespaces${NC}"

# Prepare templates for user deployment
echo -e "${GREEN}🔧 Preparing pipeline templates...${NC}"
echo -e "${YELLOW}Templates are ready for deployment to user namespaces${NC}"
echo -e "${YELLOW}Use the deployment scripts or examples in user-examples.yaml${NC}"

# User secrets need to be created in each user namespace
echo -e "${YELLOW}📝 Secret creation requirements:${NC}"
echo -e "${YELLOW}Each user needs to create secrets in their namespace:${NC}"
echo -e "${YELLOW}kubectl create secret docker-registry docker-registry-secret \\${NC}"
echo -e "${YELLOW}  --docker-server=quay.io \\${NC}"
echo -e "${YELLOW}  --docker-username=<your-username> \\${NC}"
echo -e "${YELLOW}  --docker-password=<your-password> \\${NC}"
echo -e "${YELLOW}  --docker-email=<your-email> \\${NC}"
echo -e "${YELLOW}  -n ci-analysis-<username>${NC}"
echo -e "${YELLOW}${NC}"
echo -e "${YELLOW}Update GitHub webhook secret in triggers.yaml${NC}"

echo -e "${GREEN}✅ Pipeline templates prepared!${NC}"
echo -e "${GREEN}🎯 Next steps for each user:${NC}"
echo -e "1. Create user namespace: ci-analysis-<username>"
echo -e "2. Deploy templates to user namespace using sed to replace NAMESPACE_PLACEHOLDER"
echo -e "3. Create docker registry secret in user namespace"
echo -e "4. Update GitHub webhook secret in triggers.yaml"
echo -e "5. Run the pipeline with examples from user-examples.yaml"
echo -e "6. Monitor the pipeline with: tkn pipelinerun logs --last -f -n ci-analysis-<username>"

echo -e "${GREEN}📖 For detailed examples, see user-examples.yaml${NC}"
echo -e "${GREEN}🔗 Each user gets their own webhook URL in their namespace${NC}" 