# Dynamic subagents

Source: https://docs.langchain.com/oss/python/deepagents/dynamic-subagents

## Local Usage Guidance
Use this page when subagents should be created or selected dynamically at runtime.
Read this for advanced delegation patterns beyond static subagent definitions.

## Extracted Documentation Content

### Key Sections
-  Quickstart
-  Use with a coding agent
-  How it works
-  Patterns
-  Classify and act
-  Fan-out and synthesize
-  Adversarial verification
-  Generate and filter
-  Tournament
-  Loop until done
-  Disable dynamic subagents
-  See also

### Important Points
- Use interpreters to dispatch and orchestrate Deep Agents subagents from code
- description : The prompt for the subagent
- subagentType : Which configured subagent to run
- responseSchema (optional): Structured output
- Example: fan-out and synthesize
- Example: adversarial verification
- Example: generate and filter
- Interpreters : QuickJS setup, programmatic tool calling, persistence, security, and middleware configuration
- Subagents : Configure subagent names, descriptions, and system prompts
- Event streaming : Stream updates from the coordinator and delegated subagents

### API And Concept Signals
`Agents`, `CodeInterpreterMiddleware`, `Stream`, `Subagents`, `agent`, `create_deep_agent`, `deepagents`, `file`, `files`, `invoke`, `middleware`, `model`, `streaming`, `subagent`, `subagentType`, `subagents`, `task`, `tool`, `tools`

### Representative Code Signals
```text
from deepagents import create_deep_agent from langchain_quickjs import CodeInterpreterMiddleware agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , subagents = [{ "name" : "reviewer" , "description" : "Reviews code for security issues, citing lines and severity" , "system_prompt" : "You are a security-focused code reviewer. Report issues with line numbers and severity." , }], middleware = [ CodeInterpreterMiddleware ()], )
```
```text
result = agent . invoke ({ "messages" : [{ "role" : "user" , "content" : "Run a workflow that reviews every file in src/routes/ and summarizes the top risks." }] })
```
```text
curl -LsSf https://langch.in/dcode | bash
```
```text
dcode
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
