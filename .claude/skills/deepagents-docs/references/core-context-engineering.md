# Context engineering in Deep Agents

Source: https://docs.langchain.com/oss/python/deepagents/context-engineering

## Local Usage Guidance
Use this page for context window management and long-running work.
Read this when the user asks how to reduce token usage, preserve important context, or design agents for complex multi-step tasks.

## Extracted Documentation Content

### Key Sections
-  Types of context
-  Input context
- System prompt
- Memory
- Skills
- Tool prompts
-  System prompt
-  Memory
-  Skills
-  Tool prompts
-  Complete system prompt
-  Runtime context
-  Custom state schema
-  Context compression
- Offloading
- Summarization
-  Offloading
-  Summarization
-  Context isolation with subagents
-  Long-term memory

### Important Points
- Control what context your deep agent has access to and how it is managed across long-running tasks
- Planning prompt – Instructions for write_todos to maintain a structured task list
- Filesystem prompt – Documentation for ls , read_file , write_file , edit_file , glob , grep (and execute when using a sandbox backend)
- Subagent prompt – Guidance for delegating work with the task tool
- Human-in-the-loop prompt – Usage for pausing at specified tool calls (when interrupt_on is set)
- Local context prompt – Current directory and project info (CLI only)
- Custom system_prompt (if provided)
- To-do list prompt: Instructions for how to plan with to do lists
- Memory prompt: AGENTS.md + memory usage guidelines (only when memory provided)
- Skills prompt: Skills locations + list of skills with frontmatter information + usage (only when skills provided)
- Virtual filesystem prompt (filesystem + execute tool docs if applicable)
- Subagent prompt: Task tool usage
- User-provided middleware prompts (if custom middleware is provided)
- Human-in-the-loop prompt (when interrupt_on is set)
- Tool call inputs exceed 20,000 tokens : File write and edit operations leave behind tool calls containing the complete file content in the agent’s conversation history. Since this content is already persisted to the filesystem, it’s often redundant. As the session context crosses 85% of the model’s available window, deep agents truncate older tool calls, replacing them with a pointer to the file on disk and reducing 
- Tool call results exceed 20,000 tokens : When this occurs, the deep agent offloads the response to the configured backend and substitutes it with a file path reference and a preview of the first 10 lines. Agents can then re-read or search the content as needed.
- In-context summary : An LLM generates a structured summary of the conversation including session intent, artifacts created, and next steps—which replaces the full conversation history in the agent’s working memory.
- Filesystem preservation : A text rendering of the original conversation messages is written to the filesystem as a canonical record.

### Extracted Table/Field Signals
- Context Type
- What You Control
- Scope
- Input context
- What goes into the agent’s prompt at startup (system prompt, memory, skills)
- Static, applied each run
- Runtime context
- Static configuration passed at invoke time (user metadata, API keys, connections)
- Per run, propagates to subagents
- Context compression
- Built-in offloading and summarization to keep context within window limits
- Automatic, when limits approached
- Context isolation
- Use subagents to quarantine heavy work, returning only results to the main agent
- Per subagent, when delegated
- Long-term memory
- Persistent storage across threads using the virtual filesystem
- Persistent across conversations

### API And Concept Signals
`AGENTS`, `Agents`, `Backends`, `CompositeBackend`, `Context`, `ContextOverflowError`, `DeepAgentState`, `File`, `Filesystem`, `InMemoryStore`, `Memory`, `ResearchState`, `Skills`, `StateBackend`, `StoreBackend`, `Subagent`, `Subagents`, `Task`, `Tool`, `ToolRuntime`, `agent`, `agents`, `backend`, `backends`, `context`, `context_schema`, `create`, `create_deep_agent`

### Representative Code Signals
```text
from deepagents import create_deep_agent agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , system_prompt = ( "You are a research assistant specializing in scientific literature. " "Always cite sources. Use subagents for parallel research on different topics." ), )
```
```text
agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , memory = [ "/project/AGENTS.md" , "~/.deepagents/preferences.md" ], )
```
```text
agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , skills = [ "/skills/research/" , "/skills/web-search/" ], )
```
```text
@tool ( parse_docstring = True ) def search_orders ( user_id : str , status : str , limit : int = 10 ) -> str : """Search for user orders by status. Use this when the user asks about order history or wants to check order status. Always filter by the provided status. Args: user_id: Unique identifier for the user status: Order status: 'pending', 'shipped', or 'delivered' limit: Maximum number of results to return """ # Implementation here ...
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
