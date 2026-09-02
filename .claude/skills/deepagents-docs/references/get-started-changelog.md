# Changelog

Source: https://docs.langchain.com/oss/python/releases/changelog

## Local Usage Guidance
Use this page when behavior may have changed across package versions.
The changelog tracks release-level changes across LangChain's Python OSS packages. It is important for breaking changes, renamed APIs, new beta features, version compatibility, and migration notes.
Read this when the user asks "is this still supported?", "what changed?", or reports behavior that may depend on package version.

## Extracted Documentation Content

### Key Sections
-  deepagents v0.6.0
-  langchain v1.3.0
-  langgraph v1.2.0
-  deepagents v0.5.0
-  langgraph v1.1.0
-  deepagents v0.4.0
-  langchain v1.2.0
-  langchain-google-genai v4.0.0
-  langchain v1.1.0
-  v1.0.0
-  langchain
-  langgraph

### Important Points
- Log of updates and improvements to our Python packages
- CodeInterpreterMiddleware : (experimental) deepagents now supports code execution and programmatic tool calling through a scoped QuickJS runtime.
- Supports version="v3" in stream_events / astream_events . Refer to the event streaming guide for details.
- DeltaChannel (beta) ( blog ): Deep Agents now uses DeltaChannel for message history and agent files. Rather than re-serializing the full accumulated value into every checkpoint, only the incremental delta written at each step is stored — keeping checkpoint sizes small as threads grow long.
- Harness profiles : Register per-provider or per-model configuration bundles ( HarnessProfile ) that create_deep_agent applies automatically when a model is selected — system-prompt tweaks, tool overrides, middleware changes, and subagent defaults — without modifying the call site.
- ContextHubBackend ( blog ): A new filesystem backend backed by LangSmith Hub. Agent files — skills, memories, and other persisted context — are stored as Hub commits, giving you version history on every write and LangSmith-native durability without provisioning a separate LangGraph store.
- DeltaChannel (beta) : A new channel type that stores only the incremental delta at each step rather than re-serializing the full accumulated value. Most useful for channels that grow large over time, for example a message list in a long-running thread. Use snapshot_frequency=K to write a full snapshot every K steps and bound read latency.
- Per-node timeouts : Pass timeout= to add_node to cap how long a single attempt may run. Set a hard wall-clock limit ( run_timeout ), an idle limit that resets on progress ( idle_timeout ), or both via TimeoutPolicy . When the limit fires, LangGraph raises NodeTimeoutError , clears writes from that attempt, and hands off to the retry policy. Async nodes only.
- Node-level error handlers : Pass error_handler= to add_node to run a recovery function after all retries are exhausted. The handler receives a typed NodeError and can return a Command to update state and route to a different node, useful for Saga/compensation patterns.
- Graceful shutdown : Stop an in-flight run cooperatively after the current superstep completes, and save a resumable checkpoint. Create a RunControl and call request_drain() from any thread; the run raises GraphDrained and can be resumed later with the same config.
- New event streaming API (beta) : Pass version="v3" to stream_events() / astream_events() for a content-block-centric protocol with typed, per-channel projections ( run.values , run.messages , run.lifecycle , run.subgraphs ) plus opt-in transformers for updates, custom events, checkpoints, tasks, and debug. run.messages yields one ChatModelStream per LLM call with typed sub-projections for text, reasoning, tool calls,
- Async subagents : Deep Agents can launch non-blocking background tasks, so users can continue interacting with the agent while subagents work concurrently. Requires LangSmith Deployment for sub-agents.
- Multi-modal support : The read_file tool now supports PDFs, audio, and video files in addition to images.
- Backend changes : We’ve made backward-compatible changes to the Deep Agents backend protocol :
- Updated the file format stored in State and Store backends to support binary files.
- Improved error propagation from backends to tools.
- You can now instantiate StateBackend() and StoreBackend() directly. Specifying with a factory (e.g., backend=(lambda rt: StateBackend(rt)) ) is deprecated.
- Anthropic prompt caching improvements : We’ve made some improvements to improve prompt caching performance for Anthropic models.

### API And Concept Signals
`Agent`, `Agents`, `Backend`, `ChatModelStream`, `CodeInterpreterMiddleware`, `ContextHubBackend`, `ContextOverflowError`, `Create`, `HarnessProfile`, `Model`, `State`, `StateBackend`, `Store`, `StoreBackend`, `StreamPart`, `agent`, `agents`, `ainvoke`, `astream`, `astream_events`, `backend`, `backends`, `chat_models`, `client`, `context`, `create_agent`, `create_deep_agent`, `deepagents`

### Representative Code Signals
```text
from langchain . chat_models import init_chat_model agent = create_deep_agent ( model = init_chat_model ( "openai:..." , use_responses_api = True , store = False , include = [ "reasoning.encrypted_content" ], ) )
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
