# Sandboxes

Source: https://docs.langchain.com/oss/python/deepagents/sandboxes

## Local Usage Guidance
Use this page for isolated command execution and external runtime environments.
Read this when the user asks about Docker-like execution, sandbox providers, file transfer, command execution, or risk isolation.

## Extracted Documentation Content

### Key Sections
-  Why use sandboxes?
-  Basic usage
-  Available providers
-  Lifecycle and scoping
-  Thread-scoped (default)
-  Assistant-scoped
-  Integration patterns
-  Agent in sandbox pattern
-  Sandbox as tool pattern
-  How sandboxes work
-  Isolation boundaries
-  The execute method
-  Two planes of file access
-  Working with files
-  Seeding the sandbox
-  Retrieving artifacts
-  Security considerations
-  Handling secrets safely
-  General best practices

### Important Points
- Execute code in isolated environments with sandbox backends
- All standard filesystem tools ( ls , read_file , write_file , edit_file , glob , grep )
- The execute tool for running arbitrary shell commands in the sandbox
- A secure boundary that protects your host system
- Coding agents: Agents that run autonomously can use shell, git, clone repositories (many providers offer native git APIs, e.g., Daytona’s git operations ), and run Docker-in-Docker for build and test pipelines
- Data analysis agents—Load files, install data analysis libraries (pandas, numpy, etc.), run statistical calculations, and create outputs like PowerPoint presentations in a safe, isolated environment
- ✅ Mirrors local development closely.
- ✅ Tight coupling between agent and environment.
- 🔴 API keys must live inside the sandbox (security risk).
- 🔴 Updates require rebuilding images.
- 🔴 Requires infrastructure for communication (WebSocket or HTTP layer).
- ✅ Update agent code instantly without rebuilding images.
- ✅ Cleaner separation between agent state and execution.
- API keys stay outside the sandbox.
- Sandbox failures don’t lose agent state.
- Option to run tasks in multiple sandboxes in parallel.
- ✅ Pay only for execution time.
- 🔴 Network latency on each execution call.

### API And Concept Signals
`Agent`, `AgentCore`, `AgentCoreSandbox`, `Agents`, `Context`, `Create`, `DaytonaSandbox`, `E2BSandbox`, `LangSmithSandbox`, `ModalSandbox`, `OpenShellSandbox`, `RunloopSandbox`, `Sandbox`, `SandboxBackendProtocol`, `SandboxClient`, `Sandboxes`, `VercelSandbox`, `agent`, `agentcore`, `agents`, `backend`, `backends`, `bedrock_agentcore`, `client`, `code_interpreter_client`, `context`, `create`, `create_deep_agent`

### Representative Code Signals
```text
pip install "langsmith[sandbox]"
```
```text
from deepagents import create_deep_agent from deepagents . backends import LangSmithSandbox from langchain_anthropic import ChatAnthropic from langsmith . sandbox import SandboxClient client = SandboxClient () ls_sandbox = client . create_sandbox () backend = LangSmithSandbox ( sandbox = ls_sandbox ) agent = create_deep_agent ( model = ChatAnthropic ( model = "claude-sonnet-4-6" ), system_prompt = "You are a Python coding assistant with sandbox access." , backend = backend , ) try : result = agent . invoke ( { "messages" : [ { "role" : "user" , "content" : "Create a small Python package and run pytest" , } ] } ) finally : client . delete_sandbox ( ls_sandbox . name )
```
```text
pip install langchain-daytona
```
```text
from daytona import Daytona from deepagents import create_deep_agent from langchain_anthropic import ChatAnthropic from langchain_daytona import DaytonaSandbox sandbox = Daytona (). create () backend = DaytonaSandbox ( sandbox = sandbox ) agent = create_deep_agent ( model = ChatAnthropic ( model = "claude-sonnet-4-6" ), system_prompt = "You are a Python coding assistant with sandbox access." , backend = backend , ) try : result = agent . invoke ( { "messages" : [ { "role" : "user" , "content" : "Create a small Python package and run pytest" , } ] } ) finally : sandbox . stop ()
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
