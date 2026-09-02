---
name: deepagents-docs
description: Use when answering questions, designing systems, or writing code with the Python deepagents package, including create_deep_agent, tools, context engineering, multimodality, backends, subagents, human-in-the-loop, permissions, memory, skills, sandboxes, interpreters, profiles, streaming, frontend patterns, deployment, ACP, MCP, A2A, and comparisons with Claude Agent SDK.
---

# Deep Agents Docs

Use this skill for Deep Agents work based on the official LangChain documentation. The files in `references/` are routing summaries for the docs pages; read the relevant files before answering detailed questions or writing code.

For exact API signatures, current model names, version-sensitive behavior, or production guidance, verify the linked official page before finalizing the answer.

## Workflow

1. Identify the user's topic: setup, customization, core capability, deployment, frontend, or protocol integration.
2. Read the matching reference file from the map below.
3. If the task spans topics, read the smallest set of reference files needed.
4. When writing examples, prefer concise Python examples using `create_deep_agent`.
5. Call out assumptions when the docs page is only a high-level overview or beta feature.

## Reference Map

| Topic | Read this file |
| --- | --- |
| Deep Agents overview and capability map | `references/overview.md` |
| First runnable agent | `references/get-started-quickstart.md` |
| Customizing agents | `references/get-started-customization.md` |
| Deep Agents versus Claude Agent SDK | `references/get-started-comparison-claude-agent-sdk.md` |
| Deep Agents Code | `references/get-started-deep-agents-code.md` |
| Release changes | `references/get-started-changelog.md` |
| Managed Deep Agents | `references/deployment-managed-deep-agents.md` |
| Production readiness | `references/deployment-going-to-production.md` |
| Model configuration | `references/core-models.md` |
| Tools and MCP tools | `references/core-tools.md` |
| Context management | `references/core-context-engineering.md` |
| Images, audio, video, documents | `references/core-multimodality.md` |
| Filesystem and storage backends | `references/core-backends.md` |
| Subagents | `references/core-subagents.md` |
| Async subagents | `references/core-async-subagents.md` |
| Human approval and interrupts | `references/core-human-in-the-loop.md` |
| Filesystem permission rules | `references/core-permissions.md` |
| Persistent memory | `references/core-memory.md` |
| Deep Agents skills | `references/core-skills.md` |
| Sandboxed execution | `references/core-sandboxes.md` |
| JavaScript interpreters | `references/core-interpreters.md` |
| Dynamic subagents | `references/core-dynamic-subagents.md` |
| Provider and harness profiles | `references/core-profiles.md` |
| Event stream projections | `references/core-event-streaming.md` |
| Standard streaming | `references/core-streaming.md` |
| Evaluation rubrics | `references/core-grading-rubrics.md` |
| Frontend overview | `references/frontend-overview.md` |
| Frontend subagent streaming | `references/frontend-subagent-streaming.md` |
| Frontend todo list pattern | `references/frontend-todo-list.md` |
| Frontend sandbox pattern | `references/frontend-sandbox.md` |
| Agent Client Protocol | `references/protocols-agent-client-protocol.md` |
| MCP with LangChain | `references/protocols-mcp-with-langchain.md` |
| A2A with LangSmith | `references/protocols-a2a-with-langsmith.md` |

## Topic Selection Hints

- For `create_deep_agent` basics, start with Quickstart, then Customization.
- For production services, read Going to production plus Backends, Permissions, Human-in-the-loop, and Streaming as needed.
- For user-specific authorization, read Tools, Permissions, MCP with LangChain, and Context engineering.
- For long-running or parallel tasks, read Subagents, Async subagents, Event streaming, and Frontend subagent streaming.
- For Claude-specific comparisons, read the comparison page and Models page, then verify current Anthropic model identifiers.
