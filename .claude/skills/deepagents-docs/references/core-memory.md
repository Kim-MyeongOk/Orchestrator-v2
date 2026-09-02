# Memory

Source: https://docs.langchain.com/oss/python/deepagents/memory

## Local Usage Guidance
Use this page for persistent agent context across conversations or runs.
Read this when designing personalization, project rules, user preferences, or long-term agent behavior.

## Extracted Documentation Content

### Key Sections
-  How memory works
-  Scoped memory
-  Agent-scoped memory
-  User-scoped memory
-  Advanced usage
-  Episodic memory
-  Organization-level memory
-  Background consolidation
-  Consolidation agent
-  Cron
-  Read-only vs writable memory
-  Concurrent writes
-  Multiple agents in the same deployment

### Important Points
- Add persistent memory to agents built with Deep Agents so they learn and improve across conversations
- Point the agent at memory files. Pass file paths to memory= when creating the agent. You can also pass skills via skills= for procedural memory (reusable instructions that tell the agent how to perform a task). A backend controls where files are stored and who can access them.
- Agent reads memory. The agent can load memory files into the system prompt at startup, or read them on demand during the conversation. For example, skills use on-demand loading: the agent reads only skill descriptions at startup, then reads the full skill file only when it matches a task. This keeps context lean until a capability is needed.
- Agent updates memory (optional). When the agent learns new information, it can use its built-in edit_file tool to update memory files. Updates can happen during the conversation (the default) or in the background between conversations via background consolidation . Changes are persisted and available in the next conversation. Not all memory is writable: developer-defined skills and organization policies are typically
- Full example: seed memory and invoke
- Full example: isolated memory across users
- Default to user scope (user_id) unless you have a specific reason to share
- Use read-only memory for shared policies (populate via application code, not the agent)
- Add human-in-the-loop validation before the agent writes to shared memory. Use an interrupt to require human approval for writes to sensitive paths.

### Extracted Table/Field Signals
- Dimension
- Question it answers
- Options
- Duration
- How long does it last?
- Short-term (single conversation) or long-term (across conversations)
- Information type
- What kind of information is it?
- Episodic (past experiences), procedural (instructions and skills), or semantic (facts)
- Scope
- Who can see and modify it?
- User , agent , or organization
- Update strategy
- When are memories written?
- During conversation (default) or between conversations
- Retrieval
- How are memories read?
- Loaded into prompt (default) or on demand (e.g., skills )
- Agent permissions
- Can the agent write to memory?
- Read-write (default) or read-only (for shared policies)
- Approach
- Pros
- Cons

### API And Concept Signals
`AGENTS`, `Agent`, `Agents`, `CompositeBackend`, `InMemoryStore`, `Memory`, `Permission`, `SKILL`, `StateBackend`, `Store`, `StoreBackend`, `ToolRuntime`, `agent`, `agents`, `backend`, `backends`, `client`, `consolidation_agent`, `context`, `create`, `create_deep_agent`, `create_file_data`, `deepagents`, `edit_file`, `file`, `files`, `get_client`, `interrupt`

### Representative Code Signals
```text
from deepagents import create_deep_agent from deepagents . backends import CompositeBackend , StateBackend , StoreBackend agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , memory = [ "/memories/AGENTS.md" ], skills = [ "/skills/" ], backend = CompositeBackend ( default = StateBackend (), routes = { "/memories/" : StoreBackend ( namespace = lambda rt : ( rt . server_info . assistant_id , ), ), "/skills/" : StoreBackend ( namespace = lambda rt : ( rt . server_info . assistant_id , ), ), }, ), )
```
```text
from langchain_core . utils . uuid import uuid7 from deepagents import create_deep_agent from deepagents . backends import CompositeBackend , StateBackend , StoreBackend from deepagents . backends . utils import create_file_data from langgraph . store . memory import InMemoryStore store = InMemoryStore () # Use platform store when deploying to LangSmith # Seed the memory file store . put ( ( "my-agent" ,), "/memories/AGENTS.md" , create_file_data ( """## Response style - Keep responses concise - Use code examples where possible """ ), ) # Seed a skill store . put ( ( "my-agent" ,), "/skills/langgraph-docs/SKILL.md" , create_file_data ( """--- name: langgraph-docs description: Fetch relevant LangGraph documentation to provide accurate guidance. --- # langgraph-docs Use the fetch_url tool to read https://docs.langchain.com/llms.txt, then fetch relevant pages. """ ), ) agent = create_deep_a
```
```text
from deepagents import create_deep_agent from deepagents . backends import CompositeBackend , StateBackend , StoreBackend agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , memory = [ "/memories/preferences.md" ], skills = [ "/skills/" ], backend = CompositeBackend ( default = StateBackend (), routes = { "/memories/" : StoreBackend ( namespace = lambda rt : ( rt . server_info . user . identity ,), ), "/skills/" : StoreBackend ( namespace = lambda rt : ( rt . server_info . user . identity ,), ), }, ), )
```
```text
from langchain_core . utils . uuid import uuid7 from deepagents import create_deep_agent from deepagents . backends import CompositeBackend , StateBackend , StoreBackend from deepagents . backends . utils import create_file_data from langgraph . store . memory import InMemoryStore store = InMemoryStore () # Use platform store when deploying to LangSmith # Seed preferences for two users store . put ( ( "user-alice" ,), "/memories/preferences.md" , create_file_data ( """## Preferences - Likes concise bullet points - Prefers Python examples """ ), ) store . put ( ( "user-bob" ,), "/memories/preferences.md" , create_file_data ( """## Preferences - Likes detailed explanations - Prefers TypeScript examples """ ), ) # Seed a skill for Alice store . put ( ( "user-alice" ,), "/skills/langgraph-docs/SKILL.md" , create_file_data ( """--- name: langgraph-docs description: Fetch relevant LangGraph do
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
