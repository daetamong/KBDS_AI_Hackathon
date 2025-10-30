# GitHub Codespaces Configuration

This directory contains the configuration for running this project in GitHub Codespaces.

## What's Included

- **Python 3.12**: Pre-configured Python environment
- **Node.js LTS**: For running MCP servers
- **uv Package Manager**: Modern Python package manager for fast dependency installation
- **VS Code Extensions**: Python, Pylance, Ruff formatter, and Jupyter support
- **Port Forwarding**: Port 8000 is automatically forwarded for the Chainlit application

## Getting Started

1. Open this repository in GitHub Codespaces
2. Wait for the container to build and dependencies to install
3. Configure your `.env` file with Azure OpenAI credentials:
   ```bash
   AZURE_OPENAI_API_KEY=your_api_key_here
   AZURE_OPENAI_ENDPOINT=your_endpoint_here
   AZURE_OPENAI_DEPLOYMENT=your_deployment_name_here
   ```
4. Start the application:
   ```bash
   chainlit run chat.py -h -w --port 8000
   ```
5. Click on the "Ports" tab and open the forwarded port 8000 in your browser

## Manual Setup

If you need to reinstall dependencies:

```bash
# Python dependencies
uv sync

# Node.js dependencies (if needed)
npm install
```

## Troubleshooting

- **Port already in use**: Make sure no other process is using port 8000
- **Dependencies not installed**: Run `bash .devcontainer/setup.sh` manually
- **uv not found**: Restart your terminal or run `source ~/.bashrc`
