# Comparison with Claude Agent SDK

Source: https://docs.langchain.com/oss/python/deepagents/comparison

## Local Usage Guidance
Use this page when comparing Deep Agents with Anthropic's Claude Agent SDK.
This page is useful for tradeoff analysis: framework scope, model/provider flexibility, built-in harness features, file access, tool execution, subagents, memory, skills, streaming, and deployment patterns.
Read this before answering "which should I use?" or before porting a Claude Agent SDK design to Deep Agents.

## Extracted Documentation Content

### Key Sections
-  At a glance
-  Main differences
-  Agent and execution environment
-  Multi-tenancy
-  A production agent server
-  Managed cloud or self-hosted
-  LLM
-  Ecosystems
-  Summary

### Important Points
- Compare LangChain Deep Agents with the Claude Agent SDK to choose the right tool for your use case.
- Run the agent inside a sandbox (same model as Claude Agent SDK).
- Run the agent in a long-lived container and use a remote sandbox as a tool , executing commands over the network.
- Swap in a virtual filesystem for tests, or a custom backend for your own infrastructure.
- Managed: create, run, and operate deep agents with Managed Deep Agents in LangSmith.
- Self-hosted: run langgraph build to produce a standalone Docker image you can deploy anywhere.
- Choose Deep Agents if you want model and infrastructure flexibility, built-in multi-tenant deployment, and the option to run managed or self-hosted without code changes.
- Choose Claude Agent SDK if you are already invested in the Anthropic ecosystem and wish to self-host and build the API, auth, and multi-tenant layers yourself.

### Extracted Table/Field Signals
- Deep Agents
- Claude Agent SDK
- Where the agent runs
- Inside a sandbox, or outside a sandbox executing commands remotely
- Inside a sandbox
- Execution backend
- Pluggable: local, virtual filesystem, remote sandbox, or custom
- Local filesystem of the sandbox it runs in
- Model provider
- Any (Anthropic, OpenAI, Google, 100+ others)
- Claude (Anthropic, Bedrock, Vertex, Azure)
- Per-provider/model tuning
- Harness profiles (beta): declarative bundles of system prompt, tool, middleware, and subagent tweaks, registered per provider or specific model
- Configure in code at each model call site
- Deployment
- Managed Deep Agents in LangSmith, or self-host a standalone image via langgraph build
- Self-host . You build the server, auth, and streaming layer. Claude managed agents is a separate product
- Multi-tenancy
- Built-in : scoped threads, per-user sandboxes, RBAC
- Build it yourself
- License
- MIT
- MIT (Claude Code itself is proprietary)

### API And Concept Signals
`Agent`, `Agents`, `Model`, `agent`, `agents`, `backend`, `create`, `filesystem`, `middleware`, `model`, `profiles`, `sandbox`, `sandboxes`, `streaming`, `subagent`, `tool`

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
