# Skills

Source: https://docs.langchain.com/oss/python/deepagents/skills

## Local Usage Guidance
Use this page when creating, installing, loading, or using skills with Deep Agents.
Read this when building skill folders, designing `SKILL.md`, deciding what belongs in `references/`, or explaining skill discovery.

## Extracted Documentation Content

### Key Sections
-  Usage
-  How skills work
-  When to use skills
-  Write effective skills
-  Add supporting resources
-  scripts/
-  references/
-  assets/
-  Reference files from SKILL.md
-  Backends and remote skill loading
-  Load skills at runtime
-  Dynamic skill lists
-  Namespaced skills
-  Skills for subagents
-  Skill permissions
-  Share skills across users
-  Limit skills by user context
-  Enforce read-only skills
-  Require approval for skill writes
-  Allow agents to edit personal skills

### Important Points
- Learn how to extend your deep agent’s capabilities with skills
- Create a top-level skills directory
- Create a subdirectory inside your skills directory for your skill
- Add a `SKILL.md` file with YAML frontmatter and instructions.
- Pass the skills path when creating your agent
- If omitted, no skills are loaded.
- When using StateBackend (default), provide skill files with invoke(files={...}) . Use create_file_data() from deepagents.backends.utils to format file contents; raw strings are not supported.
- With FilesystemBackend , skills are loaded from disk relative to the backend’s root_dir .
- Discovery (level 1): At agent start, the middleware scans the configured skill paths, parses each SKILL.md frontmatter , and injects the name and description fields into the system prompt.
- Read (level 2): When the agent invokes a skill, it reads the full SKILL.md content via read_file .
- Execute (level 3): After invocation, the agent follows the skill’s instructions and reads supporting files (scripts, references, assets) only as the instructions require.
- Step-by-step workflows : Workflows that span multiple steps, similar to recipes.
- Domain-specific knowledge : Instruct the agent on how to use tools for the workflow. For example, include information on where to pull information from, including other reference information or scripts that the skill may have access to.
- Instructions with executable code : Bundle procedures with scripts or modules the agent can run, so it follows tested logic instead of regenerating it from instructions each time. See Execute code with skills .
- Guidelines : Provide the agent with supporting instructions about guardrails to adhere to. For example, following a specific format or style guide, or specifying to always run tests as part of the workflow.
- Step-by-step procedures for multi-step workflows
- Decision criteria for choosing between approaches
- Examples of expected inputs and outputs so the agent knows what success looks like

### Extracted Table/Field Signals
- Level
- What loads
- When
- 1. Metadata
- name and description from SKILL.md frontmatter
- Agent startup, for every configured skill
- 2. Instructions
- Full SKILL.md body
- When the skill is invoked
- 3. Resources
- Supporting files under scripts/ , references/ , and assets/
- As needed after invocation, when the instructions reference them
- Skills
- Memory
- Tools
- Purpose
- On-demand capabilities discovered through progressive disclosure
- Persistent context loaded at startup
- Programmatic actions the agent can call
- Loading
- Read only when the agent determines relevance
- Loaded at agent start
- Available every turn
- Format

### API And Concept Signals
`AGENTS`, `Agent`, `AgentMiddleware`, `AgentState`, `Agents`, `Backends`, `CompositeBackend`, `Context`, `Create`, `File`, `FilesystemBackend`, `FilesystemPermission`, `InMemoryStore`, `Invoke`, `LangSmithSandbox`, `Memory`, `MemorySaver`, `SKILL`, `SKILLS_BY_ROLE`, `SKILLS_SHARED_NAMESPACE`, `Sandbox`, `SandboxClient`, `Skill`, `SkillSandboxSyncMiddleware`, `Skills`, `State`, `StateBackend`, `StoreBackend`

### Representative Code Signals
```text
--- name : langgraph-docs description : Use this skill for requests related to LangGraph in order to fetch relevant documentation to provide accurate, up-to-date guidance. --- # langgraph-docs ## Overview This skill explains how to access LangGraph documentation to help answer questions and guide implementation. ## Instructions ### 1. Fetch the documentation index Use the fetch_url tool to read the following URL: https://docs.langchain.com/llms.txt This provides a structured list of all available documentation with descriptions. ### 2. Select relevant documentation Based on the question, identify 2-4 most relevant documentation URLs from the index. Prioritize: - Specific how-to guides for implementation questions - Core concept pages for understanding questions - Tutorials for end-to-end examples - Reference docs for API details ### 3. Fetch and synthesize Use the fetch_url tool to read 
```
```text
from deepagents import create_deep_agent from deepagents . backends . filesystem import FilesystemBackend backend = FilesystemBackend ( root_dir = "./my-project" ) agent = create_deep_agent ( model = "anthropic:claude-sonnet-4-6" , backend = backend , skills = [ "./my-project/skills/" ], )
```
```text
result = agent . invoke ( { "messages" : [{ "role" : "user" , "content" : "What is LangGraph?" }]}, config = { "configurable" : { "thread_id" : "1" }}, )
```
```text
# Good: specific about what and when description : >- Extract text and tables from PDF files, fill PDF forms, and merge multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction. # Poor: too vague for reliable matching description : Helps with PDFs.
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
