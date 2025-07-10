# Containerized Deployment with Podman

This guide explains how to run the CI Analysis Agent and Ollama model in local containers using Podman for better isolation, consistency, and easier management.

## 🐳 Overview

Running in containers provides several benefits:
- **Isolation**: Clean separation from host system
- **Consistency**: Same environment across different machines
- **Easy cleanup**: Remove containers without affecting host
- **Version management**: Easy switching between different versions
- **Resource control**: Better control over CPU and memory usage

## 📋 Prerequisites

### Required Software
- **Podman** 4.0+ (or Docker as alternative)
- **Git** for cloning the repository
- **8GB+ RAM** (recommended 16GB for better model performance)
- **10GB+ storage** for models and container images

### Install Podman
```bash
# On Fedora/RHEL/CentOS
sudo dnf install podman

# On Ubuntu/Debian
sudo apt update && sudo apt install podman

# On macOS
brew install podman
podman machine init
podman machine start

# Verify installation
podman --version
```

## 🚀 Quick Start

### Super Fast Start (Automated)

For the fastest setup experience:

```bash
# Clone the repository
git clone https://github.com/sherine-k/ci_analysis_agent.git
cd ci_analysis_agent

# Run the automated setup script
./quick-start-containers.sh

# That's it! The script will:
# ✅ Create a pod for the application
# ✅ Start Ollama container with persistent storage
# ✅ Pull the qwen3:4b model automatically
# ✅ Build and start the CI Analysis Agent
# ✅ Verify everything is working
# ✅ Show you the status and useful commands

# Access the web interface at http://localhost:8000
```

**Script Options:**
```bash
# Get help
./quick-start-containers.sh --help

# Clean up existing containers first
./quick-start-containers.sh --cleanup

# Use a different model
./quick-start-containers.sh --model llama3:8b

# Use a different port
./quick-start-containers.sh --port 3000

# Skip model download (if you already have it)
./quick-start-containers.sh --no-model

# GPU acceleration options
./quick-start-containers.sh --gpu nvidia    # Force NVIDIA GPU
./quick-start-containers.sh --gpu amd       # Force AMD GPU
./quick-start-containers.sh --cpu-only      # Force CPU-only mode
```

**Container Management Options:**
```bash
# Stop running containers
./quick-start-containers.sh --stop

# Complete cleanup (containers, volumes, images, pods)
./quick-start-containers.sh --clean-all

# Selective cleanup options
./quick-start-containers.sh --remove-volumes    # Remove persistent volumes (loses model data)
./quick-start-containers.sh --remove-images     # Remove container images (forces re-download)
./quick-start-containers.sh --remove-pods       # Remove pods (for pod-based deployments)
```

### Complete Lifecycle Management

The `quick-start-containers.sh` script provides comprehensive lifecycle management:

```bash
# 🚀 Initial deployment
./quick-start-containers.sh

# 🛑 Stop running containers (preserves data)
./quick-start-containers.sh --stop

# 🔄 Restart containers (if already deployed)
podman start ollama ci-analysis-agent

# 🧹 Clean up specific resources
./quick-start-containers.sh --remove-volumes    # Remove persistent volumes
./quick-start-containers.sh --remove-images     # Remove container images
./quick-start-containers.sh --remove-pods       # Remove pods

# 🗑️ Complete cleanup and fresh start
./quick-start-containers.sh --clean-all         # Remove everything
./quick-start-containers.sh                     # Fresh deployment

# 🔧 Maintenance operations
./quick-start-containers.sh --cleanup           # Clean up before starting
./quick-start-containers.sh --no-model          # Skip model download
./quick-start-containers.sh --gpu nvidia        # Force specific GPU
```

### Manual Step-by-Step Setup

If you prefer manual control or want to understand each step:

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/sherine-k/ci_analysis_agent.git
cd ci_analysis_agent

# Create a pod for our application (optional but recommended)
podman pod create --name ci-analysis-pod -p 8000:8000 -p 11434:11434
```

### 2. Run Ollama Container

```bash
# Create volume for persistent model storage
podman volume create ollama-data

# Run Ollama container
podman run -d \
  --name ollama \
  --pod ci-analysis-pod \
  -v ollama-data:/root/.ollama \
  -e OLLAMA_HOST=0.0.0.0:11434 \
  ollama/ollama:latest

# Alternative: Run without pod (manual port mapping)
# podman run -d \
#   --name ollama \
#   -p 11434:11434 \
#   -v ollama-data:/root/.ollama \
#   -e OLLAMA_HOST=0.0.0.0:11434 \
#   ollama/ollama:latest

# Wait for Ollama to start
sleep 10

# Pull the qwen3:4b model
podman exec ollama ollama pull qwen3:4b

# Verify model is available
podman exec ollama ollama list
```

### 3. Build and Run CI Analysis Agent

```bash
# Build the CI Analysis Agent container
podman build -t ci-analysis-agent:latest .

# Run the CI Analysis Agent container
podman run -d \
  --name ci-analysis-agent \
  --pod ci-analysis-pod \
  -e OLLAMA_API_BASE=http://localhost:11434 \
  -e LOG_LEVEL=INFO \
  -v "$(pwd)":/app/workspace:Z \
  ci-analysis-agent:latest

# Alternative: Run without pod (manual port mapping and networking)
# podman run -d \
#   --name ci-analysis-agent \
#   -p 8000:8000 \
#   --link ollama:ollama \
#   -e OLLAMA_API_BASE=http://ollama:11434 \
#   -e LOG_LEVEL=INFO \
#   -v "$(pwd)":/app/workspace:Z \
#   ci-analysis-agent:latest
```

### 4. Access the Application

```bash
# Check if containers are running
podman pod ps
podman ps

# Access the web interface
echo "Open http://localhost:8000 in your browser"

# View logs
podman logs ci-analysis-agent
podman logs ollama
```

## 🎮 GPU Acceleration Support

GPU acceleration significantly improves Ollama inference speed. This guide supports both NVIDIA and AMD GPUs.

### **NVIDIA GPU Setup**

#### 1. Install NVIDIA Drivers and Container Toolkit

**Fedora/RHEL:**
```bash
# Install NVIDIA drivers
sudo dnf install akmod-nvidia xorg-x11-drv-nvidia-cuda

# Install container toolkit
sudo dnf install nvidia-container-toolkit

# Reboot to load drivers
sudo reboot
```

**Ubuntu/Debian:**
```bash
# Install NVIDIA drivers
sudo apt update
sudo apt install nvidia-driver-535 nvidia-utils-535

# Install container toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt update
sudo apt install nvidia-container-toolkit

# Reboot to load drivers
sudo reboot
```

#### 2. Configure Podman for NVIDIA GPU

```bash
# Configure runtime
sudo nvidia-ctk runtime configure --runtime=podman
sudo systemctl restart podman

# Test GPU access
nvidia-smi
podman run --rm --device nvidia.com/gpu=all nvidia/cuda:12.0-base-ubuntu20.04 nvidia-smi
```

#### 3. Deploy with NVIDIA GPU

```bash
# Auto-detect and use NVIDIA GPU
./quick-start-containers.sh

# Force NVIDIA GPU usage
./quick-start-containers.sh --gpu nvidia

# Check GPU usage
podman exec ollama nvidia-smi
```

### **AMD GPU Setup**

#### 1. Install AMD ROCm

**Fedora/RHEL:**
```bash
# Install ROCm
sudo dnf install rocm-dev rocm-smi

# Add user to render group
sudo usermod -a -G render $USER

# Reboot
sudo reboot
```

**Ubuntu/Debian:**
```bash
# Install ROCm
wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | sudo apt-key add -
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/debian/ ubuntu main' | sudo tee /etc/apt/sources.list.d/rocm.list
sudo apt update
sudo apt install rocm-dev rocm-smi

# Add user to render group
sudo usermod -a -G render $USER

# Reboot
sudo reboot
```

#### 2. Deploy with AMD GPU

```bash
# Auto-detect and use AMD GPU
./quick-start-containers.sh

# Force AMD GPU usage
./quick-start-containers.sh --gpu amd

# Check GPU usage
podman exec ollama rocm-smi
```

### **GPU Performance Comparison**

| GPU Type | Inference Speed | Memory Usage | Power Consumption |
|----------|----------------|--------------|-------------------|
| NVIDIA RTX 4090 | ~100 tokens/s | 8-12 GB | 200-300W |
| NVIDIA RTX 3080 | ~60 tokens/s | 6-10 GB | 150-200W |
| AMD RX 7900 XTX | ~40 tokens/s | 8-12 GB | 150-250W |
| CPU Only (16 cores) | ~5-10 tokens/s | 4-8 GB | 50-100W |

### **GPU Troubleshooting**

#### NVIDIA Issues

**Problem**: `nvidia-smi` not found
```bash
# Install drivers
sudo dnf install nvidia-driver nvidia-utils  # Fedora
sudo apt install nvidia-driver-535           # Ubuntu
```

**Problem**: Container can't access GPU
```bash
# Reconfigure runtime
sudo nvidia-ctk runtime configure --runtime=podman
sudo systemctl restart podman
```

**Problem**: Out of memory errors
```bash
# Use smaller model
./quick-start-containers.sh -m qwen3:4b

# Or check GPU memory
nvidia-smi
```

#### AMD Issues

**Problem**: No GPU devices found
```bash
# Check devices
ls -la /dev/dri/
# Should show renderD128, renderD129, etc.

# Check permissions
groups $USER
# Should include 'render' group
```

**Problem**: ROCm not detected
```bash
# Install ROCm
sudo dnf install rocm-dev rocm-smi
# or
sudo apt install rocm-dev rocm-smi
```

### **GPU Monitoring**

#### Real-time GPU monitoring:

**NVIDIA:**
```bash
# Watch GPU usage
watch -n 1 podman exec ollama nvidia-smi

# Detailed monitoring
podman exec ollama nvidia-smi -l 1
```

**AMD:**
```bash
# Watch GPU usage
watch -n 1 podman exec ollama rocm-smi

# Detailed monitoring
podman exec ollama rocm-smi -d
```

### **Performance Optimization**

#### Model Selection for GPU:

**High-end GPU (24GB+ VRAM):**
```bash
./quick-start-containers.sh -m llama3:70b
```

**Mid-range GPU (12-16GB VRAM):**
```bash
./quick-start-containers.sh -m llama3:13b
```

**Entry-level GPU (8GB VRAM):**
```bash
./quick-start-containers.sh -m llama3:8b
```

**Low VRAM (4-6GB):**
```bash
./quick-start-containers.sh -m qwen3:4b
```

## 📋 Requirements

- **System**: Linux (tested on Fedora, Ubuntu, RHEL)
- **Podman** 4.0+ (or Docker as alternative)
- **CPU**: 4+ cores recommended
- **RAM**: 8GB+ (16GB+ recommended)
- **Storage**: 20GB+ free space
- **GPU** (optional): NVIDIA RTX series or AMD RX series

## 🛠 Installation

### Install Podman

**Fedora/RHEL:**
```bash
sudo dnf install podman
```

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install podman
```

**macOS:**
```bash
brew install podman
podman machine init
podman machine start
```

**Verify installation:**
```bash
podman --version
```

## 🔧 Detailed Configuration

### Environment Variables

Create a `.env` file for container environment variables:

```bash
# Create .env file
cat > .env << EOF
# Ollama Configuration
OLLAMA_API_BASE=http://localhost:11434
OLLAMA_MODEL=qwen3:4b

# Application Configuration
LOG_LEVEL=INFO
PYTHONPATH=/app

# Optional: Google Gemini (alternative to Ollama)
# GOOGLE_GENAI_USE_VERTEXAI=FALSE
# GOOGLE_API_KEY=your_google_api_key_here

# Optional: Advanced Ollama settings
# OLLAMA_NUM_PARALLEL=1
# OLLAMA_MAX_LOADED_MODELS=1
# OLLAMA_ORIGINS=*
EOF
```

### Advanced Container Configuration

#### Using Docker Compose Format with Podman

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0:11434
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/version"]
      interval: 30s
      timeout: 10s
      retries: 3

  ci-analysis-agent:
    build: .
    container_name: ci-analysis-agent
    ports:
      - "8000:8000"
    depends_on:
      - ollama
    environment:
      - OLLAMA_API_BASE=http://ollama:11434
      - LOG_LEVEL=INFO
      - PYTHONPATH=/app
    volumes:
      - ./:/app/workspace:Z
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  ollama-data:
```

Run with podman-compose:
```bash
# Install podman-compose if not available
pip install podman-compose

# Start the stack
podman-compose up -d

# View logs
podman-compose logs -f

# Stop the stack
podman-compose down
```

#### Resource Limits

```bash
# Run with resource limits
podman run -d \
  --name ollama \
  --pod ci-analysis-pod \
  --memory=8g \
  --cpus=4 \
  --memory-swap=8g \
  -v ollama-data:/root/.ollama \
  -e OLLAMA_HOST=0.0.0.0:11434 \
  ollama/ollama:latest

podman run -d \
  --name ci-analysis-agent \
  --pod ci-analysis-pod \
  --memory=2g \
  --cpus=2 \
  -e OLLAMA_API_BASE=http://localhost:11434 \
  -v "$(pwd)":/app/workspace:Z \
  ci-analysis-agent:latest
```

## 🛠️ Container Management

### Starting and Stopping

#### Automated Container Management (Recommended)

```bash
# Stop containers using the script
./quick-start-containers.sh --stop

# Start containers (if already deployed)
podman start ollama ci-analysis-agent

# Or restart deployment from scratch
./quick-start-containers.sh

# Clean up and restart fresh
./quick-start-containers.sh --cleanup
```

#### Manual Container Management

```bash
# Start all containers in pod
podman pod start ci-analysis-pod

# Stop all containers in pod  
podman pod stop ci-analysis-pod

# Start individual containers
podman start ollama
podman start ci-analysis-agent

# Stop individual containers
podman stop ci-analysis-agent
podman stop ollama

# Restart containers
podman restart ollama
podman restart ci-analysis-agent
```

### Monitoring and Logs

```bash
# View container status
podman ps -a
podman pod ps

# View real-time logs
podman logs -f ci-analysis-agent
podman logs -f ollama

# View resource usage
podman stats

# Execute commands in running containers
podman exec -it ci-analysis-agent /bin/bash
podman exec -it ollama /bin/bash

# Check Ollama models
podman exec ollama ollama list

# Test Ollama API
podman exec ollama ollama run qwen3:4b "Hello, how are you?"
```

### Model Management

```bash
# Pull additional models
podman exec ollama ollama pull llama3:8b
podman exec ollama ollama pull codellama:7b

# Remove models to save space
podman exec ollama ollama rm qwen3:4b

# Check model sizes
podman exec ollama du -sh /root/.ollama/models/*

# Backup models
podman run --rm -v ollama-data:/source -v "$(pwd)":/backup alpine \
  tar czf /backup/ollama-models-backup.tar.gz -C /source .
```

## 🔍 Troubleshooting

### Common Issues

#### Container Startup Issues

```bash
# Check if containers are running
podman ps -a

# Check container logs for errors
podman logs ollama
podman logs ci-analysis-agent

# Check pod status
podman pod ps

# Inspect container configuration
podman inspect ollama
podman inspect ci-analysis-agent
```

#### Network Connectivity Issues

```bash
# Test Ollama connectivity from CI Analysis Agent
podman exec ci-analysis-agent curl -f http://localhost:11434/api/version

# Test from host system
curl -f http://localhost:11434/api/version

# Check port bindings
podman port ollama
podman port ci-analysis-agent

# List networks
podman network ls

# Inspect pod network
podman pod inspect ci-analysis-pod
```

#### Model Loading Issues

```bash
# Check available models
podman exec ollama ollama list

# Check model loading
podman exec ollama ollama ps

# Manually load model
podman exec ollama ollama run qwen3:4b "test"

# Check disk space
podman exec ollama df -h
```

#### Performance Issues

```bash
# Check resource usage
podman stats

# Check container resource limits
podman inspect ollama | jq '.[].HostConfig.Memory'
podman inspect ollama | jq '.[].HostConfig.CpuShares'

# Monitor system resources
top
htop
```

### SELinux Issues (Fedora/RHEL)

```bash
# If volume mounting fails due to SELinux
# Add :Z flag to volume mounts for automatic labeling
-v "$(pwd)":/app/workspace:Z

# Or set SELinux context manually
sudo semanage fcontext -a -t container_file_t "$(pwd)(/.)?"
sudo restorecon -R "$(pwd)"

# Disable SELinux temporarily (not recommended for production)
sudo setenforce 0
```

## 🧹 Cleanup

### Automated Cleanup (Recommended)

The `quick-start-containers.sh` script provides convenient cleanup options:

```bash
# Complete cleanup - removes everything (containers, volumes, images, pods)
./quick-start-containers.sh --clean-all

# Selective cleanup options
./quick-start-containers.sh --remove-volumes    # Only remove persistent volumes (loses model data)
./quick-start-containers.sh --remove-images     # Only remove container images (forces re-download)
./quick-start-containers.sh --remove-pods       # Only remove pods (for pod-based deployments)
```

**⚠️ Important Notes:**
- `--clean-all` removes **everything** including downloaded models
- `--remove-volumes` will delete all Ollama models (requires re-download)
- `--remove-images` will delete container images (requires re-download)
- Use selective options if you want to preserve certain resources

### Manual Cleanup

For more granular control, use manual podman commands:

```bash
# Stop and remove all containers in pod
podman pod stop ci-analysis-pod
podman pod rm ci-analysis-pod

# Or remove individual containers
podman stop ci-analysis-agent ollama
podman rm ci-analysis-agent ollama

# Remove images
podman rmi ci-analysis-agent:latest
podman rmi ollama/ollama:latest

# Remove volumes (WARNING: This deletes all model data)
podman volume rm ollama-data

# Remove all unused images, containers, and volumes
podman system prune -a --volumes
```

### Selective Cleanup

```bash
# Remove only stopped containers
podman container prune

# Remove only unused images
podman image prune

# Remove only unused volumes
podman volume prune

# Remove only unused networks
podman network prune
```

## 🔄 Updates and Maintenance

### Automated Updates (Recommended)

```bash
# Update the codebase
git pull origin main

# Clean up old containers and images
./quick-start-containers.sh --clean-all

# Deploy with latest code and images
./quick-start-containers.sh
```

### Manual Updates

```bash
# Pull latest images
podman pull ollama/ollama:latest

# Rebuild CI Analysis Agent
git pull origin main
podman build -t ci-analysis-agent:latest .

# Stop old containers
podman stop ci-analysis-agent ollama

# Remove old containers
podman rm ci-analysis-agent ollama

# Start new containers with same configuration
# (Use your preferred method from above)
```

### Maintenance Operations

```bash
# Regular maintenance - clean up unused resources
./quick-start-containers.sh --remove-images     # Remove old images
podman system prune -f                          # Clean up unused resources

# Model management
./quick-start-containers.sh --remove-volumes    # Remove models (if needed)
./quick-start-containers.sh --no-model          # Skip model download on restart

# Performance optimization
./quick-start-containers.sh --gpu nvidia        # Ensure GPU acceleration
./quick-start-containers.sh --cleanup           # Clean restart for performance
```

### Backup and Restore

```bash
# Backup Ollama models
podman run --rm \
  -v ollama-data:/source \
  -v "$(pwd)":/backup \
  alpine tar czf /backup/ollama-backup-$(date +%Y%m%d).tar.gz -C /source .

# Restore Ollama models
podman volume create ollama-data-restored
podman run --rm \
  -v ollama-data-restored:/target \
  -v "$(pwd)":/backup \
  alpine tar xzf /backup/ollama-backup-20240101.tar.gz -C /target

# Export container images
podman save -o ci-analysis-agent.tar ci-analysis-agent:latest
podman save -o ollama.tar ollama/ollama:latest

# Import container images
podman load -i ci-analysis-agent.tar
podman load -i ollama.tar
```

## 🎯 Production Considerations

### Security

```bash
# Run containers as non-root user
podman run --user 1001:1001 ...

# Use read-only root filesystem where possible
podman run --read-only ...

# Limit capabilities
podman run --cap-drop=ALL --cap-add=NET_BIND_SERVICE ...

# Use secrets for sensitive data
echo "secret-value" | podman secret create my-secret -
podman run --secret my-secret ...
```

### Monitoring

```bash
# Set up health checks in production
podman run -d \
  --health-cmd="curl -f http://localhost:11434/api/version || exit 1" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  ollama/ollama:latest

# Use systemd for auto-restart
podman generate systemd --new --name ollama > /etc/systemd/system/ollama.service
sudo systemctl enable --now ollama.service
```

### Performance Tuning

```bash
# Allocate more memory for better model performance
--memory=16g --memory-swap=16g

# Use more CPU cores
--cpus=8

# Use host networking for better performance (less secure)
--network=host

# Mount tmp filesystem for better I/O
--tmpfs /tmp:rw,noexec,nosuid,size=2g
```

## 📋 Quick Reference

### Script Command Summary

```bash
# Deployment
./quick-start-containers.sh                     # Start with auto GPU detection
./quick-start-containers.sh --gpu nvidia        # Force NVIDIA GPU
./quick-start-containers.sh --gpu amd           # Force AMD GPU
./quick-start-containers.sh --cpu-only          # Force CPU-only mode
./quick-start-containers.sh -m llama3:8b        # Use different model
./quick-start-containers.sh -p 3000             # Use different port

# Management
./quick-start-containers.sh --stop              # Stop running containers
./quick-start-containers.sh --cleanup           # Clean up before starting

# Cleanup
./quick-start-containers.sh --clean-all         # Remove everything
./quick-start-containers.sh --remove-volumes    # Remove persistent volumes only
./quick-start-containers.sh --remove-images     # Remove container images only
./quick-start-containers.sh --remove-pods       # Remove pods only

# Advanced
./quick-start-containers.sh --no-model          # Skip model download
./quick-start-containers.sh --help              # Show all options
```

### Common Workflows

```bash
# Fresh deployment
./quick-start-containers.sh

# Stop temporarily (preserves data)
./quick-start-containers.sh --stop
podman start ollama ci-analysis-agent           # Resume later

# Update deployment
git pull origin main
./quick-start-containers.sh --clean-all
./quick-start-containers.sh

# Switch models
./quick-start-containers.sh --remove-volumes
./quick-start-containers.sh -m llama3:8b

# Troubleshooting
./quick-start-containers.sh --cleanup           # Clean restart
./quick-start-containers.sh --cpu-only          # Disable GPU if issues
```

This containerized approach provides a clean, isolated environment for running the CI Analysis Agent with excellent portability and reproducibility across different systems. 