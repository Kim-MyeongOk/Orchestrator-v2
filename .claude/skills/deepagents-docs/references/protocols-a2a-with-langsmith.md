# A2A endpoint in Agent Server

Source: https://docs.langchain.com/langsmith/server-a2a

## Local Usage Guidance
Use this page for agent-to-agent integration through LangSmith.
A2A is relevant when agents need to communicate with other agents or expose server-side agent capabilities through a standard integration pattern.
Read this when designing cross-agent workflows, external orchestration, or LangSmith-hosted agent interoperability.

## Extracted Documentation Content

### Key Sections
-  Supported methods
-  Agent card discovery
-  Requirements
-  Usage overview
-  Creating an A2A-compatible agent
-  Agent-to-agent communication
-  Distributed tracing
-  How contextId maps to thread_id
-  Tracing across multiple agents
-  Receive thread_id in non-LangGraph agents
-  View traces in LangSmith
-  Disable A2A

### Important Points
- Use the A2A protocol to enable agent-to-agent communication with distributed tracing in LangSmith.
- message/send : Send a message to an assistant and receive a complete response
- message/stream : Send a message and stream responses in real-time using Server-Sent Events (SSE)
- tasks/get : Retrieve the status and results of a previously created task
- Upgrade to use langgraph-api>=0.4.21.
- Deploy your agent with message-based state structure.
- Connect with other A2A-compatible agents using the endpoint.
- contextId : Groups messages into a conversation thread (like a session ID)
- taskId : Identifies each individual request within that conversation
- Two LangGraph agents communicating - Example of two LangGraph agents using the A2A protocol
- Google ADK agent with LangChain agent - Example of a Google ADK agent interacting with a LangChain agent using the A2A protocol
- On the first message, the client omits contextId . The server generates one and returns it in the response.
- The client passes the contextId in all subsequent messages to maintain conversation continuity.
- Agent Server maps the contextId to thread_id in LangSmith metadata , so all turns appear in the same thread.

### API And Concept Signals
`AGENT_A_ID`, `AGENT_B_ID`, `Agent`, `ClientSession`, `Context`, `Create`, `State`, `StateGraph`, `agent`, `agent_a_assistant_id`, `agent_a_id`, `agent_a_url`, `agent_b_assistant_id`, `agent_b_id`, `agent_b_url`, `agents`, `call_model`, `client`, `context`, `contextId`, `context_id`, `context_schema`, `create`, `created`, `downstream`, `middleware`, `model`, `protocol`

### Representative Code Signals
```text
GET /.well-known/agent-card.json?assistant_id={assistant_id}
```
```text
pip install "langgraph-api>=0.4.21"
```
```text
"""LangGraph A2A conversational agent. Supports the A2A protocol with messages input for conversational interactions. """ from __future__ import annotations import os from dataclasses import dataclass from typing import Any , Dict , List , TypedDict from langgraph . graph import StateGraph from langgraph . runtime import Runtime from openai import AsyncOpenAI class Context ( TypedDict ): """Context parameters for the agent.""" my_configurable_param : str @dataclass class State : """Input state for the agent. Defines the initial structure for A2A conversational messages. """ messages : List [ Dict [ str , Any ]] async def call_model ( state : State , runtime : Runtime [ Context ]) -> Dict [ str , Any ]: """Process conversational messages and returns output using OpenAI.""" # Initialize OpenAI client client = AsyncOpenAI ( api_key = os . getenv ( "OPENAI_API_KEY" )) # Process the incoming 
```
```text
#!/usr/bin/env python3 """Agent-to-Agent conversation simulation using the LangGraph A2A endpoint.""" import asyncio import aiohttp import os import uuid def extract_text ( result : dict ) -> str : """Best-effort extraction of response text from an A2A result.""" for art in result . get ( "result" , {}). get ( "artifacts" , []) or []: for part in art . get ( "parts" , []) or []: if part . get ( "kind" ) == "text" and part . get ( "text" ): return part [ " text " ] msg = ( result . get ( "result" , {}). get ( "status" , {}) or {}). get ( "message" , {}) or {} for part in msg . get ( "parts" , []) or []: if part . get ( "kind" ) == "text" and part . get ( "text" ): return part [ " text " ] return "(no text found)" async def send_message ( session , port , assistant_id , text , context_id = None , task_id = None ): """Send an A2A message. Returns (response_text, returned_context_id, returne
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
