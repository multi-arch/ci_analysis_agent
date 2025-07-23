#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
OVERRIDE_REGISTRY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --override-registry)
            OVERRIDE_REGISTRY=true
            shift
            ;;
        --help)
            echo -e "${BLUE}Usage: $0 [OPTIONS]${NC}"
            echo -e "${BLUE}Options:${NC}"
            echo -e "  --override-registry    Prompt for new registry credentials and update secret"
            echo -e "  --help                 Show this help message"
            exit 0
            ;;
        -*)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            exit 1
            ;;
        *)
            echo -e "${RED}❌ Unexpected argument: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}🚀 CI Analysis Agent Pipeline Runner${NC}"
echo -e "${BLUE}This script will run the Tekton pipeline with smart defaults${NC}"
echo

# Function to get git origin URL (convert SSH to HTTPS)
get_git_origin() {
    if git remote get-url origin &> /dev/null; then
        local url=$(git remote get-url origin)
        # Convert SSH URL to HTTPS format
        if [[ $url == git@github.com:* ]]; then
            # Convert git@github.com:user/repo.git to https://github.com/user/repo.git
            echo "$url" | sed 's/git@github.com:/https:\/\/github.com\//'
        else
            echo "$url"
        fi
    else
        echo "https://github.com/multi-arch/ci_analysis_agent.git"
    fi
}

# Function to get current branch
get_current_branch() {
    if git branch --show-current &> /dev/null; then
        git branch --show-current
    else
        echo "main"
    fi
}

# Function to get username from git or system
get_default_username() {
    if git config user.name &> /dev/null; then
        # Convert git username to lowercase and replace spaces with hyphens
        git config user.name | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | head -c 10
    elif [ -n "$USER" ]; then
        echo "$USER"
    else
        echo "dev"
    fi
}



# Function to update registry secret with new credentials
update_registry_secret() {
    echo -e "${GREEN}🔐 Registry Configuration${NC}"
    echo -e "${YELLOW}Please provide your container registry credentials:${NC}"
    echo
    
    # Get docker server with validation
    while true; do
        echo -n "Docker Server (default: quay.io): "
        read -r DOCKER_SERVER
        DOCKER_SERVER=${DOCKER_SERVER:-quay.io}
        
        # Basic URL validation
        if [[ $DOCKER_SERVER =~ ^[a-zA-Z0-9.-]+$ ]]; then
            break
        else
            echo -e "${RED}❌ Invalid server format. Please use format like 'quay.io' or 'registry.redhat.io'${NC}"
        fi
    done
    
    # Get username with validation
    while true; do
        echo -n "Docker Username: "
        read -r DOCKER_USERNAME
        
        if [ -n "$DOCKER_USERNAME" ] && [[ $DOCKER_USERNAME =~ ^[a-zA-Z0-9._-]+$ ]]; then
            break
        else
            echo -e "${RED}❌ Invalid username. Use alphanumeric characters, dots, underscores, or hyphens only${NC}"
        fi
    done
    
    # Get password securely
    while true; do
        echo -n "Docker Password: "
        read -rs DOCKER_PASSWORD
        echo
        
        if [ -n "$DOCKER_PASSWORD" ] && [ ${#DOCKER_PASSWORD} -ge 8 ]; then
            break
        else
            echo -e "${RED}❌ Password must be at least 8 characters long${NC}"
        fi
    done
    
    # Get email with validation
    while true; do
        echo -n "Docker Email: "
        read -r DOCKER_EMAIL
        
        if [ -n "$DOCKER_EMAIL" ] && [[ $DOCKER_EMAIL =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
            break
        else
            echo -e "${RED}❌ Please enter a valid email address${NC}"
        fi
    done
    
    echo -e "${GREEN}📝 Updating docker registry secret...${NC}"
    
    # Delete existing secret
    if oc get secret docker-registry-secret -n $TARGET_NAMESPACE &> /dev/null; then
        oc delete secret docker-registry-secret -n $TARGET_NAMESPACE
    fi
    
    # Create new secret
    if kubectl create secret docker-registry docker-registry-secret \
        --docker-server="$DOCKER_SERVER" \
        --docker-username="$DOCKER_USERNAME" \
        --docker-password="$DOCKER_PASSWORD" \
        --docker-email="$DOCKER_EMAIL" \
        -n $TARGET_NAMESPACE &> /dev/null; then
        
        echo -e "${GREEN}✅ Registry secret updated successfully${NC}"
        
        echo -e "${GREEN}✅ Registry secret updated. You can now push to $DOCKER_SERVER/$DOCKER_USERNAME${NC}"
        
        # Clear sensitive variables from memory
        unset DOCKER_PASSWORD DOCKER_USERNAME DOCKER_EMAIL
    else
        echo -e "${RED}❌ Failed to update registry secret${NC}"
        unset DOCKER_PASSWORD DOCKER_USERNAME DOCKER_EMAIL
        exit 1
    fi
}

# Check if user is logged in to OpenShift
if ! oc whoami &> /dev/null; then
    echo -e "${RED}❌ Not logged in to OpenShift. Please run 'oc login' first.${NC}"
    exit 1
fi

# Check if tkn CLI is available
if ! command -v tkn &> /dev/null; then
    echo -e "${RED}❌ Tekton CLI (tkn) is not installed.${NC}"
    echo -e "${YELLOW}Install it with:${NC}"
    echo -e "  curl -LO https://github.com/tektoncd/cli/releases/latest/download/tkn_Linux_x86_64.tar.gz"
    echo -e "  tar xvzf tkn_Linux_x86_64.tar.gz -C /usr/local/bin/ tkn"
    exit 1
fi



echo -e "${GREEN}✅ Logged in to OpenShift as: $(oc whoami)${NC}"
echo -e "${GREEN}✅ Tekton CLI (tkn) is available${NC}"
echo

# Collect pipeline parameters with smart defaults
DEFAULT_GIT_URL=$(get_git_origin)
DEFAULT_GIT_REVISION=$(get_current_branch)
DEFAULT_USERNAME=$(get_default_username)
DEFAULT_NAMESPACE="ci-analysis-$DEFAULT_USERNAME"

echo -e "${BLUE}📋 Pipeline Configuration${NC}"
echo -e "${YELLOW}Press Enter to use default values shown in brackets${NC}"
echo

# Git repository URL
echo -n "Git Repository URL [$DEFAULT_GIT_URL]: "
read -r GIT_URL
GIT_URL=${GIT_URL:-$DEFAULT_GIT_URL}

# Git revision/branch
echo -n "Git Branch/Revision [$DEFAULT_GIT_REVISION]: "
read -r GIT_REVISION
GIT_REVISION=${GIT_REVISION:-$DEFAULT_GIT_REVISION}

# Username/prefix
echo -n "User Prefix [$DEFAULT_USERNAME]: "
read -r USER_PREFIX
USER_PREFIX=${USER_PREFIX:-$DEFAULT_USERNAME}

# Target namespace
TARGET_NAMESPACE="ci-analysis-$USER_PREFIX"
echo -n "Target Namespace [$TARGET_NAMESPACE]: "
read -r NAMESPACE_INPUT
TARGET_NAMESPACE=${NAMESPACE_INPUT:-$TARGET_NAMESPACE}

# Check if namespace exists
if ! oc get namespace $TARGET_NAMESPACE &> /dev/null; then
    echo -e "${RED}❌ Namespace $TARGET_NAMESPACE not found!${NC}"
    echo -e "${YELLOW}💡 Run this first: ./deploy-user-namespace.sh $USER_PREFIX --init${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found existing namespace: $TARGET_NAMESPACE${NC}"

# Handle registry override if requested
if [ "$OVERRIDE_REGISTRY" = true ]; then
    echo -e "${YELLOW}🔄 Override registry flag detected, updating registry credentials...${NC}"
    update_registry_secret
fi

# Use pipeline defaults (can be overridden by user input)
DEFAULT_REGISTRY="quay.io"
DEFAULT_IMAGE_NAMESPACE="$USER_PREFIX"

# Image registry
echo -n "Image Registry [$DEFAULT_REGISTRY]: "
read -r IMAGE_REGISTRY
IMAGE_REGISTRY=${IMAGE_REGISTRY:-$DEFAULT_REGISTRY}

# Image namespace (username on registry)  
echo -n "Image Namespace (registry username) [$DEFAULT_IMAGE_NAMESPACE]: "
read -r IMAGE_NAMESPACE
IMAGE_NAMESPACE=${IMAGE_NAMESPACE:-$DEFAULT_IMAGE_NAMESPACE}

# Image name
DEFAULT_IMAGE_NAME="ci-analysis-agent"
echo -n "Image Name [$DEFAULT_IMAGE_NAME]: "
read -r IMAGE_NAME
IMAGE_NAME=${IMAGE_NAME:-$DEFAULT_IMAGE_NAME}

# Image tag
DEFAULT_TAG="$USER_PREFIX-$(date +%Y%m%d-%H%M%S)"
echo -n "Image Tag [$DEFAULT_TAG]: "
read -r IMAGE_TAG
IMAGE_TAG=${IMAGE_TAG:-$DEFAULT_TAG}

echo
echo -e "${GREEN}📊 Pipeline Configuration Summary:${NC}"
echo -e "  Git URL:          $GIT_URL"
echo -e "  Git Revision:     $GIT_REVISION"
echo -e "  User Prefix:      $USER_PREFIX"
echo -e "  Target Namespace: $TARGET_NAMESPACE"
echo -e "  Image Registry:   $IMAGE_REGISTRY"
echo -e "  Image Namespace:  $IMAGE_NAMESPACE"
echo -e "  Image Name:       $IMAGE_NAME"
echo -e "  Image Tag:        $IMAGE_TAG"
echo
echo -e "  Full Image URL:   $IMAGE_REGISTRY/$IMAGE_NAMESPACE/$IMAGE_NAME:$IMAGE_TAG"
echo

# Confirm before proceeding
echo -e "${YELLOW}Do you want to run the pipeline with these settings? (yes/no): ${NC}"
read -r CONFIRM
if [[ $CONFIRM != "yes" ]]; then
    echo -e "${GREEN}✅ Pipeline run cancelled${NC}"
    exit 0
fi

# Check if namespace exists
if ! oc get namespace $TARGET_NAMESPACE &> /dev/null; then
    echo -e "${RED}❌ Namespace '$TARGET_NAMESPACE' does not exist!${NC}"
    echo -e "${YELLOW}💡 Run this first: ./deploy-user-namespace.sh $USER_PREFIX --init${NC}"
    exit 1
fi

# Check if docker registry secret exists
if ! oc get secret docker-registry-secret -n $TARGET_NAMESPACE &> /dev/null; then
    echo -e "${RED}❌ Docker registry secret not found in namespace $TARGET_NAMESPACE${NC}"
    echo -e "${YELLOW}💡 Run this first: ./deploy-user-namespace.sh $USER_PREFIX --update-secret${NC}"
    exit 1
fi

echo -e "${GREEN}🚀 Starting pipeline with tkn CLI${NC}"
echo -e "${GREEN}📁 Using ephemeral storage (emptyDir) for shared workspace${NC}"

# Start the pipeline using tkn
echo -e "${BLUE}Running: tkn pipeline start ci-analysis-agent-pipeline...${NC}"

PIPELINE_RUN=$(tkn pipeline start ci-analysis-agent-pipeline \
    --param git-url="$GIT_URL" \
    --param git-revision="$GIT_REVISION" \
    --param target-namespace="$TARGET_NAMESPACE" \
    --param user-prefix="$USER_PREFIX" \
    --param image-registry="$IMAGE_REGISTRY" \
    --param image-namespace="$IMAGE_NAMESPACE" \
    --param image-name="$IMAGE_NAME" \
    --param image-tag="$IMAGE_TAG" \
    --workspace name=shared-data,emptyDir="" \
    --workspace name=docker-credentials,secret=docker-registry-secret \
    --serviceaccount pipeline-service-account \
    --namespace $TARGET_NAMESPACE \
    --output name)

if [ $? -eq 0 ] && [ -n "$PIPELINE_RUN" ]; then
    echo -e "${GREEN}✅ Pipeline run started successfully!${NC}"
    echo -e "${GREEN}📋 Pipeline Run Name: $PIPELINE_RUN${NC}"
    echo
    echo -e "${BLUE}📊 Monitoring Commands:${NC}"
    echo -e "  Watch pipeline runs:  ${YELLOW}tkn pipelinerun list -n $TARGET_NAMESPACE${NC}"
    echo -e "  Get status:           ${YELLOW}tkn pipelinerun describe $PIPELINE_RUN -n $TARGET_NAMESPACE${NC}"
    echo -e "  Check deployments:    ${YELLOW}oc get all -n $TARGET_NAMESPACE${NC}"
    echo
    echo -e "${BLUE}🔗 Quick Actions:${NC}"
    echo -e "  View in OpenShift:    Find '$PIPELINE_RUN' in the Pipelines section"
    echo
    echo -e "${GREEN}🔍 Following pipeline logs (press Ctrl+C to stop):${NC}"
    echo
    
    # Auto-follow logs
    tkn pipelinerun logs $PIPELINE_RUN -f -n $TARGET_NAMESPACE
else
    echo -e "${RED}❌ Failed to start pipeline run${NC}"
    exit 1
fi 