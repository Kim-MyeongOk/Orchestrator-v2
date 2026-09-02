# Quickstart

Source: https://docs.langchain.com/oss/python/deepagents/quickstart

## Local Usage Guidance
Use this page for the smallest runnable Deep Agents example.
The quickstart shows installing Deep Agents with a provider integration, importing `create_deep_agent`, defining a simple Python tool, constructing an agent with `model`, `tools`, and `system_prompt`, then invoking it with a `messages` input.
Read this before writing beginner examples, installation snippets, or minimal smoke tests.

## Extracted Documentation Content

### Key Sections
-  Prerequisites
-  Step 1: Install dependencies
-  Step 2: Set up your API keys
-  Step 3: Create a search tool
-  Step 4: Create a deep agent
-  Step 5: Set up LangSmith tracing
-  Step 6: Run the agent
-  How does it work?
-  Examples
-  Streaming

### Important Points
- Build your first deep agent in minutes
- Install the LangChain Docs MCP server to give your agent access to up-to-date LangChain documentation and examples.
- Install LangChain Skills to improve your agent’s performance on LangChain ecosystem tasks.
- Plans its approach using the built-in write_todos tool to break down the research task.
- Conducts research by calling the internet_search tool to gather information.
- Manages context by using file system tools ( write_file , read_file ) to offload large search results.
- Spawns subagents as needed to delegate complex subtasks to specialized subagents.
- Synthesizes a report to compile findings into a coherent response.
- Customize your agent : Learn about customization options , including custom system prompts, tools, and subagents.
- Add long-term memory : Enable persistent memory across conversations.
- Deploy to production : Use Managed Deep Agents to create, run, and operate deep agents in LangSmith.
- Test and evaluate : Use LangSmith evaluation to run automated tests and measure your agent’s performance against a dataset.

### API And Concept Signals
`Agents`, `Create`, `MCP`, `Skills`, `Streaming`, `TavilyClient`, `agent`, `agents`, `context`, `create`, `create_deep_agent`, `deepagents`, `file`, `invoke`, `memory`, `model`, `read_file`, `subagents`, `subtasks`, `task`, `tasks`, `tavily_client`, `tool`, `tools`, `write_file`, `write_todos`

### Representative Code Signals
```text
pip install deepagents tavily-python
```
```text
export GOOGLE_API_KEY = "your-api-key" export TAVILY_API_KEY = "your-tavily-api-key"
```
```text
export OPENAI_API_KEY = "your-api-key" export TAVILY_API_KEY = "your-tavily-api-key"
```
```text
export ANTHROPIC_API_KEY = "your-api-key" export TAVILY_API_KEY = "your-tavily-api-key"
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
