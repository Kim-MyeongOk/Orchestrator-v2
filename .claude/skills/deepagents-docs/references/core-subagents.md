# Subagents

Source: https://docs.langchain.com/oss/python/deepagents/subagents

## Local Usage Guidance
Use this page for delegated work and custom child agents.
Read this when the user asks about main-agent versus subagent responsibilities, parallel research, specialized workers, or tool permissions per subagent.

## Extracted Documentation Content

### Key Sections
-  Why use subagents?
-  Configuration
-  Default subagent
-  Running without subagents
-  Custom subagents
-  SubAgent (Dictionary-based)
-  CompiledSubAgent
-  Using SubAgent
-  Using CompiledSubAgent
-  Dynamic subagents
-  Enable dynamic subagents
-  Trigger dynamic orchestration
-  Use with a coding agent
-  Streaming
-  Stream subagent progress
-  LangSmith tracing
-  Filter by subagent in LangSmith
-  Filter in the LangSmith UI
-  Filter programmatically with the SDK
-  Structured output

### Important Points
- Learn how to use subagents to delegate work and keep context clean
- ✅ Multi-step tasks that would clutter the main agent’s context
- ✅ Specialized domains that need custom instructions or tools
- ✅ Tasks requiring different model capabilities
- ✅ When you want to keep the main agent focused on high-level coordination
- ❌ Simple, single-step tasks
- ❌ When you need to maintain intermediate context
- ❌ When the overhead outweighs benefits
- To replace it, pass your own subagent named general-purpose .
- To rename or re-prompt the auto-added version, set general_purpose_subagent=GeneralPurposeSubagentProfile(...) on the active harness profile .
- To disable it, see Running without subagents below.
- Set general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False) on the active harness profile .
- Pass no synchronous subagents via subagents= on create_deep_agent .
- Open your tracing project in LangSmith .
- Switch the view to Runs on the Tracing project page to see individual spans.
- Click Add filter and select Metadata .
- Set the Key to lc_agent_name and the Value to the subagent name, for example coordinator .
- Uses its own default system prompt with profile overlays applied

### Extracted Table/Field Signals
- Field
- Type
- Description
- name
- str
- description
- Required. Description of what this subagent does. Be specific and action-oriented. The main agent uses this to decide when to delegate.
- system_prompt
- tools
- list[Callable]
- model
- str | BaseChatModel
- middleware
- list[Middleware]
- Optional. Additional middleware for custom behavior, logging, or rate limiting. Does not inherit from the main agent. Appended to the default subagent stack .
- interrupt_on
- dict[str, bool | InterruptOnConfig]
- skills
- list[str]
- response_format
- ResponseFormat
- permissions
- list[FilesystemPermission]
- Optional. Filesystem permission rules for the subagent. When set, replaces the parent agent’s permissions entirely. Inherits from main agent by default.

### API And Concept Signals
`BaseChatModel`, `BaseModel`, `Client`, `CodeInterpreterMiddleware`, `CompiledSubAgent`, `Context`, `Create`, `Filesystem`, `FilesystemPermission`, `GeneralPurposeSubagentProfile`, `InterruptOnConfig`, `Middleware`, `Skill`, `Skills`, `SkillsMiddleware`, `Stream`, `Streaming`, `SubAgent`, `Subagent`, `Subagents`, `Tasks`, `TavilyClient`, `ToolMessage`, `ToolRuntime`, `ToolStrategy`, `Tools`, `agent`, `agent_name`

### Representative Code Signals
```text
import os from typing import Literal from deepagents import create_deep_agent from tavily import TavilyClient tavily_client = TavilyClient ( api_key = os . environ [ " TAVILY_API_KEY " ]) def internet_search ( query : str , max_results : int = 5 , topic : Literal [ " general " , " news " , " finance " ] = "general" , include_raw_content : bool = False , ): """Run a web search""" return tavily_client . search ( query , max_results = max_results , include_raw_content = include_raw_content , topic = topic , ) research_subagent = { "name" : "research-agent" , "description" : "Used to research more in depth questions" , "system_prompt" : "You are a great researcher" , "tools" : [ internet_search ], "model" : "openai:gpt-5.5" , # Optional override, defaults to main agent model } subagents = [ research_subagent ] agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , subagents = 
```
```text
from deepagents import create_deep_agent , CompiledSubAgent from langchain . agents import create_agent # Create a custom agent graph custom_graph = create_agent ( model = your_model , tools = specialized_tools , prompt = "You are a specialized agent for data analysis..." ) # Use it as a custom subagent custom_subagent = CompiledSubAgent ( name = "data-analyzer" , description = "Specialized agent for complex data analysis tasks" , runnable = custom_graph ) subagents = [ custom_subagent ] agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , tools = [ internet_search ], system_prompt = research_instructions , subagents = subagents )
```
```text
pip install -U "deepagents[quickjs]"
```
```text
from deepagents import create_deep_agent from langchain_quickjs import CodeInterpreterMiddleware agent = create_deep_agent ( model = "openai:gpt-5.5" , subagents = [{ "name" : "reviewer" , "description" : "Reviews code for security issues, citing lines and severity" , "system_prompt" : "You are a security-focused code reviewer. Report issues with line numbers and severity." , }], middleware = [ CodeInterpreterMiddleware ()], )
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
