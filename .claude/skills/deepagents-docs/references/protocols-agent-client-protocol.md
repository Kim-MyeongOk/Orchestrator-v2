# Agent Client Protocol (ACP)

Source: https://docs.langchain.com/oss/python/deepagents/acp

## Local Usage Guidance
Use this page for ACP integration.
Agent Client Protocol defines a client-facing protocol shape for communicating with agents. It is relevant when standardizing how external clients send messages, receive events, and manage agent sessions.
Read this when integrating Deep Agents with a frontend, external client, or protocol-compatible runtime.

## Extracted Documentation Content

### Key Sections
-  Quickstart
- Example coding agent
-  Clients
-  Zed
-  Toad

### Important Points
- Expose Deep Agents over the Agent Client Protocol (ACP) to integrate with code editors and IDEs.
- Visual Studio Code (via vscode-acp )
- Neovim (via ACP-compatible plugins)
- Clone the deepagents repo and install dependencies:
- Configure credentials for the demo agent:
- Configure your ACP agent server command in Zed’s settings.json :
- Open Zed’s Agents panel and start a Deep Agents thread.
- Introduction: https://agentclientprotocol.com/get-started/introduction
- Clients/editors: https://agentclientprotocol.com/get-started/clients

### API And Concept Signals
`Agent`, `AgentServerACP`, `Agents`, `Client`, `Clients`, `DeepAgents`, `MemorySaver`, `Protocol`, `agent`, `agent_servers`, `agentclientprotocol`, `clients`, `create_deep_agent`, `deepagents`, `deepagents_acp`, `memory`, `middleware`, `model`, `run_agent`, `run_demo_agent`, `subagents`, `tool`, `tools`

### Representative Code Signals
```text
pip install deepagents-acp
```
```text
import asyncio from acp import run_agent from deepagents import create_deep_agent from langgraph . checkpoint . memory import MemorySaver from deepagents_acp . server import AgentServerACP async def main () -> None : agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , # You can customize your deep agent here: set a custom prompt, # add your own tools, attach middleware, or compose subagents. system_prompt = "You are a helpful coding assistant" , checkpointer = MemorySaver (), ) server = AgentServerACP ( agent ) await run_agent ( server ) if __name__ == "__main__" : asyncio . run ( main ())
```
```text
git clone https://github.com/langchain-ai/deepagents.git cd deepagents/libs/acp uv sync --all-groups chmod +x run_demo_agent.sh
```
```text
cp .env.example .env
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
