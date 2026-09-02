# Interpreters

Source: https://docs.langchain.com/oss/python/deepagents/interpreters

## Local Usage Guidance
Use this page for lightweight programmatic execution inside an agent.
Read this when the user needs programmable behavior but does not need package installs, filesystem access, network access, or a full sandbox.

## Extracted Documentation Content

### Key Sections
-  Why use interpreters?
- Programmatic tool calling (PTC)
- Dynamic subagents
- Stateful work
- Deterministic transforms
-  Choose a pattern
-  Quickstart
-  How interpreters work
-  Programmatic tool calling (PTC)
-  Enable PTC
-  Dynamic subagents
-  Persistence
-  Security
-  Configuration

### Important Points
- Run lightweight code inside Deep Agents to compose tools, orchestrate subagents, and transform structured data
- Tools , through programmatic tool calling (PTC) . Provide an allowlist of tools as async functions under the tools namespace. These can be the agent’s own tools or standalone tools you define and pass in.
- Subagents , through dynamic subagents . When the agent has subagents configured, the interpreter exposes a task() global for dispatching them from code.
- Fan-out and synthesize : Run the same kind of work across many items in parallel, then combine the results.
- Verification : Send findings to independent verifier subagents and keep only confirmed results.
- Recursive workflows : Keep a working set in interpreter variables, select slices, call subagents, and refine the result.
- "thread" (default): State persists across eval calls and across agent turns. The middleware snapshots interpreter state after each agent turn and restores it before the next turn.
- "turn" : State persists across multiple eval calls within one agent turn, then resets on the next turn.
- "call" : Each eval call runs in a fresh REPL with no carry-over from prior calls.
- A turn starts, and the middleware restores the latest interpreter snapshot for the thread.
- The agent calls eval one or more times. Those calls share one live context; the middleware does not snapshot between them.
- The turn finishes, and the middleware writes an updated snapshot to graph state.
- The next turn resumes from that snapshot instead of an empty runtime.

### Extracted Table/Field Signals
- Need
- Use
- One or two simple external calls
- Normal tool calling
- Pure in-memory JavaScript: loops, branches, retries, or data transforms (no external tools)
- Interpreter
- Many external tool calls orchestrated from code (requires PTC )
- Interpreter with programmatic tool calling (PTC)
- Many independent units of work, multiple perspectives, or recursive analysis over large inputs
- Interpreter with dynamic subagents
- Shell commands, package installs, tests, or full OS filesystem access
- Sandboxes
- Capability
- Available by default
- How to expose it
- JavaScript execution
- Yes
- Add interpreter middleware
- Top-level await
- Use promises in interpreter code
- console.log , warn , error capture
- Disable with capture_console=False
- Agent tools
- Add a PTC allowlist

### API And Concept Signals
`Agent`, `Agents`, `BaseTool`, `CodeInterpreterMiddleware`, `Filesystem`, `MemorySaver`, `Sandboxes`, `State`, `Stateful`, `Subagents`, `Tools`, `agent`, `backend`, `context`, `create_deep_agent`, `deepagents`, `filesystem`, `memory`, `memory_limit`, `middleware`, `model`, `restores`, `sandbox`, `state`, `subagentType`, `subagents`, `task`, `tool`

### Representative Code Signals
```text
pip install -U "deepagents[quickjs]"
```
```text
from deepagents import create_deep_agent from langchain_quickjs import CodeInterpreterMiddleware agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , middleware = [ CodeInterpreterMiddleware ()], )
```
```text
const rows = [ { team : "alpha" , score : 8 }, { team : "beta" , score : 13 }, { team : "alpha" , score : 21 }, ] ; const totals = rows . reduce ( ( acc , row ) => { acc[row . team] = (acc[row . team] ?? 0 ) + row . score ; console . log ( ` ${ row . team } score: ${ acc [ row . team ] } ` ) ; return acc ; }, {} ) ; totals ;
```
```text
const result : string = await tools . webSearch ( { query : "deepagents interpreters" , } ) ;
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
