# Async subagents

Source: https://docs.langchain.com/oss/python/deepagents/async-subagents

## Local Usage Guidance
Use this page when subagent execution should happen asynchronously.
Read this when designing asynchronous task handling, concurrent subagent execution, or streamed progress from delegated work.

## Extracted Documentation Content

### Key Sections
-  When to use async subagents
-  Configure async subagents
-  Use the async subagent tools
-  Understand the lifecycle
-  Understand state management
-  Choose a transport
-  ASGI transport (co-deployed)
-  HTTP transport (remote)
-  Choose a deployment topology
-  Single deployment
-  Split deployment
-  Hybrid
-  Best practices
-  Size the worker pool for local development
-  Write clear subagent descriptions
-  Trace with thread IDs
-  Troubleshooting
-  Supervisor polls immediately after launch
-  Supervisor reports stale status
-  Task ID lookup failures

### Important Points
- Launch background subagents that run concurrently while the supervisor continues interacting with the user
- Launch creates a new thread on the server, starts a run with the task description as input, and returns the thread ID as the task ID. The supervisor reports this ID to the user and does not poll for completion.
- Check fetches the current run status. If the run succeeded, it retrieves the thread state to extract the subagent’s final output. If still running, it reports that to the user.
- Update creates a new run on the same thread with an interrupt multitask strategy. The previous run is interrupted, and the subagent restarts with the full conversation history plus the new instructions. The task ID stays the same.
- Cancel calls runs.cancel() on the server and marks the task as "cancelled" .
- List iterates over all tracked tasks. For non-terminal tasks, it fetches live status from the server in parallel. Terminal statuses ( success , error , cancelled ) are returned from cache.

### Extracted Table/Field Signals
- Dimension
- Sync subagents
- Async subagents
- Execution model
- Supervisor blocks until subagent completes
- Returns job ID immediately; supervisor continues
- Concurrency
- Parallel but blocking
- Parallel and non-blocking
- Mid-task updates
- Not possible
- Send follow-up instructions via update_async_task
- Cancellation
- Cancel running tasks via cancel_async_task
- Statefulness
- Stateless — no persistent state between invocations
- Stateful — maintains state on its own thread across interactions
- Best for
- Tasks where the agent should wait for results before continuing
- Long-running, complex tasks managed interactively in a chat
- Field
- Type
- Description
- name

### API And Concept Signals
`Agent`, `AsyncSubAgent`, `Protocol`, `Stateful`, `Statefulness`, `Stateless`, `Subagent`, `Task`, `Tasks`, `Tool`, `agent`, `async_subagents`, `cancel_async_task`, `check_async_task`, `create_deep_agent`, `creates`, `deepagents`, `interrupt`, `interrupted`, `list_async_tasks`, `model`, `multitask`, `start_async_task`, `state`, `subagent`, `subagents`, `task`, `tasks`

### Representative Code Signals
```text
from deepagents import AsyncSubAgent , create_deep_agent async_subagents = [ AsyncSubAgent ( name = "researcher" , description = "Research agent for information gathering and synthesis" , graph_id = "researcher" , # No url → ASGI transport (co-deployed in the same deployment) ), AsyncSubAgent ( name = "coder" , description = "Coding agent for code generation and review" , graph_id = "coder" , # url="https://coder-deployment.langsmith.dev" # Optional: HTTP transport for remote ), ] agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , subagents = async_subagents , )
```
```text
{ " graphs " : { " supervisor " : "./src/supervisor.py:graph" , " researcher " : "./src/researcher.py:graph" , " coder " : "./src/coder.py:graph" } }
```
```text
AsyncSubAgent ( name = "researcher" , description = "Research agent" , graph_id = "researcher" , url = "https://my-research-deployment.langsmith.dev" , )
```
```text
async_subagents = [ AsyncSubAgent ( name = "researcher" , description = "Research agent" , graph_id = "researcher" , # No url → ASGI (co-deployed) ), AsyncSubAgent ( name = "coder" , description = "Coding agent" , graph_id = "coder" , url = "https://coder-deployment.langsmith.dev" , # url present → HTTP (remote) ), ]
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
