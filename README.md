# CI Analysis Agent

## What is it?

This tool is experimentation to find root cause analysis for multi-arch release test failures. It uses Google's Agent Development Kit (ADK) with local LLM models via Ollama to analyze CI/CD pipeline failures and provide intelligent insights.

## Prerequisites

Before getting started, ensure you have the following installed:

### Required Software
- **Python 3.11+** (recommended 3.13)
- **Git** for version control
- **Ollama** for local LLM models
- **Docker/Podman** for containerization
- **Node.js 18+** (for ADK web interface)

### System Requirements
- **RAM**: 8GB minimum, 16GB recommended (for running local LLM models)
- **Storage**: 10GB free space (for models and dependencies)
- **OS**: Linux (recommended), macOS, or Windows with WSL2

## Getting Started

### 1. Clone the Repository

```bash
# Clone your fork
git clone git@github.com:jeffdyoung/ci_analysis_agent.git
cd ci_analysis_agent

# Add upstream remote (optional, for contributing)
git remote add upstream git@github.com:sherine-k/ci_analysis_agent.git
```

### 2. Install Dependencies

#### Install Python Dependencies
```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python packages
pip install -r requirements.txt

# If requirements.txt doesn't exist, install core dependencies:
pip install google-adk litellm drain3 google-cloud-storage python-dotenv
```

#### Install Ollama
```bash
# On Linux/macOS
curl -fsSL https://ollama.com/install.sh | sh

# On Windows (PowerShell)
# Download from https://ollama.com/download/windows

# Start Ollama service
ollama serve
```

#### Install ADK (Agent Development Kit)
```bash
# Install ADK globally
npm install -g @google/adk

# Or install locally
npm install @google/adk
```

### 3. Setup Local LLM Model

```bash
# Pull the qwen3:4b model (recommended)
ollama pull qwen3:4b

# Verify model is available
ollama list

# Test the model (optional)
ollama run qwen3:4b "Hello, how are you?"
```

### 4. Environment Configuration

Create a `.env` file in the project root:

```bash
# For local Ollama models (default)
OLLAMA_API_BASE=http://localhost:11434

# For Google Gemini (alternative)
# GOOGLE_GENAI_USE_VERTEXAI=FALSE
# GOOGLE_API_KEY=your_google_api_key_here

# Optional: Logging level
LOG_LEVEL=INFO
```

### 5. Build the Prow MCP Server

```bash
# Navigate to the prow_mcp_server directory
cd prow_mcp_server

# Build the container image
podman build -t mcp-server-template:latest .
# Or with Docker:
# docker build -t mcp-server-template:latest .

# Return to project root
cd ..
```

### 6. Run the Application

#### Option A: Using ADK Web Interface (Recommended)
```bash
# Start the web interface
adk web

# Open your browser to http://localhost:3000
# Select "CI Analysis Agent" from the available agents
```

#### Option B: Command Line Interface
```bash
# Run the agent directly
python agent.py

# Or run specific sub-agents
python sub_agents/installation_analyst/agent.py
python sub_agents/mustgather_analyst/agent.py
```

#### Option C: Development Mode
```bash
# Run with auto-reload for development
adk dev

# Or use Python's development server
python -m adk.cli dev
```

## Configuration Options

### Model Configuration
Edit `agent.py` to change the model:
```python
# For local Ollama models
MODEL = LiteLlm(model="ollama_chat/qwen3:4b")

# For other Ollama models
MODEL = LiteLlm(model="ollama_chat/llama3:8b")
MODEL = LiteLlm(model="ollama_chat/codellama:7b")

# For Google Gemini
MODEL = LiteLlm(model="gemini/gemini-1.5-flash")
```

### Log Analysis Configuration
The system uses Drain3 for log pattern detection. Configure in `drain3.ini`:
```ini
[DRAIN]
sim_th = 0.4
depth = 4
max_children = 100
max_clusters = 1000
```

## Usage Examples

### Analyzing CI Failures
1. Upload your CI logs or must-gather files
2. The agent will automatically:
   - Parse and categorize logs
   - Identify failure patterns
   - Provide root cause analysis
   - Suggest remediation steps

### Supported Input Types
- **Prow job logs**
- **OpenShift must-gather archives**
- **Installation logs**
- **Test execution reports**

## Troubleshooting

### Common Issues

#### "Model not found" Error
```bash
# Check if Ollama is running
ollama list

# If model missing, pull it
ollama pull qwen3:4b

# Verify environment variable
echo $OLLAMA_API_BASE
```

#### "Connection refused" Error
```bash
# Start Ollama service
ollama serve

# Check if port 11434 is available
netstat -tlnp | grep 11434
```

#### ADK Web Interface Issues
```bash
# Clear ADK cache
adk cache clear

# Reinstall ADK
npm uninstall -g @google/adk
npm install -g @google/adk
```

#### Python Import Errors
```bash
# Activate virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

### Performance Tips
- Use smaller models (qwen3:4b) for faster responses
- Increase system RAM for better model performance
- Use SSD storage for faster model loading
- Monitor system resources during analysis

## Development

### Project Structure
```
ci_analysis_agent/
├── agent.py                 # Main agent implementation
├── prompt.py               # Agent prompts and instructions
├── sub_agents/             # Specialized analysis agents
│   ├── installation_analyst/
│   └── mustgather_analyst/
├── prow_mcp_server/        # MCP server for Prow integration
├── deploy/                 # Deployment configurations
└── requirements.txt        # Python dependencies
```

### Adding New Features
1. Create a new sub-agent in `sub_agents/`
2. Update the main agent to include the new functionality
3. Add appropriate prompts and instructions
4. Test with sample data

### Contributing
1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Submit a pull request to the upstream repository

## Deployment

For production deployment on Kubernetes or OpenShift clusters, see the [`deploy/`](deploy/) directory:

- **Kubernetes**: `./deploy/deploy.sh`
- **OpenShift 4.19+**: `./deploy/deploy-openshift.sh`

Full documentation: [KUBERNETES.md](KUBERNETES.md)

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Search existing issues in the repository
3. Create a new issue with detailed information
4. Include system information and error logs

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## 🚀 Multi-User Tekton Pipeline Suite

### Files Created:
- **`deploy/tekton/pipeline.yaml`** - Main pipeline definition with 7 stages (multi-user)
- **`deploy/tekton/tasks.yaml`** - Custom tasks for deployment operations (multi-user)
- **`deploy/tekton/rbac.yaml`** - Service account and RBAC permissions
- **`deploy/tekton/pipeline-run.yaml`** - Example pipeline run configuration
- **`deploy/tekton/triggers.yaml`** - Automated GitHub webhook triggers (multi-user)
- **`deploy/tekton/deploy-pipeline.sh`** - Automated deployment script
- **`deploy/tekton/user-examples.yaml`** - Multi-user deployment examples
- **`deploy/tekton/README.md`** - Comprehensive documentation

### Pipeline Flow:
1. **Git Clone** - Fetches source code from any GitHub repository
2. **Create Namespace** - Sets up user-specific namespaces (`ci-analysis-<username>`)
3. **Build Image** - Builds container image using Buildah (user-tagged)
4. **Deploy Ollama** - Deploys Ollama with persistent storage (per user)
5. **Deploy CI Analysis Agent** - Deploys the main application (per user)
6. **Load Model** - Loads the qwen3:4b model into Ollama
7. **Create Route** - Exposes the application via OpenShift Route (per user)

### Key Features:
- ✅ **Multi-User Support** - Multiple developers on single cluster
- ✅ **Namespace Isolation** - Each user gets their own namespace
- ✅ **Resource Prefixing** - All resources prefixed with user identifier
- ✅ **OpenShift 4.19+ Compatible** - Full security contexts and RBAC
- ✅ **Automated Triggers** - GitHub webhook integration for auto-deployment
- ✅ **Persistent Storage** - Ollama model storage across deployments
- ✅ **Security Hardened** - Non-root containers, minimal permissions
- ✅ **Comprehensive Monitoring** - Full logging and status tracking
- ✅ **Registry Integration** - Supports any container registry (Quay.io default)

### Quick Start:
```bash
# Navigate to tekton directory
cd deploy/tekton

# Deploy all pipeline resources
./deploy-pipeline.sh

# Create registry secret
oc create secret docker-registry docker-registry-secret \
  --docker-server=quay.io \
  --docker-username=<your-username> \
  --docker-password=<your-password> \
  --docker-email=<your-email> \
  -n tekton-pipelines

# Deploy for user "alice"
./deploy-user.sh alice https://github.com/alice/ci_analysis_agent.git feature/new-analysis alice

# Monitor progress
tkn pipelinerun logs --last -f -n tekton-pipelines
```

### Multi-User Deployment:
The pipeline supports multiple users deploying to isolated namespaces. Each user gets their own:
- **Namespace**: `ci-analysis-<username>`
- **Resources**: Prefixed with username (e.g., `alice-ollama`, `bob-ci-analysis-agent`)
- **Routes**: Individual URLs for each deployment
- **Storage**: Isolated persistent volumes

### Automated Deployment:
The pipeline supports GitHub webhooks for automatic deployment on code pushes from any repository. The webhook endpoint automatically creates user-specific deployments based on the repository owner.

The pipeline is production-ready and includes comprehensive error handling, security best practices, and detailed documentation. Perfect for development teams working on the same codebase with different features or environments.