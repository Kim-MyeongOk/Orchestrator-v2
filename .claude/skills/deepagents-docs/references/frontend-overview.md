# Overview

Source: https://docs.langchain.com/oss/python/deepagents/frontend/overview

## Local Usage Guidance
Use this page when building a frontend around Deep Agents.
The frontend overview explains how UI applications can represent agent runs, messages, tools, subagents, todos, files, and sandbox output. It connects backend event streams to user-facing interaction patterns.
Read this before designing a web UI or dashboard for a Deep Agents application.

## Extracted Documentation Content

### Key Sections
-  Architecture
-  What the SDK exposes
-  Patterns
- Subagent streaming
- Todo list
- Sandbox
-  Related patterns

### Important Points
- Build UIs that display real-time subagent streams, task progress, and sandbox for Deep Agents

### Extracted Table/Field Signals
- Projection
- Use it for
- stream.messages
- The coordinator conversation and final synthesis.
- stream.subagents
- Live discovery of specialist workers, including status and task metadata.
- stream.values
- Shared state such as todos, plans, report sections, sandbox metadata, or any custom key your agent writes.
- Tool-call state
- Rendering filesystem, search, browser, or domain tools as cards with progress and results.
- Interrupts
- Pausing delegated work for user approval or missing input without losing the run state.

### API And Concept Signals
`Agents`, `Interrupts`, `Sandbox`, `Subagent`, `Todo`, `Tool`, `agent`, `create_deep_agent`, `deepagents`, `filesystem`, `model`, `sandbox`, `state`, `stream`, `streaming`, `streams`, `subagent`, `subagents`, `task`, `todos`, `tools`, `useStream`

### Representative Code Signals
```text
from deepagents import create_deep_agent agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , tools = [ get_weather ], system_prompt = "You are a helpful assistant" , subagents = [ { "name" : "researcher" , "description" : "Research assistant" , } ], )
```
```text
import { useStream } from "@langchain/react" ; function App () { const stream = useStream < typeof agent > ( { apiUrl : "http://localhost:2024" , assistantId : "agent" , } ) ; // Deep agent state beyond messages const todos = stream . values ?. todos ; const subagents = [ ... stream . subagents . values ()] ; }
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
