#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to show usage
show_usage() {
    echo -e "${BLUE}Usage: $0 <username> [OPTIONS]${NC}"
    echo -e "${BLUE}Modes:${NC}"
    echo -e "  (no flags)         Deploy only if project exists (for development iterations)"
    echo -e "  --init             Initialize new project: create namespace + setup credentials"
    echo -e "  --update-secret    Update container registry credentials"
    echo -e "  --cleanup          Remove all resources and namespace for the user"
    echo -e "  --help             Show this help message"
    echo -e ""
    echo -e "${BLUE}Examples:${NC}"
    echo -e "  $0 alice           # Deploy to existing project (development workflow)"
    echo -e "  $0 alice --init    # First-time setup: create namespace + credentials"
    echo -e "  $0 alice --update-secret  # Update registry credentials"
    echo -e "  $0 alice --cleanup # Remove all resources for user alice"
    echo -e ""
    echo -e "${BLUE}Workflow:${NC}"
    echo -e "  1. First time: $0 alice --init"
    echo -e "  2. Development: $0 alice (repeatedly for updates)"
    echo -e "  3. Update creds: $0 alice --update-secret (when needed)"
    echo -e "  4. Cleanup: $0 alice --cleanup (when done)"
}

# Parse command line arguments
USERNAME=""
MODE="development"  # default mode

while [[ $# -gt 0 ]]; do
    case $1 in
        --init)
            MODE="init"
            shift
            ;;
        --update-secret)
            MODE="update-secret"
            shift
            ;;
        --cleanup)
            MODE="cleanup"
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        -*)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            show_usage
            exit 1
            ;;
        *)
            if [ -z "$USERNAME" ]; then
                USERNAME=$1
            else
                echo -e "${RED}❌ Multiple usernames provided${NC}"
                show_usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Check if username is provided
if [ -z "$USERNAME" ]; then
    echo -e "${RED}❌ Username is required${NC}"
    show_usage
    exit 1
fi

NAMESPACE="ci-analysis-$USERNAME"

# Function to cleanup user resources
cleanup_user_resources() {
    echo -e "${YELLOW}🧹 Starting cleanup for user: $USERNAME${NC}"
    echo -e "${YELLOW}📦 Target namespace: $NAMESPACE${NC}"
    
    if ! oc get namespace $NAMESPACE &> /dev/null; then
        echo -e "${YELLOW}⚠️  Namespace '$NAMESPACE' does not exist, nothing to clean up${NC}"
        return 0
    fi
    
    echo -e "${RED}⚠️  This will permanently delete ALL resources in namespace: $NAMESPACE${NC}"
    echo -e "${RED}⚠️  Including: pipelines, tasks, secrets, deployments, services, routes, PVCs${NC}"
    echo -e "${YELLOW}Type 'DELETE' to confirm (case-sensitive): ${NC}"
    read -r CONFIRM
    
    if [[ $CONFIRM != "DELETE" ]]; then
        echo -e "${GREEN}✅ Cleanup cancelled${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}🗑️  Deleting all resources in namespace $NAMESPACE...${NC}"
    local cleanup_failed=false
    
    # Function to delete resources with error checking
    delete_resources() {
        local resource_type=$1
        local description=$2
        
        echo -e "${YELLOW}   Deleting $description...${NC}"
        if ! oc delete $resource_type --all -n $NAMESPACE --timeout=60s 2>/dev/null; then
            echo -e "${YELLOW}⚠️  Some $description may not have been deleted${NC}"
            cleanup_failed=true
        fi
    }
    
    # Delete resources in specific order to avoid dependency issues
    delete_resources "pipelineruns" "pipeline runs"
    delete_resources "taskruns" "task runs"
    delete_resources "pods" "pods"
    delete_resources "jobs" "jobs"
    delete_resources "deployments" "deployments"
    delete_resources "replicasets" "replica sets"
    delete_resources "services" "services"
    delete_resources "routes" "routes (OpenShift)"
    delete_resources "ingresses" "ingresses"
    delete_resources "configmaps" "config maps"
    delete_resources "secrets" "secrets"
    delete_resources "pvc" "persistent volume claims"
    
    # Delete Tekton resources
    delete_resources "pipelines" "pipelines"
    delete_resources "tasks" "tasks"
    delete_resources "eventlisteners" "event listeners"
    delete_resources "triggerbindings" "trigger bindings"
    delete_resources "triggertemplates" "trigger templates"
    
    # Delete RBAC resources
    delete_resources "serviceaccounts" "service accounts"
    delete_resources "rolebindings" "role bindings"
    delete_resources "roles" "roles"
    
    # Final cleanup - delete any remaining resources
    echo -e "${YELLOW}   Final cleanup of any remaining resources...${NC}"
    oc delete all --all -n $NAMESPACE --timeout=60s 2>/dev/null || cleanup_failed=true
    
    if [ "$cleanup_failed" = true ]; then
        echo -e "${YELLOW}⚠️  Some resources may not have been deleted completely${NC}"
        echo -e "${YELLOW}💡 You may need to manually check and clean up remaining resources${NC}"
    fi
    
    echo -e "${YELLOW}🗑️  Deleting namespace $NAMESPACE...${NC}"
    if ! oc delete namespace $NAMESPACE --timeout=300s; then
        echo -e "${RED}❌ Failed to delete namespace $NAMESPACE${NC}"
        echo -e "${YELLOW}💡 Please check for remaining resources and try manual deletion${NC}"
        return 1
    fi
    
    # Wait for namespace to be deleted with timeout
    echo -e "${YELLOW}⏳ Waiting for namespace deletion to complete...${NC}"
    local wait_count=0
    local max_wait=60  # 5 minutes (60 * 5 seconds)
    
    while oc get namespace $NAMESPACE &> /dev/null && [ $wait_count -lt $max_wait ]; do
        echo -e "${YELLOW}   Still deleting... (${wait_count}/${max_wait})${NC}"
        sleep 5
        ((wait_count++))
    done
    
    if oc get namespace $NAMESPACE &> /dev/null; then
        echo -e "${RED}❌ Namespace deletion timed out after 5 minutes${NC}"
        echo -e "${YELLOW}💡 The namespace may still be in 'Terminating' state${NC}"
        echo -e "${YELLOW}💡 Check: oc get namespace $NAMESPACE${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Cleanup completed for user: $USERNAME${NC}"
    echo -e "${GREEN}🎯 Namespace $NAMESPACE and all resources have been removed${NC}"
}

# Function to validate email format
validate_email() {
    local email=$1
    if [[ $email =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        return 0
    else
        return 1
    fi
}

# Function to create docker registry secret
create_docker_secret() {
    echo -e "${GREEN}🔐 Creating Docker Registry Secret${NC}"
    echo -e "${YELLOW}Please provide your Docker registry credentials:${NC}"
    echo -e "${YELLOW}(This is required for the pipeline to build and push images)${NC}"
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
        
        if [ -n "$DOCKER_EMAIL" ] && validate_email "$DOCKER_EMAIL"; then
            break
        else
            echo -e "${RED}❌ Please enter a valid email address${NC}"
        fi
    done
    
    echo -e "${GREEN}📝 Creating docker registry secret...${NC}"
    
    # Check if secret already exists and get user confirmation
    if oc get secret docker-registry-secret -n $NAMESPACE &> /dev/null; then
        echo -e "${YELLOW}⚠️  Secret 'docker-registry-secret' already exists${NC}"
        echo -e "${YELLOW}Do you want to replace it? (yes/no): ${NC}"
        read -r REPLACE_SECRET
        if [[ $REPLACE_SECRET != "yes" ]]; then
            echo -e "${GREEN}✅ Keeping existing secret${NC}"
            # Clear sensitive variables
            unset DOCKER_PASSWORD DOCKER_USERNAME
            return 0
        fi
        
        if ! oc delete secret docker-registry-secret -n $NAMESPACE; then
            echo -e "${RED}❌ Failed to delete existing secret${NC}"
            unset DOCKER_PASSWORD DOCKER_USERNAME
            return 1
        fi
    fi
    
    # Create secret using a more secure method
    if kubectl create secret docker-registry docker-registry-secret \
        --docker-server="$DOCKER_SERVER" \
        --docker-username="$DOCKER_USERNAME" \
        --docker-password="$DOCKER_PASSWORD" \
        --docker-email="$DOCKER_EMAIL" \
        -n $NAMESPACE &> /dev/null; then
        
        echo -e "${GREEN}✅ Docker registry secret created successfully${NC}"
        
        # Clear sensitive variables from memory
        unset DOCKER_PASSWORD DOCKER_USERNAME DOCKER_EMAIL
        return 0
    else
        echo -e "${RED}❌ Failed to create docker registry secret${NC}"
        echo -e "${YELLOW}💡 Please check your credentials and try again${NC}"
        
        # Clear sensitive variables from memory
        unset DOCKER_PASSWORD DOCKER_USERNAME DOCKER_EMAIL
        return 1
    fi
}

# Functions are defined below, main execution is at the end of the file

# Function to handle init mode (first-time setup)
handle_init_mode() {
    echo -e "${GREEN}🚀 Initializing CI Analysis Agent Pipeline for user: $USERNAME${NC}"
    echo -e "${GREEN}📦 Target namespace: $NAMESPACE${NC}"
    
    # Check if namespace already exists
    if oc get namespace $NAMESPACE &> /dev/null; then
        echo -e "${YELLOW}⚠️  Namespace '$NAMESPACE' already exists!${NC}"
        echo -e "${YELLOW}Are you sure you want to continue with initialization? (yes/no): ${NC}"
        read -r CONFIRM
        if [[ $CONFIRM != "yes" ]]; then
            echo -e "${GREEN}✅ Initialization cancelled${NC}"
            echo -e "${YELLOW}💡 Use '$0 $USERNAME' for development deployments to existing namespace${NC}"
            exit 0
        fi
    fi
    
    check_prerequisites
    create_namespace_and_deploy_resources
    
    echo -e "${GREEN}🔐 Setting up container registry credentials...${NC}"
    if ! create_docker_secret; then
        echo -e "${RED}❌ Failed to create docker registry secret during initialization${NC}"
        echo -e "${YELLOW}💡 You can update credentials later with: $0 $USERNAME --update-secret${NC}"
        exit 1
    fi
    
    show_completion_message "init"
}

# Function to handle development mode (existing project)
handle_development_mode() {
    echo -e "${GREEN}🚀 Deploying to existing CI Analysis Agent project for user: $USERNAME${NC}"
    echo -e "${GREEN}📦 Target namespace: $NAMESPACE${NC}"
    
    # Check if namespace exists
    if ! oc get namespace $NAMESPACE &> /dev/null; then
        echo -e "${RED}❌ Namespace '$NAMESPACE' does not exist!${NC}"
        echo -e "${YELLOW}💡 Use '$0 $USERNAME --init' to create the project for the first time${NC}"
        exit 1
    fi
    
    check_prerequisites
    deploy_resources_only
    
    # Check secret status but don't create
    if oc get secret docker-registry-secret -n $NAMESPACE &> /dev/null; then
        echo -e "${GREEN}✅ Docker registry secret already configured${NC}"
    else
        echo -e "${YELLOW}⚠️  Docker registry secret not found${NC}"
        echo -e "${YELLOW}💡 Use '$0 $USERNAME --update-secret' to configure credentials${NC}"
    fi
    
    show_completion_message "development"
}

# Function to handle update secret mode
handle_update_secret_mode() {
    echo -e "${GREEN}🔐 Updating container registry credentials for user: $USERNAME${NC}"
    echo -e "${GREEN}📦 Target namespace: $NAMESPACE${NC}"
    
    # Check if namespace exists
    if ! oc get namespace $NAMESPACE &> /dev/null; then
        echo -e "${RED}❌ Namespace '$NAMESPACE' does not exist!${NC}"
        echo -e "${YELLOW}💡 Use '$0 $USERNAME --init' to create the project for the first time${NC}"
        exit 1
    fi
    
    check_prerequisites
    
    echo -e "${GREEN}🔄 Updating docker registry secret...${NC}"
    if ! create_docker_secret; then
        echo -e "${RED}❌ Failed to update docker registry secret${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Container registry credentials updated successfully!${NC}"
    echo -e "${GREEN}🎯 You can now run pipelines with the updated credentials${NC}"
}

# Function to check prerequisites
check_prerequisites() {
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
        echo -e "${YELLOW}⚠️  Tekton Triggers not found.${NC}"
        echo -e "${YELLOW}Do you want to install Tekton Triggers? (yes/no): ${NC}"
        read -r INSTALL_TRIGGERS
        if [[ $INSTALL_TRIGGERS == "yes" ]]; then
            echo -e "${GREEN}📥 Installing Tekton Triggers...${NC}"
            if ! oc apply -f https://storage.googleapis.com/tekton-releases/triggers/latest/release.yaml; then
                echo -e "${RED}❌ Failed to install Tekton Triggers release${NC}"
                exit 1
            fi
            if ! oc apply -f https://storage.googleapis.com/tekton-releases/triggers/latest/interceptors.yaml; then
                echo -e "${RED}❌ Failed to install Tekton Triggers interceptors${NC}"
                exit 1
            fi
            echo -e "${GREEN}✅ Tekton Triggers installed successfully${NC}"
        else
            echo -e "${YELLOW}⚠️  Pipeline triggers will not be available without Tekton Triggers${NC}"
            echo -e "${YELLOW}💡 Manual pipeline runs will still work${NC}"
        fi
    fi
}

# Orphaned code removed - this functionality is handled by the mode functions

# Function to deploy a file with namespace replacement
deploy_with_namespace() {
    local file=$1
    local description=$2
    local script_dir=$(dirname "$0")
    local full_path="$script_dir/$file"
    
    echo -e "${GREEN}$description${NC}"
    
    if [ ! -f "$full_path" ]; then
        echo -e "${RED}❌ File not found: $full_path${NC}"
        echo -e "${YELLOW}💡 Make sure you're running this script from the correct directory${NC}"
        return 1
    fi
    
    sed "s/NAMESPACE_PLACEHOLDER/$NAMESPACE/g" "$full_path" | oc apply -f -
}

# Function to create namespace and deploy all resources (init mode)
create_namespace_and_deploy_resources() {
    echo -e "${GREEN}📦 Creating namespace: $NAMESPACE${NC}"
    if ! oc get namespace $NAMESPACE &> /dev/null; then
        oc create namespace $NAMESPACE
    else
        echo -e "${YELLOW}Namespace '$NAMESPACE' already exists${NC}"
    fi
    
    deploy_resources_only
}

# Function to deploy only resources (development mode)
deploy_resources_only() {
    echo -e "${GREEN}🔄 Deploying/updating pipeline resources...${NC}"
    deploy_with_namespace "rbac.yaml" "🔐 Deploying RBAC..."
    deploy_with_namespace "tasks.yaml" "📝 Deploying Tasks..."
    deploy_with_namespace "pipeline.yaml" "🔄 Deploying Pipeline..."
    deploy_with_namespace "triggers.yaml" "⚡ Deploying Triggers..."
    
    # Create the application configuration configmap
    echo -e "${GREEN}⚙️  Creating application configuration...${NC}"
    oc create configmap ${USERNAME}-ci-analysis-config \
        --from-literal=OLLAMA_API_BASE="http://${USERNAME}-ollama-service:11434" \
        --from-literal=GOOGLE_GENAI_USE_VERTEXAI="FALSE" \
        --from-literal=PYTHONPATH="/app" \
        -n $NAMESPACE \
        --dry-run=client -o yaml | oc apply -f -
        
    # Grant SCC permissions for container builds (persistent)
    echo -e "${GREEN}🔐 Configuring Security Context Constraints for buildah...${NC}"
    if ! oc adm policy add-scc-to-user pipelines-scc system:serviceaccount:${NAMESPACE}:pipeline-service-account &> /dev/null; then
        echo -e "${YELLOW}⚠️  SCC policy may already be applied or cluster permissions insufficient${NC}"
    else
        echo -e "${GREEN}✅ SCC permissions configured successfully${NC}"
    fi

    # Note: pipeline-run.yaml is a template file, not deployed directly
    echo -e "${GREEN}📄 Pipeline Run template available for use${NC}"
}



# Function to show completion message
show_completion_message() {
    local mode=$1
    local script_dir=$(dirname "$0")
    
    echo -e "${GREEN}✅ Pipeline deployment completed for user: $USERNAME${NC}"
    
    case $mode in
        "init")
            echo -e "${GREEN}🎉 Initial setup complete!${NC}"
            ;;
        "development") 
            echo -e "${GREEN}🔄 Development deployment updated!${NC}"
            ;;
    esac
    
    echo -e "${GREEN}🎯 Next steps:${NC}"

    if oc get secret docker-registry-secret -n $NAMESPACE &> /dev/null; then
        echo -e "1. ✅ Docker registry secret configured"
    else
        echo -e "1. ⚠️  Configure docker registry secret: $0 $USERNAME --update-secret"
    fi

    echo -e "2. Update GitHub webhook secret in namespace $NAMESPACE if using webhooks"
    echo -e "3. Run the pipeline using one of these methods:"
    
    # Check if files exist before referencing them
    if [ -f "$script_dir/user-examples.yaml" ]; then
        echo -e "   • Use examples from $script_dir/user-examples.yaml"
    else
        echo -e "   • Use examples from user-examples.yaml (if available)"
    fi
    
    if [ -f "$script_dir/pipeline-run.yaml" ]; then
        echo -e "   • Create from template: sed 's/NAMESPACE_PLACEHOLDER/$NAMESPACE/g' $script_dir/pipeline-run.yaml | oc create -f -"
    else
        echo -e "   • Create pipeline runs manually or from templates"
    fi
    
    echo -e "   • Use webhook triggers (if configured)"
    echo -e "4. Monitor the pipeline with: tkn pipelinerun logs --last -f -n $NAMESPACE"

    # Get webhook URL if triggers are deployed
    if oc get route ci-analysis-agent-webhook -n $NAMESPACE &> /dev/null 2>&1; then
        WEBHOOK_URL=$(oc get route ci-analysis-agent-webhook -n $NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null)
        if [ -n "$WEBHOOK_URL" ]; then
            echo -e "${GREEN}🔗 Webhook URL: https://${WEBHOOK_URL}${NC}"
            echo -e "   Configure this URL in your GitHub repository webhooks"
        fi
    fi

    echo -e "${GREEN}📊 Resources deployed to namespace: $NAMESPACE${NC}"
    echo -e "${GREEN}🔍 View deployment: oc get all -n $NAMESPACE${NC}"
    echo -e ""
    echo -e "${BLUE}💡 Useful commands:${NC}"
    echo -e "   Development deploy:     $0 $USERNAME"
    echo -e "   Update credentials:     $0 $USERNAME --update-secret"
    echo -e "   Cleanup everything:     $0 $USERNAME --cleanup"
    echo -e "   View help:              $0 --help"
}

# Main execution logic based on mode
case $MODE in
    "cleanup")
        cleanup_user_resources
        exit 0
        ;;
    "update-secret")
        handle_update_secret_mode
        exit 0
        ;;
    "init")
        handle_init_mode
        ;;
    "development")
        handle_development_mode
        ;;
    *)
        echo -e "${RED}❌ Unknown mode: $MODE${NC}"
        exit 1
        ;;
esac 