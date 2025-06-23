# CI Analysis Agent

## What is it?

This tool is experimentation to find root cause analysis for multi-arch release test failures.

## How to use

1. [Install ADK](https://google.github.io/adk-docs/get-started/installation/)
2. If you intend to use local models with LiteLLM, install ollama
3. run `adk web` from the parent folder of ci_analysis_agent

PS: If you're using Gemini (not a local model), create a .env file with content:
```
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY={{YOUR_TOKEN_HERE}}
```