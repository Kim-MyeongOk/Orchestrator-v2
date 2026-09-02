# Customize Deep Agents

Source: https://docs.langchain.com/oss/python/deepagents/customization

## Local Usage Guidance
Use this page when the user wants to customize the behavior, inputs, tool surface, middleware, state, runtime context, or output structure of a Deep Agent.
The customization guide is the next step after Quickstart. It explains the main configuration surfaces around `create_deep_agent`, including model selection, prompts, tools, middleware, subagents, state/context schemas, and response shaping.
Read this when examples need to go beyond the default agent loop.

## Extracted Documentation Content

### Key Sections
-  Model
-  Tools
-  MCP tools
-  System prompt
-  Prompt assembly
-  Middleware
-  Default stack (main agent)
-  Default stack (synchronous subagents)
-  Prebuilt middleware
-  Provider-specific middleware
-  Custom middleware
-  Interpreters
-  Subagents
-  Backends
-  Sandboxes
-  Human-in-the-loop
-  Skills
-  Memory
-  Profiles
-  Structured output

### Important Points
- Learn how to customize Deep Agents with system prompts, tools, subagents, and more
- USER is always at the front. The caller’s text precedes any SDK or profile content, so persona/instructions take precedence regardless of which model is selected.
- SUFFIX is always at the end. Profile suffixes sit closest to the conversation history, where model-tuning guidance lands most reliably.
- General-purpose subagent prompt
- TodoListMiddleware : Tracks and manages todo lists for organizing agent tasks and work.
- SkillsMiddleware : Only when you pass skills . Injected immediately after the todo middleware and before filesystem middleware so skill metadata is available before file tools run.
- FilesystemMiddleware : Handles file system operations such as reading, writing, and navigating directories. When you pass permissions , filesystem permissions enforcement is included here so it can evaluate every tool the agent might call.
- SubAgentMiddleware : Spawns and coordinates subagents for delegating tasks to specialized agents.
- SummarizationMiddleware : Condenses message history to stay within context limits when conversations grow long (via create_summarization_middleware ).
- PatchToolCallsMiddleware : Repairs dangling tool calls in message history when a run resumes after an interruption or receives malformed tool-call arguments. Runs before Anthropic prompt caching and the tail stack below.
- AsyncSubAgentMiddleware : Only when you configure async subagents.
- Your middleware argument : Optional middleware you pass as the middleware argument is appended here (after Patch, before the tail stack).
- Harness profile extras : Provider-specific middleware from the resolved model profile, if any.
- Excluded-tool filtering : When the harness profile lists excluded tools, middleware removes those tools from the agent.
- Prompt caching ( AnthropicPromptCachingMiddleware and BedrockPromptCachingMiddleware ): Both are always registered and run after Patch and after your middleware so the cached prefix matches what is actually sent to the model. Each no-ops on models it does not support ( unsupported_model_behavior="ignore" ), so the Anthropic middleware applies on Anthropic models and the Bedrock middleware on AWS Bedrock models with c
- MemoryMiddleware : Only when you pass memory . MemoryMiddleware is placed after profile extras and the prompt caching middleware so updates to injected memory are less likely to invalidate the cache prefix. The same ordering concern is called out in the create_deep_agent implementation comments.
- HumanInTheLoopMiddleware : Only when you pass interrupt_on . Pauses for human approval or input at configured tool calls.
- Skills run after PatchToolCallsMiddleware on these inner agents (on the main agent, skills run before filesystem middleware when skills is set).

### Extracted Table/Field Signals
- Parameter
- What it does
- model=
- Which model to use
- system_prompt=
- Custom instructions for the agent
- tools=
- Domain tools the agent can call
- memory=
- AGENTS.md files loaded at startup
- skills=
- Skills directory for on-demand knowledge
- backend=
- Filesystem backend (StateBackend by default)
- permissions=
- Path-level access control for the filesystem
- subagents=
- Custom subagents for delegated tasks
- middleware=
- Extra middleware appended to the default stack
- interrupt_on=
- Pause before tool calls for human approval
- response_format=
- Structured output schema

### API And Concept Signals
`AGENTS`, `AgentMiddleware`, `AgentState`, `Agents`, `AnthropicPromptCachingMiddleware`, `AsyncSubAgent`, `AsyncSubAgentMiddleware`, `BASE_AGENT_PROMPT`, `BackendFactory`, `BackendProtocol`, `Backends`, `BaseChatModel`, `BaseModel`, `BaseStore`, `BaseTool`, `BedrockPromptCachingMiddleware`, `CodeInterpreterMiddleware`, `CompiledStateGraph`, `CompiledSubAgent`, `CompositeBackend`, `ContextHubBackend`, `ContextT`, `Create`, `CustomMiddleware`, `CustomMiddlewareBad`, `DaytonaSandbox`, `DeepAgentState`, `E2BSandbox`

### Representative Code Signals
```text
from deepagents import create_deep_agent agent = create_deep_agent ( model = "anthropic:claude-sonnet-4-6" , system_prompt = "You are a helpful assistant." , tools = [ search , fetch_url ], memory = [ "./AGENTS.md" ], skills = [ "./skills/" ], )
```
```text
create_deep_agent ( model : str | BaseChatModel | None = None , tools : Sequence [ BaseTool | Callable | dict [ str , Any ]] | None = None , * , system_prompt : str | SystemMessage | None = None , middleware : Sequence [ AgentMiddleware ] = (), subagents : Sequence [ SubAgent | CompiledSubAgent | AsyncSubAgent ] | None = None , skills : list [ str ] | None = None , memory : list [ str ] | None = None , permissions : list [ FilesystemPermission ] | None = None , backend : BackendProtocol | BackendFactory | None = None , interrupt_on : dict [ str , bool | InterruptOnConfig ] | None = None , response_format : ResponseFormat [ ResponseT ] | type [ ResponseT ] | dict [ str , Any ] | None = None , state_schema : type [ DeepAgentState ] | None = None , context_schema : type [ ContextT ] | None = None , checkpointer : Checkpointer | None = None , store : BaseStore | None = None , debug : bool = 
```
```text
pip install -U "langchain[openai]"
```
```text
import os from deepagents import create_deep_agent os . environ [ " OPENAI_API_KEY " ] = "sk-..." agent = create_deep_agent ( model = "openai:gpt-5.5" ) # this calls init_chat_model for the specified model with default parameters # to use specific model parameters, use init_chat_model directly
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
