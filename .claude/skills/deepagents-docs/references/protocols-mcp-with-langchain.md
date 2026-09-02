# Model Context Protocol (MCP)

Source: https://docs.langchain.com/oss/python/langchain/mcp

## Local Usage Guidance
Use this page for Model Context Protocol integration through LangChain.
MCP lets agents connect to external tools, data sources, and services through a standard protocol. With Deep Agents, MCP tools are commonly routed through LangChain-compatible tool abstractions.
Read this when connecting MCP servers, selecting transports, converting tools, handling authentication, or passing context to external tools.

## Extracted Documentation Content

### Key Sections
-  Quickstart
-  Custom servers
-  Transports
-  HTTP
-  Passing headers
-  Authentication
-  stdio
-  Stateful sessions
-  Core features
-  Tools
-  Loading tools
-  Structured content
-  Multimodal tool content
-  Resources
-  Loading resources
-  Prompts
-  Loading prompts
-  Advanced features
-  Tool interceptors
-  Accessing runtime context

### Important Points
- Example custom auth implementation
- server_name : Name of the MCP server
- tool_name : Name of the tool being executed (available during tool calls)
- MCP Transport documentation

### Extracted Table/Field Signals
- Section
- Description
- Accessing runtime context
- Read user IDs, API keys, store data, and agent state
- State updates and commands
- Update agent state or control graph flow with Command
- Writing interceptors
- Patterns for modifying requests, composing interceptors, and error handling
- Action
- accept
- User provided valid input. Include the data in the content field.
- decline
- User chose not to provide the requested information.
- cancel
- User cancelled the operation entirely.

### API And Concept Signals
`AgentState`, `BaseModel`, `CallbackContext`, `Client`, `Context`, `Create`, `Created`, `FastMCP`, `InMemoryStore`, `Invoke`, `MCP`, `MCPToolCallRequest`, `Model`, `MultiServerMCPClient`, `Profile`, `Protocol`, `RequestContext`, `State`, `Stateful`, `Store`, `Tool`, `ToolMessage`, `Tools`, `access_multimodal_tool_content`, `agent`, `agents`, `ainvoke`, `client`

### Representative Code Signals
```text
pip install langchain-mcp-adapters
```
```text
import asyncio from langchain_mcp_adapters . client import MultiServerMCPClient from langchain . agents import create_agent async def main (): client = MultiServerMCPClient ( { "math" : { "transport" : "stdio" , # Local subprocess communication "command" : "python" , # Absolute path to your math_server.py file "args" : [ "/path/to/math_server.py" ], }, "weather" : { "transport" : "http" , # HTTP-based remote server # Ensure you start your weather server on port 8000 "url" : "http://localhost:8000/mcp" , } } ) tools = await client . get_tools () agent = create_agent ( "claude-sonnet-4-6" , tools ) math_response = await agent . ainvoke ( { "messages" : [{ "role" : "user" , "content" : "what's (3 + 5) x 12?" }]} ) weather_response = await agent . ainvoke ( { "messages" : [{ "role" : "user" , "content" : "what is the weather in nyc?" }]} ) print ( math_response ) print ( weather_response ) i
```
```text
pip install fastmcp
```
```text
from fastmcp import FastMCP mcp = FastMCP ( "Math" ) @mcp . tool () def add ( a : int , b : int ) -> int : """Add two numbers""" return a + b @mcp . tool () def multiply ( a : int , b : int ) -> int : """Multiply two numbers""" return a * b if __name__ == "__main__" : mcp . run ( transport = "stdio" )
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
