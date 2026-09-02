# Permissions

Source: https://docs.langchain.com/oss/python/deepagents/permissions

## Local Usage Guidance
Use this page for filesystem access control and scoped agent capabilities.
Read this when the user asks about allowing or denying paths, protecting secrets, or giving subagents narrower access.

## Extracted Documentation Content

### Key Sections
-  Basic usage
-  Rule structure
-  Pause for human approval
-  Examples
-  Isolate to a workspace directory
-  Protect specific files
-  Read-only memory
-  Deny all access
-  Rule ordering
-  Subagent permissions
-  Composite backends

### Important Points
- Control filesystem access with declarative permission rules for Deep Agents

### Extracted Table/Field Signals
- Field
- Type
- Description
- operations
- list["read" | "write"]
- Operations this rule applies to. "read" covers ls , read_file , glob , grep . "write" covers write_file , edit_file .
- paths
- list[str]
- Glob patterns for matching file paths (e.g., ["/workspace/**"] ). Supports ** for recursive matching and {a,b} for alternation.
- mode
- "allow" | "deny" | "interrupt"
- Whether to allow, deny, or pause for human approval on matching operations. Defaults to "allow" . See Pause for human approval .

### API And Concept Signals
`Agents`, `CompositeBackend`, `FilesystemPermission`, `InMemorySaver`, `Interrupt`, `Permissions`, `StateBackend`, `StoreBackend`, `Subagent`, `agent`, `backend`, `backends`, `context`, `correct_permissions`, `create_deep_agent`, `deepagents`, `edit_file`, `file`, `files`, `filesystem`, `incorrect_permissions`, `interrupt`, `memories_backend`, `memory`, `model`, `permission`, `permissions`, `read_file`

### Representative Code Signals
```text
from deepagents import FilesystemPermission , create_deep_agent # Read-only agent: deny all writes agent = create_deep_agent ( model = model , backend = backend , permissions = [ FilesystemPermission ( operations = [ "write" ], paths = [ "/**" ], mode = "deny" , ), ], )
```
```text
from deepagents import FilesystemPermission , create_deep_agent from langgraph . checkpoint . memory import InMemorySaver agent = create_deep_agent ( model = model , permissions = [ # Pause for approval before writing anything under /secrets. FilesystemPermission ( operations = [ "write" ], paths = [ "/secrets/**" ], mode = "interrupt" , ), ], # Interrupt mode requires a checkpointer to pause and resume. checkpointer = InMemorySaver (), )
```
```text
agent = create_deep_agent ( model = model , backend = backend , permissions = [ FilesystemPermission ( operations = [ "read" , "write" ], paths = [ "/workspace/**" ], mode = "allow" , ), FilesystemPermission ( operations = [ "read" , "write" ], paths = [ "/**" ], mode = "deny" , ), ], )
```
```text
agent = create_deep_agent ( model = model , backend = backend , permissions = [ FilesystemPermission ( operations = [ "read" , "write" ], paths = [ "/workspace/.env" , "/workspace/examples/**" ], mode = "deny" , ), FilesystemPermission ( operations = [ "read" , "write" ], paths = [ "/workspace/**" ], mode = "allow" , ), FilesystemPermission ( operations = [ "read" , "write" ], paths = [ "/**" ], mode = "deny" , ), ], )
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
