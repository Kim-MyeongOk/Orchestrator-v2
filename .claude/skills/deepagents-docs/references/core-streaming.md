# Streaming

Source: https://docs.langchain.com/oss/python/deepagents/streaming

## Local Usage Guidance
Use this page for standard streaming behavior in Deep Agents.
Read this when implementing token/message streaming, CLI progress output, or simple live responses.

## Extracted Documentation Content

### Key Sections
-  Enable subgraph streaming
-  Namespaces
-  Subagent progress
-  LLM tokens
-  Tool calls
-  Custom updates
-  Stream multiple modes
-  Common patterns
-  Track subagent lifecycle
-  v2 streaming format
-  Related

### Important Points
- Stream real-time updates from deep agent runs and subagent execution
- Stream subagent progress —track each subagent’s execution as it runs in parallel.
- Stream LLM tokens —stream tokens from the main agent and each subagent.
- Stream tool calls —see tool calls and results from within subagent execution.
- Stream custom updates —emit user-defined signals from inside subagent nodes.
- Subagents —Configure and use subagents with Deep Agents
- Frontend streaming —Build React UIs with useStream for Deep Agents
- LangChain Event Streaming —General streaming concepts with LangChain agents

### Extracted Table/Field Signals
- Namespace
- Source
- () (empty)
- Main agent
- ("tools:abc123",)
- A subagent spawned by the main agent’s task tool call abc123
- ("tools:abc123", "model_request:def456")
- The model request node inside a subagent

### API And Concept Signals
`Agents`, `Stream`, `Streaming`, `Subagent`, `Subagents`, `Tool`, `active_subagents`, `agent`, `agents`, `create_deep_agent`, `deepagents`, `get_stream_writer`, `is_subagent`, `middleware`, `model`, `model_request`, `state`, `states`, `stream`, `stream_mode`, `streaming`, `subagent`, `subagent_ns`, `subagent_type`, `subagents`, `task`, `tasks`, `tool`

### Representative Code Signals
```text
from deepagents import create_deep_agent agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , system_prompt = "You are a helpful research assistant" , subagents = [ { "name" : "researcher" , "description" : "Researches a topic in depth" , "system_prompt" : "You are a thorough researcher." , }, ], ) for chunk in agent . stream ( { "messages" : [{ "role" : "user" , "content" : "Research quantum computing advances" }]}, stream_mode = "updates" , subgraphs = True , version = "v2" , ): if chunk [ " type " ] == "updates" : if chunk [ " ns " ]: # Subagent event - namespace identifies the source print ( f "[subagent: { chunk [ ' ns ' ] } ]" ) else : # Main agent event print ( "[main agent]" ) print ( chunk [ " data " ])
```
```text
for chunk in agent . stream ( { "messages" : [{ "role" : "user" , "content" : "Plan my vacation" }]}, stream_mode = "updates" , subgraphs = True , version = "v2" , ): if chunk [ " type " ] == "updates" : # Check if this event came from a subagent is_subagent = any ( segment . startswith ( "tools:" ) for segment in chunk [ " ns " ] ) if is_subagent : # Extract the tool call ID from the namespace tool_call_id = next ( s . split ( ":" )[ 1 ] for s in chunk [ " ns " ] if s . startswith ( "tools:" ) ) print ( f "Subagent { tool_call_id } : { chunk [ ' data ' ] } " ) else : print ( f "Main agent: { chunk [ ' data ' ] } " )
```
```text
from deepagents import create_deep_agent agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , system_prompt = ( "You are a project coordinator. Always delegate research tasks " "to your researcher subagent using the task tool. Keep your final response to one sentence." ), subagents = [ { "name" : "researcher" , "description" : "Researches topics thoroughly" , "system_prompt" : ( "You are a thorough researcher. Research the given topic " "and provide a concise summary in 2-3 sentences." ), }, ], ) for chunk in agent . stream ( { "messages" : [{ "role" : "user" , "content" : "Write a short summary about AI safety" }]}, stream_mode = "updates" , subgraphs = True , version = "v2" , ): if chunk [ " type " ] == "updates" : # Main agent updates (empty namespace) if not chunk [ " ns " ]: for node_name , data in chunk [ " data " ]. items (): if node_name == "tools" : # Subagent r
```
```text
[ main agent ] step: model_request [ tools:call_abc123 ] step: model_request [ tools:call_abc123 ] step: tools [ tools:call_abc123 ] step: model_request Subagent complete: task Result: ## AI Safety Report... [ main agent ] step: model_request
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
