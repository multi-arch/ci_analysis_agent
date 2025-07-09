# Use Python 3.13 base image
FROM python:3.13-slim

# Create non-root user for OpenShift compatibility
RUN groupadd -r appuser -g 1001 && \
    useradd -r -g appuser -u 1001 -m -d /app appuser

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Change ownership to appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER 1001

# Set environment variables
ENV PYTHONPATH=/app
ENV OLLAMA_API_BASE=http://ollama-service:11434

# Expose port for ADK web server
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Run the agent
CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8000"] 