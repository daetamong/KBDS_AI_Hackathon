#!/bin/bash

echo "🚀 Setting up MCP Realtime Chainlit environment..."

# Install uv package manager
echo "📦 Installing uv package manager..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
uv sync

# Install Node.js dependencies if package.json exists
if [ -f "package.json" ]; then
    echo "📦 Installing Node.js dependencies..."
    npm install
fi

# Create .env file template if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env template..."
    cat > .env << 'EOF'
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_OPENAI_DEPLOYMENT=your_deployment_name_here

# Optional: Other environment variables
# Add your environment variables here
EOF
    echo "⚠️  Please update .env file with your Azure OpenAI credentials"
fi

echo "✅ Setup complete!"
echo ""
echo "To start the application, run:"
echo "  chainlit run chat.py -h -w --port 8000"
echo ""
echo "Don't forget to configure your .env file with Azure OpenAI credentials!"
