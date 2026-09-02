# Sandbox

Source: https://docs.langchain.com/oss/python/deepagents/frontend/sandbox

## Local Usage Guidance
Use this page when exposing sandbox activity in the frontend.
The sandbox frontend pattern concerns displaying command execution, files, outputs, and artifacts created inside an isolated execution environment.
Read this when building a coding-agent UI, notebook-like interface, or artifact preview surface.

## Extracted Documentation Content

### Key Sections
-  Architecture
-  Sandbox lifecycle
-  Connect the agent and API server
-  Resolve the sandbox from thread metadata
-  Seed project files
-  Adding the file browsing API
-  Create the API server
-  Configure langgraph.json
-  Building the frontend
-  Thread creation
-  File state management
-  Real-time file sync
-  Detecting changed files
-  Displaying diffs
-  Changed files summary
-  Use cases
-  Best practices
-  Related
- Going to production
- Sandboxes

### Important Points
- Build an IDE-like UI for a coding agent backed by a sandbox environment
- Deep agent with a sandbox backend: The agent gets filesystem tools ( read_file , write_file , edit_file , execute ) automatically from the sandbox
- Custom API server — A FastAPI app exposed via langgraph.json ’s http.app field, providing file browsing endpoints the frontend can call
- Three-panel frontend: A file tree, code/diff viewer, and chat panel that syncs files in real time as the agent makes changes
- Coding agents that create, modify, and run code need a visual interface beyond chat
- Code review workflows where the agent suggests changes and the user reviews diffs before accepting
- Tutorial or learning apps where an AI assistant helps users build a project step by step, showing changes in context
- Prototyping tools where users describe features in natural language and watch the agent implement them in real time
- Persist threadId in sessionStorage so page reloads reconnect to the same thread and sandbox instead of creating new ones.
- Sync files on every relevant tool call , not just when the run finishes. Watch for write_file , edit_file , and execute tool messages and refresh immediately.
- Default to diff view for changed files . When a user clicks a file that was modified by the agent, show the diff first — that’s what they care about.
- Show compact tool results for read-only operations . Instead of dumping the full output of read_file in the chat, show a one-liner like Read router.js L1-42 . Reserve the full output display for mutating tools.
- Filter node_modules from the file tree . Nobody wants to browse thousands of dependency files. Filter them out when fetching the tree.
- Use thread-scoped sandboxes for production apps. See Sandbox lifecycle .
- Share sandbox resolution between the agent backend and the API server via thread metadata so both resolve the same environment with no in-memory caches.
- Seed the sandbox with a real project . See File transfers .
- Keep secrets out of the sandbox . Use the sandbox auth proxy instead of environment variables or file uploads for API keys.
- Add guardrails before launch . Configure rate limits , error handling , and data privacy middleware for autonomous coding agents.

### Extracted Table/Field Signals
- Framework
- Library
- Component
- React
- @pierre/diffs
- <FileDiff> with parseDiffFromFile
- Vue
- @git-diff-view/vue
- <DiffView> with generateDiffFile from @git-diff-view/file
- Svelte
- @git-diff-view/svelte
- Angular
- ngx-diff
- <ngx-unified-diff> with [before] and [after]

### API And Concept Signals
`AGENT_URL`, `ChangedFilesSummary`, `Create`, `FILE_MUTATING_TOOLS`, `File`, `FileDiff`, `FileEntry`, `FileSnapshot`, `Files`, `LangSmithSandbox`, `Sandbox`, `Sandboxes`, `ToolMessage`, `adownload_files`, `agent`, `agents`, `backend`, `backends`, `changedFiles`, `client`, `context`, `create`, `create_deep_agent`, `deep_agent_ide`, `deepagents`, `edit_file`, `fetchFile`, `file`

### Representative Code Signals
```text
from deepagents import create_deep_agent from deepagents . backends . langsmith import LangSmithSandbox from langgraph . config import get_config def get_or_create_sandbox_for_thread ( thread_id : str ) -> LangSmithSandbox : if not thread_id : raise ValueError ( "thread_id is required" ) # Look up sandbox_id from thread metadata, create if missing, and seed files. raise NotImplementedError ( "Implement sandbox lookup and creation for your deployment environment." ) def get_thread_id_from_config () -> str : configurable = get_config (). get ( "configurable" , {}) thread_id = configurable . get ( "thread_id" ) if not thread_id : raise ValueError ( "No thread_id, agent must run on a thread" ) return thread_id def agent (): return create_deep_agent ( model = "google_genai:gemini-3.5-flash" , backend = lambda _runtime : get_or_create_sandbox_for_thread ( get_thread_id_from_config () ), )
```
```text
# src/api/server.py from fastapi import FastAPI , Query , Path from utils import get_or_create_sandbox_for_thread app = FastAPI () @app . get ( "/sandbox/ {thread_id} /tree" ) async def list_tree ( thread_id : str = Path ( ... ), filePath : str = Query ( "/app" ), ): sandbox = await get_or_create_sandbox_for_thread ( thread_id ) result = await sandbox . aexecute ( f "find { filePath } -printf '%y \\ t%s \\ t%p \\ n' 2>/dev/null | sort" ) entries = [] for line in result . output . strip (). split ( " \n " ): if not line : continue type_char , size_str , full_path = line . split ( " \t " ) entries . append ({ "name" : full_path . split ( "/" )[ - 1 ], "type" : "directory" if type_char == "d" else "file" , "path" : full_path , "size" : int ( size_str ), }) return { "path" : filePath , "entries" : entries , "sandboxId" : sandbox . id } @app . get ( "/sandbox/ {thread_id} /file" ) async def r
```
```text
{ " graphs " : { " deep_agent_ide " : "./src/agents/my_agent.py:agent" }, " env " : ".env" , " http " : { " app " : "./src/api/server.py:app" } }
```
```text
const THREAD_KEY = "sandbox-thread-id" ; function IDEPreview () { const [ threadId , setThreadId ] = useState < string | null > ( () => sessionStorage . getItem ( THREAD_KEY ) , ) ; const updateThreadId = useCallback ( ( id : string | null ) => { setThreadId (id) ; if (id) sessionStorage . setItem ( THREAD_KEY , id) ; else sessionStorage . removeItem ( THREAD_KEY ) ; }, []) ; const stream = useStream < typeof myAgent > ( { apiUrl : AGENT_URL , assistantId : "deep_agent_ide" , threadId , onThreadId : updateThreadId , } ) ; // Create thread on first mount useEffect ( () => { if (threadId) return ; stream . client . threads . create () . then ( ( t ) => updateThreadId (t . thread_id)) ; }, [stream . client , threadId , updateThreadId]) ; // Pass threadId to sandbox file hooks const { tree , files } = useSandboxFiles (threadId) ; // ... }
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
