# Going to production

Source: https://docs.langchain.com/oss/python/deepagents/going-to-production

## Local Usage Guidance
Use this page for production-readiness decisions.
This page should guide questions about reliability, state persistence, observability, security, permissions, deployment topology, human approval, evaluation, and operational monitoring.
Read this when moving from a prototype agent to a service used by real users.

## Extracted Documentation Content

### Key Sections
-  Overview
-  LangSmith Deployments
-  Production considerations
-  Invoking the agent
-  Multi-tenancy
-  User identity and access control
-  Team access control (RBAC)
-  End-user credentials
-  Async
-  Durability
-  Memory
-  Scoping
-  Configuration
-  Execution environment
-  Filesystem
-  Sandboxes
-  Lifecycle
-  File transfers
-  Managing secrets
-  Guardrails

### Important Points
- Take your deep agent to production with persistent memory, sandboxes, resilience middleware, and deployment options
- Thread : a single conversation. Message history and scratch files are scoped to the thread by default and don’t carry over.
- User : someone interacting with your agent. Memory and files can be private to a user or shared across users. Identity and authorization comes from your auth layer .
- Assistant : a configured agent instance. Memory and files can be tied to one assistant or shared across all of them.
- LangSmith Deployments : managed infrastructure with auth, webhooks, and cron
- Production considerations : invocation, multi-tenancy, authentication, credentials, async, and durability
- Memory : persist information across conversations
- Execution environment : file storage and code execution
- Guardrails : rate limiting, error handling, and data privacy
- Frontend : connect your UI to a deployed agent
- thread_id (passed via config={"configurable": {"thread_id": ...}} ): a stable identifier for the conversation. The checkpointer uses it to persist and resume message history, so follow-up turns continue the same conversation. Generate a new thread_id to start a fresh conversation.
- context : per-run data your tools and middleware read at invocation time, for example user_id , API keys, feature flags, or session metadata. Define the shape with context_schema and access it via runtime.context . See Runtime context .
- Tag resources with ownership metadata (e.g., owner: user_id )
- Return filters so users only see their own resources
- Deny access with HTTP 403 for unauthorized operations
- Create async tools. LangChain runs sync tools in a separate thread to avoid blocking, but native async avoids the threading overhead entirely.
- Use async middleware methods. Custom middleware should implement async hooks (e.g., abefore_agent instead of before_agent ).
- Use async for external resource lifecycle. Creating sandboxes or connecting to MCP servers involves network calls and should be awaited. This is why graph factories that provision these resources are async.

### Extracted Table/Field Signals
- Field
- Description
- dependencies
- Packages to install. ["."] installs the current directory as a package (reads from requirements.txt , pyproject.toml , or package.json ).
- graphs
- env
- Path to a .env file with environment variables (API keys, secrets). These are set at build time and available at runtime.
- Role
- Access
- Workspace Admin
- Full permissions including settings and member management
- Workspace Editor
- Create and modify resources, but cannot delete runs or manage members
- Workspace Viewer
- Read-only access
- Scope
- Namespace
- Use case
- Example
- User (recommended default)
- (user_id)
- Per-user preferences and context
- ”I prefer concise responses”
- Assistant

### API And Concept Signals
`AgentMiddleware`, `AgentState`, `Client`, `CompositeBackend`, `Context`, `ContextHubBackend`, `Create`, `File`, `Files`, `Filesystem`, `LangSmithSandbox`, `MCP`, `Memory`, `Middleware`, `ModelCallLimitMiddleware`, `ModelFallbackMiddleware`, `ModelRetryMiddleware`, `PIIMiddleware`, `Permissions`, `Sandbox`, `SandboxClient`, `SandboxSyncMiddleware`, `Sandboxes`, `StateBackend`, `StoreBackend`, `ToolCallLimitMiddleware`, `ToolRetryMiddleware`, `ToolRuntime`

### Representative Code Signals
```text
{ " dependencies " : [ "." ], " graphs " : { " agent " : "./agent.py:agent" }, " env " : ".env" }
```
```text
from dataclasses import dataclass from deepagents import create_deep_agent from langchain_core . utils . uuid import uuid7 @dataclass class Context : user_id : str agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , context_schema = Context , ) # Start a conversation config = { "configurable" : { "thread_id" : str ( uuid7 ())}} agent . invoke ( { "messages" : [{ "role" : "user" , "content" : "Plan a 3-day trip to Tokyo" }]}, config = config , context = Context ( user_id = "user-123" ), ) # Follow-up on the same conversation: reuse the same thread_id agent . invoke ( { "messages" : [{ "role" : "user" , "content" : "Make it 5 days instead" }]}, config = config , context = Context ( user_id = "user-123" ), )
```
```text
from langgraph_sdk import get_client client = get_client ( url = "<DEPLOYMENT_URL>" , api_key = "<LANGSMITH_API_KEY>" ) thread = await client . threads . create () async for chunk in client . runs . stream ( thread [ " thread_id " ], "agent" , input = { "messages" : [{ "role" : "user" , "content" : "Plan a 3-day trip to Tokyo" }]}, context = { "user_id" : "user-123" }, stream_mode = "updates" , ): print ( chunk . data )
```
```text
from langchain_auth import Client from langchain . tools import tool , ToolRuntime auth_client = Client () # Inside your agent's tool: @tool async def github_action ( runtime : ToolRuntime ): """Perform an action on behalf of the user via GitHub.""" auth_result = await auth_client . authenticate ( provider = "github" , scopes = [ "repo" , "read:org" ], user_id = runtime . server_info . user . identity , ) # Use auth_result.token for GitHub API calls on the user's behalf
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
