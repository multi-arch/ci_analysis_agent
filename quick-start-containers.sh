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
POD_NAME="ci-analysis-pod"
OLLAMA_CONTAINER="ollama"
AGENT_CONTAINER="ci-analysis-agent"
OLLAMA_VOLUME="ollama-data"
OLLAMA_MODEL="qwen3:4b"
AGENT_PORT="8000"
OLLAMA_PORT="11434"

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

# Function to cleanup existing containers
cleanup_existing() {
    print_status "Cleaning up existing containers..."
    
    # Stop and remove containers if they exist
    if podman pod exists "$POD_NAME" 2>/dev/null; then
        podman pod stop "$POD_NAME" 2>/dev/null || true
        podman pod rm "$POD_NAME" 2>/dev/null || true
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
    
    print_success "Cleanup completed"
}

# Function to create pod
create_pod() {
    print_status "Creating pod '$POD_NAME'..."
    podman pod create --name "$POD_NAME" -p "$AGENT_PORT:$AGENT_PORT" -p "$OLLAMA_PORT:$OLLAMA_PORT"
    print_success "Pod '$POD_NAME' created"
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
    print_status "Starting Ollama container..."
    podman run -d \
        --name "$OLLAMA_CONTAINER" \
        --pod "$POD_NAME" \
        -v "$OLLAMA_VOLUME:/root/.ollama" \
        -e OLLAMA_HOST=0.0.0.0:$OLLAMA_PORT \
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
    podman run -d \
        --name "$AGENT_CONTAINER" \
        --network host \
        -e OLLAMA_API_BASE="http://localhost:$OLLAMA_PORT" \
        -e LOG_LEVEL=INFO \
        -v "$(pwd):/app/workspace:Z" \
        ci-analysis-agent:latest
    
    print_success "CI Analysis Agent container started"
}

# Function to verify deployment
verify_deployment() {
    print_status "Verifying deployment..."
    
    # Check if containers are running
    if podman ps | grep -q "$OLLAMA_CONTAINER"; then
        print_success "Ollama container is running"
    else
        print_error "Ollama container is not running"
        return 1
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

# Function to show status
show_status() {
    echo ""
    echo "================================================================="
    echo "                 🚀 DEPLOYMENT SUCCESSFUL! 🚀"
    echo "================================================================="
    echo ""
    echo "🌐 Web Interface: http://localhost:$AGENT_PORT"
    echo "🤖 Ollama API:    http://localhost:$OLLAMA_PORT"
    echo ""
    echo "📊 Container Status:"
    podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "💾 Volume Status:"
    podman volume ls | grep "$OLLAMA_VOLUME" || echo "  No volumes found"
    echo ""
    echo "🎯 Quick Commands:"
    echo "  • View logs:           podman logs -f $AGENT_CONTAINER"
    echo "  • Check Ollama models: podman exec $OLLAMA_CONTAINER ollama list"
    echo "  • Stop all:            podman pod stop $POD_NAME"
    echo "  • Start all:           podman pod start $POD_NAME"
    echo "  • Remove all:          podman pod rm -f $POD_NAME"
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
    echo "  -h, --help        Show this help message"
    echo "  -c, --cleanup     Clean up existing containers before starting"
    echo "  -m, --model MODEL Set the Ollama model to use (default: $OLLAMA_MODEL)"
    echo "  -p, --port PORT   Set the agent port (default: $AGENT_PORT)"
    echo "  --no-model        Skip pulling the Ollama model"
    echo ""
    echo "Examples:"
    echo "  $0                    # Start with default settings"
    echo "  $0 -c                 # Clean up and start fresh"
    echo "  $0 -m llama3:8b       # Use a different model"
    echo "  $0 -p 3000            # Use port 3000 instead of 8000"
}

# Main function
main() {
    local cleanup=false
    local skip_model=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -c|--cleanup)
                cleanup=true
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
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    print_status "Starting CI Analysis Agent containerized deployment..."
    
    # Check prerequisites
    check_podman
    
    # Cleanup if requested
    if [ "$cleanup" = true ]; then
        cleanup_existing
    fi
    
    # Start deployment
    create_pod
    create_volume
    start_ollama
    
    if [ "$skip_model" = false ]; then
        pull_model
    fi
    
    start_agent
    verify_deployment
    show_status
}

# Trap to cleanup on exit
trap 'echo ""; print_warning "Deployment interrupted"' INT TERM

# Run main function
main "$@" 