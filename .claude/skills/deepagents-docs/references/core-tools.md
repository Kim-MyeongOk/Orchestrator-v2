# Tools

Source: https://docs.langchain.com/oss/python/deepagents/tools

## Local Usage Guidance
Use this page when defining or wiring tools into a Deep Agent.
The tools page covers Python functions, LangChain tools, model-visible tool descriptions, MCP tools, built-in filesystem tools, and how tools fit into the Deep Agents harness.
Read this for tool design, tool naming, tool argument schemas, MCP tool integration, and debugging tool-calling behavior.

## Extracted Documentation Content

### Key Sections
-  Custom tools
-  MCP tools
-  Built-in harness tools
-  Multimodal tool outputs

### Important Points
- Connect Deep Agents to custom functions, APIs, databases, and any MCP server

### Extracted Table/Field Signals
- Tool
- Description
- List files in a directory
- read_file
- Read file contents (with pagination and multimodal support)
- write_file
- Create new files
- edit_file
- Perform exact string replacements in files
- glob
- Find files matching a glob pattern
- grep
- Search file contents
- execute
- Run shell commands (sandbox backends only)
- task
- Spawn a subagent to handle a delegated task
- write_todos
- Manage a structured todo list

### API And Concept Signals
`Agents`, `Create`, `MCP`, `MultiServerMCPClient`, `TavilyClient`, `Tool`, `Tools`, `agent`, `ainvoke`, `backends`, `client`, `create_deep_agent`, `deepagents`, `edit_file`, `file`, `files`, `get_tools`, `langchain_mcp_adapters`, `mcp`, `model`, `read_file`, `sandbox`, `subagent`, `task`, `tavily_client`, `todo`, `tool`, `tools`

### Representative Code Signals
```text
from deepagents import create_deep_agent agent = create_deep_agent ( model = "anthropic:claude-sonnet-4-6" , tools = [ search , fetch_url , run_query ], )
```
```text
import os from typing import Literal from tavily import TavilyClient from deepagents import create_deep_agent tavily_client = TavilyClient ( api_key = os . environ [ " TAVILY_API_KEY " ]) def internet_search ( query : str , max_results : int = 5 , topic : Literal [ " general " , " news " , " finance " ] = "general" , include_raw_content : bool = False , ): """Run a web search""" return tavily_client . search ( query , max_results = max_results , include_raw_content = include_raw_content , topic = topic , ) agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , tools = [ internet_search ], )
```
```text
pip install langchain-mcp-adapters
```
```text
import asyncio from langchain_mcp_adapters . client import MultiServerMCPClient from deepagents import create_deep_agent async def main (): client = MultiServerMCPClient ( { "my_server" : { "transport" : "http" , "url" : "http://localhost:8000/mcp" , } } ) tools = await client . get_tools () agent = create_deep_agent ( model = "openai:gpt-5.5" , tools = tools , ) result = await agent . ainvoke ( { "messages" : [{ "role" : "user" , "content" : "Use the MCP server to help me." }]}, config = { "configurable" : { "thread_id" : "1" }}, ) asyncio . run ( main ())
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
