# MCP Realtime Airbnb Chatbot

This project implements a real-time chatbot that provides Airbnb information using Model Context Protocol (MCP) and OpenAI's realtime API. The chatbot supports both text and audio interactions through a Chainlit web interface.

## Features

- **Multi-modal Interaction**: Support for both text input and voice conversations
- **Real-time Audio Processing**: Audio streaming for natural conversation flow
- **Model Context Protocol (MCP) Integration**: Connects to external MCP services for Airbnb data
- **Internationalization**: Supports multiple languages (currently English and Korean)
- **Azure OpenAI Integration**: Uses Azure OpenAI's Realtime API for streaming responses

## Architecture

The project consists of three main components:

1. **MCP Service**: Manages connection to MCP servers that provide Airbnb data
2. **Realtime Client**: Handles WebSocket communication with OpenAI's realtime API
3. **Chainlit Interface**: Provides the user-facing chat interface with audio support

## Prerequisites

- Python 3.11+
- Node.js and npm (for the MCP server)
- uv package manager for Python
- Azure OpenAI API access with realtime capabilities

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd mcp-realtime-chainlit
   ```

2. Install Python dependencies using uv (modern Python package manager):
   ```bash
   uv sync
   ```
   
   Note: If you don't have uv installed, install it first:
   ```bash
   curl -sSf https://install.ultraviolet.rs | sh
   ```

3. Create a `.env` file with your Azure OpenAI credentials:
   ```
   AZURE_OPENAI_API_KEY=your_api_key
   AZURE_OPENAI_ENDPOINT=your_endpoint
   AZURE_OPENAI_DEPLOYMENT=your_deployment_name
   ```

## Usage

Start the application:

```bash
chainlit run chat.py
```

This will launch the Chainlit web interface, typically accessible at http://localhost:8000.

### Interacting with the Chatbot

- **Text Mode**: Type questions about Airbnb listings, pricing, locations, etc.
- **Voice Mode**: Click the microphone button to start speaking, and the system will process your audio input

## Project Structure

- `mcp_service.py`: Implements the MCP service client for communicating with MCP servers
- `realtime.py`: Manages WebSocket connections to the OpenAI realtime API
- `chat.py`: Chainlit interface implementation with handlers for text and audio
- `chainlit_config.py`: Configuration for internationalization
- `locales/`: Translation files for different languages

## How It Works

1. The Chainlit application starts and establishes a connection to Azure OpenAI's realtime API
2. The MCP service initializes and connects to the Airbnb MCP server
3. When a user sends a message (text or audio):
   - If text: The message is sent directly to the model
   - If audio: The audio is streamed to the model for real-time transcription
4. The model processes the input with access to Airbnb data through MCP tools
5. Responses are streamed back to the user (text and/or audio)

## Development

### Adding New MCP Tools

To add a new MCP server:

1. Add the server configuration to the `MCPService.initialize()` method
2. Install the required npm package for the MCP server
## License

MIT License (MIT)
## Acknowledgements

- This project uses the [Chainlit](https://github.com/Chainlit/chainlit) framework for the chat interface
- The realtime streaming implementation is derived from [openai-realtime-console](https://github.com/openai/openai-realtime-console)
- Airbnb data is provided through [@openbnb/mcp-server-airbnb](https://www.npmjs.com/package/@openbnb/mcp-server-airbnb)
