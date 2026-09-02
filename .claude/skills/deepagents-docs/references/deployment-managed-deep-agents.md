# Managed Deep Agents

Source: https://docs.langchain.com/langsmith/managed-deep-agents-overview

## Local Usage Guidance
Use this page when the user asks about LangSmith-hosted or managed Deep Agents.
Managed Deep Agents concerns deployment and operations through LangSmith rather than only local Python package usage. It is relevant for hosted runtimes, management UI, observability, deployment lifecycle, and operational controls.
Read this before recommending a managed deployment path.

## Extracted Documentation Content

### Key Sections
-  Follow the workflow
- Quickstart
- Connect tools
- Deploy an agent
- Run an agent
- SDKs
- CLI reference
- API reference
-  Use Managed Deep Agents
-  Created resources
-  LangSmith sandbox backends
-  Limits and notes
-  Stable deploy experience
-  Supported models
-  Thread retention
-  Rate limits and quotas
-  Agent limits
-  Delete agents
-  API stability
-  Support and feedback

### Important Points
- Overview of Managed Deep Agents private beta features, workflows, and limits.
- Create or edit a local Managed Deep Agents project.
- Keep the default backend or opt into a LangSmith sandbox backend.
- Connect MCP tools when the agent needs external capabilities.
- Deploy the project to Managed Deep Agents.
- Run the agent with the Python or TypeScript SDK.
- Inspect traces, files, tool calls, runtime state, and revisions in LangSmith.
- Create and manage deep agents from local project files.
- Run long-running agents without standing up a custom agent server.
- Give each thread or agent isolated LangSmith sandbox resources for code execution, filesystem work, and long-running tasks.
- Stream runs and persist thread state.
- Use a managed file tree for instructions, skills, subagents, tools, and runtime files.
- Register workspace-level MCP servers, including OAuth MCP servers, and list their available tools.
- Inspect traces and agent behavior in LangSmith.
- A Managed Deep Agent resource.
- A separate LangSmith tracing project for the agent.
- A Context Hub agent repo that stores the managed file tree.
- state : applies no sandbox-specific backend behavior.

### API And Concept Signals
`Agent`, `Agents`, `Context`, `Create`, `Created`, `MCP`, `Stream`, `agent`, `agents`, `backend`, `backends`, `file`, `files`, `filesystem`, `models`, `sandbox`, `sandbox_config`, `skills`, `state`, `stores`, `subagents`, `tasks`, `tool`, `tools`

### Representative Code Signals
```text
{ " backend " : { " type " : "state" } }
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
