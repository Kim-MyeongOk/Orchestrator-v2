# Event streaming

Source: https://docs.langchain.com/oss/python/deepagents/event-streaming

## Local Usage Guidance
Use this page for typed event streams and detailed run tracing.
Read this when the user wants to parse streams, show subagent progress, or trace tool execution.

## Extracted Documentation Content

### Key Sections
-  Stream subagents
-  Subagent stream fields
-  Track subagent lifecycle
-  Stream messages
-  Stream tool calls
-  Stream nested work
-  Consume concurrently
-  Subagents versus subgraphs
-  Related

### Important Points
- Stream subagents, messages, tool calls, and final output from Deep Agents.
- LangChain Event Streaming covers general agent message and tool-call streaming concepts.
- Subagent frontend streaming shows UI patterns that separate coordinator messages from subagent cards.
- LangGraph Event Streaming covers the underlying graph streaming model.

### Extracted Table/Field Signals
- Field
- Description
- name
- Sub-agent name, taken from the subagent_type the coordinator selects in its task call.
- messages
- Messages emitted by the subagent.
- subagents
- Nested subagent invocations.
- output
- Final subagent state, or completion signal for the delegated task.
- path
- Namespace path for the subagent stream.
- status
- Lifecycle status such as started , completed , failed , or interrupted .
- tool_calls
- Tool calls scoped to the subagent.

### API And Concept Signals
`Agents`, `Stream`, `Streaming`, `Subagent`, `Subagents`, `Tool`, `agent`, `astream_events`, `consume_subagents`, `interrupted`, `model`, `state`, `stream`, `stream_events`, `streaming`, `subagent`, `subagent_type`, `subagents`, `task`, `tool`, `tool_call`, `tool_calls`, `tool_name`

### Representative Code Signals
```text
stream = agent . stream_events ({ "messages" : [{ "role" : "user" , "content" : "Write me a haiku about the sea" }], }, version = "v3" ) for subagent in stream . subagents : print ( subagent . name , subagent . path , subagent . status ) for message in subagent . messages : print ( message . text )
```
```text
stream = agent . stream_events ( input , version = "v3" ) running = 0 completed = 0 failed = 0 for subagent in stream . subagents : running += 1 print ( f " { subagent . name } : started" ) try : _ = subagent . output running -= 1 completed += 1 print ( f " { subagent . name } : completed" ) except Exception : running -= 1 failed += 1 print ( f " { subagent . name } : failed" )
```
```text
stream = agent . stream_events ( input , version = "v3" ) for message in stream . messages : print ( "[coordinator]" , message . text ) for subagent in stream . subagents : for message in subagent . messages : print ( f "[ { subagent . name } ]" , message . text )
```
```text
stream = agent . stream_events ( input , version = "v3" ) for call in stream . tool_calls : print ( "[coordinator tool]" , call . tool_name , call . input ) print ( call . completed , call . error ) for subagent in stream . subagents : for call in subagent . tool_calls : print ( f "[ { subagent . name } tool]" , call . tool_name , call . input ) for delta in call . output_deltas : print ( delta , end = "" , flush = True ) if call . completed and call . error is None : print ( call . output ) elif call . error is not None : print ( call . error )
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
