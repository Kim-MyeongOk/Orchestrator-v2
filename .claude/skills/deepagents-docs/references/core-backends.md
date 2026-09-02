# Backends

Source: https://docs.langchain.com/oss/python/deepagents/backends

## Local Usage Guidance
Use this page when configuring where Deep Agents store and access files, state, memory, and execution artifacts.
Read this when designing persistence, isolation, custom filesystems, backend policies, or multi-user storage.

## Extracted Documentation Content

### Key Sections
-  Quickstart
-  Built-in backends
-  StateBackend
-  FilesystemBackend (local disk)
-  LocalShellBackend (local shell)
-  StoreBackend (LangGraph store)
-  Namespace factories
-  ContextHubBackend
-  CompositeBackend (router)
-  Specify a backend
-  Route to different backends
-  Custom backends
-  Implement the backend protocol
-  Permissions
-  Add policy hooks
-  Migrate from backend factories
-  What changed
-  Deprecated APIs
-  Migration example
-  Migrating from BackendContext

### Important Points
- Choose and configure filesystem backends for Deep Agents. You can specify routes to different backends, implement virtual filesystems, and enforce policies.
- Route different paths to different backends
- Implement a custom backend
- Set permissions on filesystem access
- Comply with the backend protocol
- Stores files in LangGraph agent state for the current thread via StateBackend .
- Persists across multiple agent turns on the same thread via checkpoints. Files are not shared across threads.
- A scratch pad for the agent to write intermediate results.
- Automatic eviction of large tool outputs which the agent can then read back in piece by piece.
- Local development CLIs (coding assistants, development tools)
- CI/CD pipelines (see security considerations below)
- Web servers or HTTP APIs - use StateBackend , StoreBackend , or a sandbox backend instead
- Agents can read any accessible file, including secrets (API keys, credentials, .env files)
- Combined with network tools, secrets may be exfiltrated via SSRF attacks
- File modifications are permanent and irreversible
- Enable Human-in-the-Loop (HITL) middleware to review sensitive operations.
- Exclude secrets from accessible filesystem paths (especially in CI/CD).
- Use a sandbox backend for production environments requiring filesystem interaction.

### Extracted Table/Field Signals
- Built-in backend
- Description
- Default
- Local filesystem persistence
- Durable store (LangGraph store)
- Context Hub
- Sandbox
- Local shell
- Composite
- Method
- Signature
- What it does
- (path: str) -> LsResult
- List files and directories at the given path.
- read
- (file_path: str, offset: int, limit: int) -> ReadResult
- Return file contents, optionally paginated.
- write
- (file_path: str, content: str) -> WriteResult
- Create or overwrite a file.
- edit
- (file_path: str, old_string: str, new_string: str, replace_all: bool) -> EditResult
- Find-and-replace within an existing file.
- glob

### API And Concept Signals
`AgentCore`, `Agents`, `BackendContext`, `BackendProtocol`, `Backends`, `BaseStore`, `CompositeBackend`, `Context`, `ContextHubBackend`, `Create`, `File`, `FileData`, `FileInfo`, `Files`, `Filesystem`, `FilesystemBackend`, `FilesystemPermission`, `GuardedBackend`, `InMemoryStore`, `LocalShellBackend`, `Permissions`, `Protocol`, `S3Backend`, `Sandbox`, `Sandboxes`, `State`, `StateBackend`, `Store`

### Representative Code Signals
```text
from deepagents import create_deep_agent from deepagents . backends import StateBackend # By default we provide a StateBackend agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" ) # Under the hood, it looks like agent2 = create_deep_agent ( model = "openai:gpt-5.5" , backend = StateBackend (), )
```
```text
from deepagents import create_deep_agent from deepagents . backends import FilesystemBackend agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , backend = FilesystemBackend ( root_dir = "." , virtual_mode = True ), )
```
```text
from deepagents import create_deep_agent from deepagents . backends import CompositeBackend , StateBackend , FilesystemBackend agent = create_deep_agent ( backend = CompositeBackend ( default = StateBackend (), routes = { "/workspace/" : FilesystemBackend ( root_dir = "/path/to/project" , virtual_mode = True ), }, ) )
```
```text
from deepagents import create_deep_agent from deepagents . backends import LocalShellBackend agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , backend = LocalShellBackend ( root_dir = "." , virtual_mode = True , env = { "PATH" : "/usr/bin:/bin" }), )
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
