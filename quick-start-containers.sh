#!/bin/bash

# CI Analysis Agent - Quick Start with Containers
# This script sets up the CI Analysis Agent and Ollama in containers using Podman

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
OLLAMA_CONTAINER="ollama"
AGENT_CONTAINER="ci-analysis-agent"
LOKI_MCP_CONTAINER="loki-mcp"
OLLAMA_VOLUME="ollama-data"
OLLAMA_MODEL="qwen3:4b"
MCP_SERVER_PORT="8888"
AGENT_PORT="8000"
OLLAMA_PORT="11434"
USE_GPU="auto"  # auto, nvidia, amd, none
USE_REMOTE_VLLM=false  # Use remote vLLM instead of local Ollama

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if podman is available
check_podman() {
    if ! command_exists podman; then
        print_error "Podman is not installed. Please install Podman first."
        echo "Visit: https://podman.io/getting-started/installation"
        exit 1
    fi
    print_success "Podman is available"
}

# Function to validate remote vLLM environment variables
validate_vllm_env() {
    if [ "$USE_REMOTE_VLLM" = true ]; then
        print_status "Validating remote vLLM environment variables..."
        
        local missing_vars=""
        
        if [ -z "$HOSTED_VLLM_API_BASE" ]; then
            missing_vars="$missing_vars HOSTED_VLLM_API_BASE"
        fi
        
        if [ -z "$HOSTED_VLLM_API_KEY" ]; then
            missing_vars="$missing_vars HOSTED_VLLM_API_KEY"
        fi
        
        if [ -z "$HOSTED_VLLM_MODEL_NAME" ]; then
            missing_vars="$missing_vars HOSTED_VLLM_MODEL_NAME"
        fi
        if [ -n "$missing_vars" ]; then
            print_error "Missing required environment variables for remote vLLM:$missing_vars"
            echo ""
            echo "Please set the following environment variables before running this script:"
            echo "  export HOSTED_VLLM_API_BASE=\"your_vllm_api_base_url\""
            echo "  export HOSTED_VLLM_API_KEY=\"your_vllm_api_key\""
            echo "  export HOSTED_VLLM_MODEL_NAME=\"your_vllm_model\""
            echo ""
            echo "Example:"
            echo "  export HOSTED_VLLM_API_BASE=\"https://your-vllm-endpoint.com/v1\""
            echo "  export HOSTED_VLLM_API_KEY=\"your-api-key-here\""
            echo "  export HOSTED_VLLM_MODEL_NAME=\"claudette-sheep\""
            exit 1
        fi
        
        print_success "Remote vLLM environment variables are set"
        print_status "API Base: $HOSTED_VLLM_API_BASE"
        print_status "API Key: ${HOSTED_VLLM_API_KEY:0:8}..." # Show only first 8 characters for security
        print_status "Model Name: $HOSTED_VLLM_MODEL_NAME"
    fi
}

# Function to detect GPU capabilities
detect_gpu() {
    local gpu_type="none"
    
    # Check for NVIDIA GPU
    if command_exists nvidia-smi && nvidia-smi >/dev/null 2>&1; then
        gpu_type="nvidia"
        print_success "NVIDIA GPU detected"
    # Check for AMD GPU (ROCm)
    elif command_exists rocm-smi && rocm-smi >/dev/null 2>&1; then
        gpu_type="amd"
        print_success "AMD GPU detected"
    # Check for Intel GPU (if needed in future)
    elif lspci | grep -i "vga\|3d\|display" | grep -i intel >/dev/null 2>&1; then
        print_warning "Intel GPU detected but not supported for LLM acceleration"
        gpu_type="none"
    else
        print_warning "No compatible GPU detected, using CPU-only mode"
        gpu_type="none"
    fi
    
    echo "$gpu_type"
}

# Function to check GPU runtime support
check_gpu_runtime() {
    local gpu_type="$1"
    
    case "$gpu_type" in
        "nvidia")
            if ! command_exists nvidia-container-toolkit; then
                print_error "NVIDIA Container Toolkit not found. Please install it:"
                echo "  sudo dnf install nvidia-container-toolkit  # Fedora/RHEL"
                echo "  sudo apt install nvidia-container-toolkit  # Ubuntu/Debian"
                return 1
            fi
            
            # Test if podman can access GPU
            if ! podman run --rm --device nvidia.com/gpu=all nvidia/cuda:12.0-base-ubuntu20.04 nvidia-smi >/dev/null 2>&1; then
                print_error "Podman cannot access NVIDIA GPU. Please configure:"
                echo "  sudo nvidia-ctk runtime configure --runtime=podman"
                echo "  sudo systemctl restart podman"
                return 1
            fi
            print_success "NVIDIA GPU runtime configured"
            ;;
        "amd")
            if ! ls /dev/dri/render* >/dev/null 2>&1; then
                print_error "AMD GPU devices not found in /dev/dri/"
                return 1
            fi
            print_success "AMD GPU devices detected"
            ;;
        "none")
            print_status "Using CPU-only mode"
            ;;
    esac
    
    return 0
}

# Function to cleanup existing containers
cleanup_existing() {
    print_status "Cleaning up existing containers..."
    
    # Stop and remove pod if it exists (from previous versions)
    if podman pod exists "ci-analysis-pod" 2>/dev/null; then
        podman pod stop "ci-analysis-pod" 2>/dev/null || true
        podman pod rm "ci-analysis-pod" 2>/dev/null || true
    fi
    
    # Remove individual containers if they exist
    if podman container exists "$OLLAMA_CONTAINER" 2>/dev/null; then
        podman stop "$OLLAMA_CONTAINER" 2>/dev/null || true
        podman rm "$OLLAMA_CONTAINER" 2>/dev/null || true
    fi
    
    if podman container exists "$AGENT_CONTAINER" 2>/dev/null; then
        podman stop "$AGENT_CONTAINER" 2>/dev/null || true
        podman rm "$AGENT_CONTAINER" 2>/dev/null || true
    fi

    if podman container exists "$LOKI_MCP_CONTAINER" 2>/dev/null; then
        podman stop "$LOKI_MCP_CONTAINER" 2>/dev/null || true
        podman rm "$LOKI_MCP_CONTAINER" 2>/dev/null || true
    fi
    
    print_success "Cleanup completed"
}

# Function to create Ollama volume
create_volume() {
    print_status "Creating volume '$OLLAMA_VOLUME'..."
    if ! podman volume exists "$OLLAMA_VOLUME" 2>/dev/null; then
        podman volume create "$OLLAMA_VOLUME"
        print_success "Volume '$OLLAMA_VOLUME' created"
    else
        print_warning "Volume '$OLLAMA_VOLUME' already exists"
    fi
}

# Function to start Ollama container
start_ollama() {
    local gpu_type="$1"
    local gpu_args=""
    
    # Configure GPU arguments based on type
    case "$gpu_type" in
        "nvidia")
            gpu_args="--device nvidia.com/gpu=all"
            print_status "Starting Ollama container with NVIDIA GPU support..."
            ;;
        "amd")
            gpu_args="--device /dev/dri --device /dev/kfd --security-opt seccomp=unconfined"
            print_status "Starting Ollama container with AMD GPU support..."
            ;;
        "none")
            print_status "Starting Ollama container in CPU-only mode..."
            ;;
    esac
    
    podman run -d \
        --name "$OLLAMA_CONTAINER" \
        -p "$OLLAMA_PORT:$OLLAMA_PORT" \
        -v "$OLLAMA_VOLUME:/root/.ollama" \
        -e OLLAMA_HOST=0.0.0.0:$OLLAMA_PORT \
        $gpu_args \
        ollama/ollama:latest
    
    print_success "Ollama container started"
    
    # Wait for Ollama to be ready
    print_status "Waiting for Ollama to be ready..."
    sleep 10
    
    # Check if Ollama is responding
    for i in {1..30}; do
        if curl -s -f "http://localhost:$OLLAMA_PORT/api/version" >/dev/null 2>&1; then
            print_success "Ollama is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "Ollama failed to start properly"
            exit 1
        fi
        sleep 2
    done
}

# Function to pull Ollama model
pull_model() {
    print_status "Pulling Ollama model '$OLLAMA_MODEL'..."
    podman exec "$OLLAMA_CONTAINER" ollama pull "$OLLAMA_MODEL"
    print_success "Model '$OLLAMA_MODEL' pulled successfully"
    
    # Verify model is available
    print_status "Verifying model availability..."
    podman exec "$OLLAMA_CONTAINER" ollama list
}

# Function to build and start CI Analysis Agent
start_agent() {
    print_status "Building CI Analysis Agent container..."
    podman build -t ci-analysis-agent:latest .
    
    print_status "Starting CI Analysis Agent container..."
    
    # Prepare environment variables
    local env_args="-e LOG_LEVEL=INFO"
    
    if [ "$USE_REMOTE_VLLM" = true ]; then
        env_args="$env_args -e HOSTED_VLLM_API_BASE=$HOSTED_VLLM_API_BASE"
        env_args="$env_args -e HOSTED_VLLM_API_KEY=$HOSTED_VLLM_API_KEY"
        env_args="$env_args -e MODEL=$HOSTED_VLLM_MODEL_NAME"
        print_status "Using remote vLLM endpoint: $HOSTED_VLLM_API_BASE"
    else
        # Use default values for local Ollama setup
        env_args="$env_args -e MODEL=ollama_chat/$OLLAMA_MODEL"
        env_args="$env_args -e OLLAMA_API_BASE=http://localhost:$OLLAMA_PORT"
        print_status "Using local Ollama setup with default vLLM fallback"
    fi
    
    podman run -d \
        --name "$AGENT_CONTAINER" \
        --network host \
        $env_args \
        ci-analysis-agent:latest
    
    print_success "CI Analysis Agent container started"
}

build_loki_mcp() {
    print_status "Building Loki MCP container..."
    git clone https://github.com/grafana/loki-mcp.git
    podman build -t loki-mcp:latest loki-mcp
    print_success "Loki MCP container built"
}

start_loki_mcp() {
    print_status "Starting Loki MCP container..."
    podman run -d --name "$LOKI_MCP_CONTAINER" -e MCP_TRANSPORT=http=stream  -p "$MCP_SERVER_PORT:8080" loki-mcp:latest
    print_success "Loki MCP container started"
    # Wait for MCP server to be ready
    print_status "Waiting for MCP server to be ready..."
    sleep 5

    # Check if MCP server is responding
    for i in {1..15}; do
        if curl -s -f "http://localhost:$MCP_SERVER_PORT/" >/dev/null 2>&1; then
            print_success "Loki MCP server is ready"
            break
        fi
        if [ $i -eq 15 ]; then
            print_warning "Loki MCP server may not be fully ready yet"
        fi
        sleep 2
    done
}

# Function to verify deployment
verify_deployment() {
    print_status "Verifying deployment..."
    
    # Check if containers are running
    if [ "$USE_REMOTE_VLLM" = false ]; then
        if podman ps | grep -q "$OLLAMA_CONTAINER"; then
            print_success "Ollama container is running"
        else
            print_error "Ollama container is not running"
            return 1
        fi
    else
        print_status "Skipping Ollama container check (using remote vLLM)"
    fi
    
    if podman ps | grep -q "$AGENT_CONTAINER"; then
        print_success "CI Analysis Agent container is running"
    else
        print_error "CI Analysis Agent container is not running"
        return 1
    fi
    
    # Check if services are responding
    for i in {1..30}; do
        if curl -s -f "http://localhost:$AGENT_PORT/" >/dev/null 2>&1; then
            print_success "CI Analysis Agent is responding"
            break
        fi
        if [ $i -eq 30 ]; then
            print_warning "CI Analysis Agent may not be fully ready yet"
        fi
        sleep 2
    done
}

# Function to stop containers
stop_containers() {
    print_status "Stopping CI Analysis Agent containers..."
    
    # Stop containers

    if podman container exists "$LOKI_MCP_CONTAINER" 2>/dev/null; then
        if podman ps | grep -q "$LOKI_MCP_CONTAINER"; then
            print_status "Stopping Loki MCP container..."
            podman stop "$LOKI_MCP_CONTAINER"
            print_success "Loki MCP container stopped"
        else
            print_warning "Loki MCP container is not running"
        fi
    else
        print_warning "CI Analysis Agent container does not exist"
    fi

    if podman container exists "$AGENT_CONTAINER" 2>/dev/null; then
        if podman ps | grep -q "$AGENT_CONTAINER"; then
            print_status "Stopping CI Analysis Agent container..."
            podman stop "$AGENT_CONTAINER"
            print_success "CI Analysis Agent container stopped"
        else
            print_warning "CI Analysis Agent container is not running"
        fi
    else
        print_warning "CI Analysis Agent container does not exist"
    fi
    
    if podman container exists "$OLLAMA_CONTAINER" 2>/dev/null; then
        if podman ps | grep -q "$OLLAMA_CONTAINER"; then
            print_status "Stopping Ollama container..."
            podman stop "$OLLAMA_CONTAINER"
            print_success "Ollama container stopped"
        else
            print_warning "Ollama container is not running"
        fi
    else
        print_warning "Ollama container does not exist"
    fi
    
    echo ""
    echo "================================================================="
    echo "                 🛑 CONTAINERS STOPPED 🛑"
    echo "================================================================="
    echo ""
    echo "📊 Container Status:"
    podman ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "$OLLAMA_CONTAINER|$AGENT_CONTAINER|$LOKI_MCP_CONTAINER" || echo "  No containers found"
    echo ""
    echo "🎯 Quick Commands:"
    echo "  • Start containers:    podman start $OLLAMA_CONTAINER $AGENT_CONTAINER $LOKI_MCP_CONTAINER"
    echo "  • Clean up all:        $0 --clean-all"
    echo "  • Remove volumes:      $0 --remove-volumes"
    echo "  • Remove images:       $0 --remove-images"
    echo "  • Check logs:          podman logs $AGENT_CONTAINER"
    echo "  • Restart deployment: $0"
    echo "================================================================="
}

# Function to clean up all resources
clean_all() {
    local remove_volumes="$1"
    local remove_images="$2"
    local remove_pods="$3"
    
    print_status "Performing comprehensive cleanup..."
    
    # Stop containers first
    print_status "Stopping containers..."
    podman stop "$LOKI_MCP_CONTAINER" "$AGENT_CONTAINER" "$OLLAMA_CONTAINER" 2>/dev/null || true
    
    # Remove containers
    print_status "Removing containers..."
    if podman container exists "$LOKI_MCP_CONTAINER" 2>/dev/null; then
        podman rm -f "$LOKI_MCP_CONTAINER" 2>/dev/null || true
        print_success "Removed Loki MCP container"
    fi

    if podman container exists "$AGENT_CONTAINER" 2>/dev/null; then
        podman rm -f "$AGENT_CONTAINER" 2>/dev/null || true
        print_success "Removed CI Analysis Agent container"
    fi
    
    if podman container exists "$OLLAMA_CONTAINER" 2>/dev/null; then
        podman rm -f "$OLLAMA_CONTAINER" 2>/dev/null || true
        print_success "Removed Ollama container"
    fi
    
    # Remove pods if requested
    if [ "$remove_pods" = true ]; then
        print_status "Removing pods..."
        if podman pod exists "ci-analysis-pod" 2>/dev/null; then
            podman pod rm -f "ci-analysis-pod" 2>/dev/null || true
            print_success "Removed ci-analysis-pod"
        fi
        
        # Remove any other pods that might contain our containers
        for pod in $(podman pod ls --format "{{.Name}}" 2>/dev/null | grep -E "ci-analysis|ollama" || true); do
            if [ -n "$pod" ]; then
                podman pod rm -f "$pod" 2>/dev/null || true
                print_success "Removed pod: $pod"
            fi
        done
    fi
    
    # Remove volumes if requested
    if [ "$remove_volumes" = true ]; then
        print_status "Removing volumes..."
        if podman volume exists "$OLLAMA_VOLUME" 2>/dev/null; then
            podman volume rm -f "$OLLAMA_VOLUME" 2>/dev/null || true
            print_success "Removed volume: $OLLAMA_VOLUME"
        fi
        
        # Remove any other volumes that might be related
        for volume in $(podman volume ls --format "{{.Name}}" 2>/dev/null | grep -E "ollama|ci-analysis" || true); do
            if [ -n "$volume" ]; then
                podman volume rm -f "$volume" 2>/dev/null || true
                print_success "Removed volume: $volume"
            fi
        done
    fi
    
    # Remove images if requested
    if [ "$remove_images" = true ]; then
        print_status "Removing images..."
        
        # Remove CI Analysis Agent image
        if podman image exists "ci-analysis-agent:latest" 2>/dev/null; then
            podman rmi -f "ci-analysis-agent:latest" 2>/dev/null || true
            print_success "Removed image: ci-analysis-agent:latest"
        fi
        
        # Remove Ollama image
        if podman image exists "ollama/ollama:latest" 2>/dev/null; then
            podman rmi -f "ollama/ollama:latest" 2>/dev/null || true
            print_success "Removed image: ollama/ollama:latest"
        fi
        
        # Remove Loki MCP image
        if podman image exists "loki-mcp:latest" 2>/dev/null; then
            podman rmi -f "loki-mcp:latest" 2>/dev/null || true
            print_success "Removed image: loki-mcp:latest"
        fi
        
        # Remove any other related images
        for image in $(podman images --format "{{.Repository}}:{{.Tag}}" 2>/dev/null | grep -E "ci-analysis|ollama" || true); do
            if [ -n "$image" ] && [ "$image" != "ollama/ollama:latest" ] && [ "$image" != "ci-analysis-agent:latest" ]; then
                podman rmi -f "$image" 2>/dev/null || true
                print_success "Removed image: $image"
            fi
        done
    fi
    
    echo ""
    echo "================================================================="
    echo "                 🧹 CLEANUP COMPLETED 🧹"
    echo "================================================================="
    echo ""
    echo "📊 Remaining Resources:"
    echo ""
    echo "Containers:"
    podman ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "$OLLAMA_CONTAINER|$AGENT_CONTAINER|$LOKI_MCP_CONTAINER|ci-analysis" || echo "  No related containers found"
    echo ""
    echo "Volumes:"
    podman volume ls --format "table {{.Name}}\t{{.Driver}}" | grep -E "ollama|ci-analysis" || echo "  No related volumes found"
    echo ""
    echo "Images:"
    podman images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | grep -E "ollama|ci-analysis|loki-mcp" || echo "  No related images found"
    echo ""
    echo "🎯 Next Steps:"
    echo "  • Fresh deployment:    $0"
    echo "  • Check system:        podman system df"
    echo "  • Prune unused:        podman system prune -a"
    echo "================================================================="
}

# Function to show status
show_status() {
    local gpu_type="$1"
    
    echo ""
    echo "================================================================="
    echo "                 🚀 DEPLOYMENT SUCCESSFUL! 🚀"
    echo "================================================================="
    echo ""
    echo "🌐 Web Interface: http://localhost:$AGENT_PORT"
    
    if [ "$USE_REMOTE_VLLM" = false ]; then
        echo "🤖 Ollama API:    http://localhost:$OLLAMA_PORT"
        
        # Show GPU status
        case "$gpu_type" in
            "nvidia")
                echo "🎮 GPU Mode:      NVIDIA GPU acceleration enabled"
                ;;
            "amd")
                echo "🎮 GPU Mode:      AMD GPU acceleration enabled"
                ;;
            "none")
                echo "🎮 GPU Mode:      CPU-only mode"
                ;;
        esac
    else
        echo "🤖 Remote vLLM:   $HOSTED_VLLM_API_BASE"
        echo "🎮 GPU Mode:      Remote vLLM endpoint"
    fi
    
    echo ""
    echo "📊 Container Status:"
    podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    if [ "$USE_REMOTE_VLLM" = false ]; then
        echo "💾 Volume Status:"
        podman volume ls | grep "$OLLAMA_VOLUME" || echo "  No volumes found"
        echo ""
        echo "🎯 Quick Commands:"
        echo "  • View logs:           podman logs -f $AGENT_CONTAINER"
        echo "  • Check Ollama models: podman exec $OLLAMA_CONTAINER ollama list"
        echo "  • Stop containers:     $0 --stop"
        echo "  • Start containers:    podman start $OLLAMA_CONTAINER $AGENT_CONTAINER"
        echo "  • Clean up all:        $0 --clean-all"
        echo "  • Remove volumes:      $0 --remove-volumes"
        echo "  • Remove images:       $0 --remove-images"
    else
        echo "🎯 Quick Commands:"
        echo "  • View logs:           podman logs -f $AGENT_CONTAINER"
        echo "  • Stop container:      $0 --stop"
        echo "  • Start container:     podman start $AGENT_CONTAINER"
        echo "  • Clean up all:        $0 --clean-all"
        echo "  • Remove images:       $0 --remove-images"
    fi
    
    # GPU-specific commands (only for local Ollama)
    if [ "$USE_REMOTE_VLLM" = false ]; then
        if [ "$gpu_type" = "nvidia" ]; then
            echo "  • Check GPU usage:     podman exec $OLLAMA_CONTAINER nvidia-smi"
        elif [ "$gpu_type" = "amd" ]; then
            echo "  • Check GPU usage:     podman exec $OLLAMA_CONTAINER rocm-smi"
        fi
    fi
    
    echo ""
    echo "📖 For more information, see: CONTAINERIZED-DEPLOYMENT.md"
    echo "================================================================="
}

# Function to show help
show_help() {
    echo "CI Analysis Agent - Quick Start with Containers"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -s, --stop          Stop running containers"
    echo "  -c, --cleanup       Clean up existing containers before starting"
    echo "  -m, --model MODEL   Set the Ollama model to use (default: $OLLAMA_MODEL)"
    echo "  -p, --port PORT     Set the agent port (default: $AGENT_PORT)"
    echo "  --no-model          Skip pulling the Ollama model"
    echo "  --gpu TYPE          GPU type to use: auto, nvidia, amd, none (default: $USE_GPU)"
    echo "  --cpu-only          Force CPU-only mode, disable GPU detection"
    echo "  --remote-vllm       Use remote vLLM endpoint instead of local Ollama"
    echo ""
    echo "Cleanup Options:"
    echo "  --clean-all         Remove containers, volumes, images, and pods"
    echo "  --remove-volumes    Remove persistent volumes (loses model data)"
    echo "  --remove-images     Remove container images (forces re-download)"
    echo "  --remove-pods       Remove pods (for pod-based deployments)"
    echo ""
    echo "Examples:"
    echo "  $0                       # Start with default settings (auto GPU detection)"
    echo "  $0 -s                    # Stop running containers"
    echo "  $0 -c                    # Clean up and start fresh"
    echo "  $0 --clean-all           # Complete cleanup (containers, volumes, images, pods)"
    echo "  $0 --remove-volumes      # Remove only volumes"
    echo "  $0 --remove-images       # Remove only images"
    echo "  $0 -m llama3:8b          # Use a different model"
    echo "  $0 -p 3000               # Use port 3000 instead of 8000"
    echo "  $0 --gpu nvidia          # Force NVIDIA GPU usage"
    echo "  $0 --cpu-only            # Force CPU-only mode"
    echo "  $0 --remote-vllm         # Use remote vLLM (requires env vars)"
    echo ""
    echo "Remote vLLM Usage:"
    echo "  Set environment variables before using --remote-vllm:"
    echo "    export HOSTED_VLLM_API_BASE=\"https://your-vllm-endpoint.com/v1\""
    echo "    export HOSTED_VLLM_API_KEY=\"your-api-key-here\""
    echo "    $0 --remote-vllm       # Start without local Ollama"
}

# Main function
main() {
    local cleanup=false
    local skip_model=false
    local gpu_type="auto"
    local stop_containers_flag=false
    local clean_all_flag=false
    local remove_volumes_flag=false
    local remove_images_flag=false
    local remove_pods_flag=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -s|--stop)
                stop_containers_flag=true
                shift
                ;;
            -c|--cleanup)
                cleanup=true
                shift
                ;;
            --clean-all)
                clean_all_flag=true
                remove_volumes_flag=true
                remove_images_flag=true
                remove_pods_flag=true
                shift
                ;;
            --remove-volumes)
                remove_volumes_flag=true
                shift
                ;;
            --remove-images)
                remove_images_flag=true
                shift
                ;;
            --remove-pods)
                remove_pods_flag=true
                shift
                ;;
            -m|--model)
                OLLAMA_MODEL="$2"
                shift 2
                ;;
            -p|--port)
                AGENT_PORT="$2"
                shift 2
                ;;
            --no-model)
                skip_model=true
                shift
                ;;
            --gpu)
                USE_GPU="$2"
                shift 2
                ;;
            --cpu-only)
                USE_GPU="none"
                shift
                ;;
            --remote-vllm)
                USE_REMOTE_VLLM=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Handle stop command
    if [ "$stop_containers_flag" = true ]; then
        stop_containers
        exit 0
    fi
    
    # Handle cleanup commands
    if [ "$clean_all_flag" = true ] || [ "$remove_volumes_flag" = true ] || [ "$remove_images_flag" = true ] || [ "$remove_pods_flag" = true ]; then
        clean_all "$remove_volumes_flag" "$remove_images_flag" "$remove_pods_flag"
        exit 0
    fi
    
    print_status "Starting CI Analysis Agent containerized deployment..."
    
    # Check prerequisites
    check_podman
    
    # Validate remote vLLM environment variables if needed
    validate_vllm_env
    
    # Determine GPU type (only needed for local Ollama)
    if [ "$USE_REMOTE_VLLM" = false ]; then
        if [ "$USE_GPU" = "auto" ]; then
            gpu_type=$(detect_gpu)
        else
            gpu_type="$USE_GPU"
        fi
        
        # Validate GPU runtime if needed
        if [ "$gpu_type" != "none" ]; then
            if ! check_gpu_runtime "$gpu_type"; then
                print_warning "GPU runtime check failed, falling back to CPU-only mode"
                gpu_type="none"
            fi
        fi
    else
        gpu_type="none"  # GPU not relevant for remote vLLM
        print_status "Using remote vLLM - skipping GPU detection"
    fi
    
    # Cleanup if requested
    if [ "$cleanup" = true ]; then
        cleanup_existing
    fi
    
    # Start deployment
    if [ "$USE_REMOTE_VLLM" = false ]; then
        create_volume
        start_ollama "$gpu_type"
        
        if [ "$skip_model" = false ]; then
            pull_model
        fi
    else
        print_status "Skipping Ollama setup (using remote vLLM)"
    fi

    build_loki_mcp
    start_loki_mcp
    start_agent
    verify_deployment
    show_status "$gpu_type"
}

# Trap to cleanup on exit
trap 'echo ""; print_warning "Deployment interrupted"' INT TERM

# Run main function
main "$@" 