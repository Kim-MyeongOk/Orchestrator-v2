# Deep Agents overview

Source: https://docs.langchain.com/oss/python/deepagents/overview

## Local Usage Guidance
Use this page when you need the high-level mental model for Deep Agents.
The overview frames Deep Agents as an agent harness built on LangChain and LangGraph for complex multi-step tasks. It highlights built-in support for task planning, virtual filesystem access, tool use, MCP, context management, skills, memory, subagents, streaming, human-in-the-loop control, and production-oriented execution patterns.
Read this first when a user asks what Deep Agents is, why it exists, which features are built in, or how it differs from a raw LangChain or LangGraph agent.

## Extracted Documentation Content

### Key Sections
-  Quickstart
-  Core capabilities
- Execution environment
- Context management
- Delegation
- Steering
-  Execution environment
-  Tools and MCP
-  Virtual filesystem access
-  Filesystem permissions
-  Code execution
-  Streaming
-  Context management
-  Skills
-  Memory
-  Summarization and context offloading
-  Prompt caching
-  Delegation
-  Task planning
-  Subagents

### Important Points
- Build agents that can plan, use subagents, and leverage file systems for complex tasks
- Take actions in an environment : Take actions via tools, read and write files, execute code
- Connect to your data : Load memories, skills, and domain knowledge at the right moment
- Manage growing context : Summarize history and offload large results across long runs
- Parallelize tasks : Delegate to general or specialized subagents running in isolated context windows
- Stay in the loop : Pause for human approval at critical decision points
- Improve over time : Update memory, skills, and prompts based on real usage
- Tools : custom functions, APIs, and databases the agent can call
- Virtual filesystem : file tools backed by pluggable backends
- Filesystem permissions : declarative access control over which paths agents can read or write
- Code execution : sandboxed shell execution and an in-process JavaScript interpreter
- Supported multimodal file extensions
- Running without the default filesystem tools
- operations : "read" and/or "write"
- paths : Glob patterns for files or directories
- Sandbox backends expose an execute tool for shell commands in an isolated environment.
- Interpreters add an eval tool that runs JavaScript in a scoped QuickJS runtime.
- Skills : on-demand domain knowledge loaded progressively from skill files

### Extracted Table/Field Signals
- Tool
- Description
- List files in a directory with metadata (size, modified time)
- read_file
- write_file
- Create new files
- edit_file
- Perform exact string replacements in files (with global replace mode)
- glob
- Find files matching patterns (e.g., **/*.py )
- grep
- Search file contents with multiple output modes (files only, content with context, or counts)
- execute
- Run shell commands in the environment (available with sandbox backends only)
- Type
- Extensions
- Image
- .png , .jpg , .jpeg , .gif , .webp , .heic , .heif
- Video
- .mp4 , .mpeg , .mov , .avi , .flv , .mpg , .webm , .wmv , .3gpp
- Audio
- .wav , .mp3 , .aiff , .aac , .ogg , .flac
- File
- .pdf , .ppt , .pptx

### API And Concept Signals
`AGENTS`, `Agents`, `Context`, `Create`, `File`, `Filesystem`, `HarnessProfile`, `MCP`, `Memory`, `Sandbox`, `Skills`, `Stateless`, `Streaming`, `Subagents`, `Task`, `Tool`, `Tools`, `agent`, `agents`, `backends`, `context`, `create_deep_agent`, `creates`, `deepagents`, `edit_file`, `excluded_tools`, `file`, `files`

### Representative Code Signals
```text
# pip install -qU deepagents langchain-google-genai from deepagents import create_deep_agent def get_weather ( city : str ) -> str : """Get weather for a given city.""" return f "It's always sunny in { city } !" agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , tools = [ get_weather ], system_prompt = "You are a helpful assistant" , ) # Run the agent agent . invoke ( { "messages" : [{ "role" : "user" , "content" : "what is the weather in sf" }]} )
```
```text
# pip install -qU deepagents langchain-openai from deepagents import create_deep_agent def get_weather ( city : str ) -> str : """Get weather for a given city.""" return f "It's always sunny in { city } !" agent = create_deep_agent ( model = "openai:gpt-5.5" , tools = [ get_weather ], system_prompt = "You are a helpful assistant" , ) # Run the agent agent . invoke ( { "messages" : [{ "role" : "user" , "content" : "what is the weather in sf" }]} )
```
```text
# pip install -qU deepagents langchain-anthropic from deepagents import create_deep_agent def get_weather ( city : str ) -> str : """Get weather for a given city.""" return f "It's always sunny in { city } !" agent = create_deep_agent ( model = "anthropic:claude-sonnet-4-6" , tools = [ get_weather ], system_prompt = "You are a helpful assistant" , ) # Run the agent agent . invoke ( { "messages" : [{ "role" : "user" , "content" : "what is the weather in sf" }]} )
```
```text
# pip install -qU deepagents langchain-openrouter from deepagents import create_deep_agent def get_weather ( city : str ) -> str : """Get weather for a given city.""" return f "It's always sunny in { city } !" agent = create_deep_agent ( model = "openrouter:anthropic/claude-sonnet-4-6" , tools = [ get_weather ], system_prompt = "You are a helpful assistant" , ) # Run the agent agent . invoke ( { "messages" : [{ "role" : "user" , "content" : "what is the weather in sf" }]} )
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
