# Deep Agents Code

Source: https://docs.langchain.com/oss/python/deepagents/code/overview

## Local Usage Guidance
Use this page for the Deep Agents Code product or coding-agent experience built around Deep Agents.
Read this when the request mentions Deep Agents Code specifically.

## Extracted Documentation Content

### Key Sections
-  Quickstart
-  Capabilities
-  Built-in tools
-  Command reference
-  Configuration
-  Interactive mode
-  Non-interactive mode and piping
-  Trace with LangSmith

### Important Points
- Terminal coding agent built on the Deep Agents SDK
- File operations - read, write, and edit files on disk.
- Shell execution - execute commands to run tests, build projects, manage dependencies, and interact with version control.
- Remote sandboxes - run agent tools remotely instead of on your local machine.
- Web search - search the web for up-to-date information and documentation. Requires a Tavily API key .
- Task planning and tracking - break down complex tasks into discrete steps and track progress.
- Goals and rubrics - define measurable objectives or grading criteria so the agent can check whether work is done.
- Subagents - delegate work to task-specific subagents.
- Memory storage and retrieval - store and retrieve information across sessions, enabling agents to remember project conventions and learned patterns.
- Context compaction & offloading - summarize older conversation messages and offload originals to storage.
- Human-in-the-loop - require human approval for sensitive tool operations.
- Skills - extend agent capabilities with custom expertise and instructions.
- MCP tools - load external tools from Model Context Protocol servers.
- Tracing - trace agent operations in LangSmith for observability and debugging.
- Full list of built-in tools
- /model : Switch models or open the interactive model selector.
- /effort : Set reasoning effort for the current model.
- /agents : Hot-swap between pre-configured agents without relaunching. See Command reference for details.

### Extracted Table/Field Signals
- Tool
- Description
- Human-in-the-Loop
- List files and directories
- read_file
- Read contents of a file; returns multimodal blocks for images, audio, video, and PDFs
- write_file
- Create or overwrite a file
- Required 1
- edit_file
- Make targeted edits to existing files
- delete
- Delete a file or directory recursively
- glob
- Find files matching a pattern
- grep
- Search for text patterns across files
- execute
- Execute shell commands locally or in a remote sandbox
- web_search
- Search the web using Tavily (see Enable web search )
- fetch_url
- Fetch and convert web pages to markdown
- task

### API And Concept Signals
`Agent`, `AgentCore`, `Agents`, `Context`, `Create`, `DEEPAGENTS_CODE_`, `DEEPAGENTS_CODE_LANGSMITH_PROJECT`, `DEEPAGENTS_CODE_LANGSMITH_REPLICA_PROJECTS`, `File`, `Interrupt`, `Invoke`, `MCP`, `MODEL`, `Memory`, `Model`, `Profiles`, `Protocol`, `SKILL`, `Sandbox`, `Skills`, `Store`, `Subagents`, `Task`, `Tool`, `agent`, `agent_name`, `agentcore`, `agentic`

### Representative Code Signals
```text
curl -LsSf https://langch.in/dcode | bash
```
```text
dcode --model anthropic:claude-opus-4-8 dcode --model openai:gpt-5.5 dcode --model fireworks:accounts/fireworks/models/deepseek-v4-pro dcode --model baseten:moonshotai/Kimi-K2.7-Code
```
```text
Create a Python script that prints "Hello, World!"
```
```text
LANGSMITH_TRACING = true LANGSMITH_API_KEY = lsv2_... LANGSMITH_PROJECT = optional-project-name # Specify a project name or default to "deepagents-code"
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
