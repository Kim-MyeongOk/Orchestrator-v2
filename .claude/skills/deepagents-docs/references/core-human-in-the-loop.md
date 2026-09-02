# Human-in-the-loop

Source: https://docs.langchain.com/oss/python/deepagents/human-in-the-loop

## Local Usage Guidance
Use this page for approvals, interrupts, and user confirmation workflows.
Read this before implementing approval gates or interrupt policies.

## Extracted Documentation Content

### Key Sections
-  Basic configuration
-  Decision types
-  Conditional interrupts
-  Handle interrupts
-  Multiple tool calls
-  Rejection messages
-  Edit tool arguments
-  Subagent interrupts
-  Interrupts on tool calls
-  Interrupts within tool calls
-  Filesystem permission interrupts
-  Best practices
-  Always use a checkpointer
-  Use the same thread ID
-  Match decision order to actions
-  Tailor configurations by risk

### Important Points
- Learn how to configure human approval for sensitive tool operations
- True : Enable interrupts with default behavior (approve, edit, reject, respond allowed)
- False : Disable interrupts for this tool
- InterruptOnConfig : Custom configuration. Set allowed_decisions to control review options. In Python, add an optional when predicate to interrupt only specific calls (see Conditional interrupts ).

### Extracted Table/Field Signals
- Decision Type
- Description
- Example Use Case
- ✅ approve
- Execute the tool with the original arguments as proposed by the agent.
- Send an email draft exactly as written
- ✏️ edit
- Modify the tool arguments before execution.
- Change the recipient before sending an email
- ❌ reject
- Skip executing this tool call entirely and return rejection feedback to the agent.
- Deny file deletion and explain why
- 💬 respond
- Return the human’s message directly as a synthetic tool result, skipping execution, for “ask user” style tools.
- Answer an "ask_user" prompt with a direct reply

### API And Concept Signals
`CompiledSubAgent`, `Create`, `Filesystem`, `FilesystemPermission`, `InMemorySaver`, `Interrupt`, `InterruptOnConfig`, `Interrupts`, `Invoke`, `MemorySaver`, `Subagent`, `Tool`, `ToolCallRequest`, `agent`, `agents`, `compiled_subagent`, `create_agent`, `create_deep_agent`, `deepagents`, `delete_file`, `fetch_file`, `file`, `file_path`, `filesystem`, `interrupt`, `interrupt_on`, `interrupt_value`, `interrupted`

### Representative Code Signals
```text
from langchain . tools import tool from deepagents import create_deep_agent from langgraph . checkpoint . memory import MemorySaver @tool def remove_file ( path : str ) -> str : """Delete a file from the filesystem.""" return f "Deleted { path } " @tool def fetch_file ( path : str ) -> str : """Read a file from the filesystem.""" return f "Contents of { path } " @tool def notify_email ( to : str , subject : str , body : str ) -> str : """Send an email.""" return f "Sent email to { to } " # Checkpointer is REQUIRED for human-in-the-loop checkpointer = MemorySaver () agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , tools = [ remove_file , fetch_file , notify_email ], interrupt_on = { "remove_file" : True , # Default: approve, edit, reject, respond "fetch_file" : False , # No interrupts needed "notify_email" : { "allowed_decisions" : [ "approve" , "reject" ]}, # No edit
```
```text
interrupt_on = { # Sensitive operations: allow all options "delete_file" : { "allowed_decisions" : [ "approve" , "edit" , "reject" ]}, # Moderate risk: approval or rejection only "write_file" : { "allowed_decisions" : [ "approve" , "reject" ]}, # Must approve (no rejection allowed) "critical_operation" : { "allowed_decisions" : [ "approve" ]}, }
```
```text
from deepagents import create_deep_agent from langchain . agents . middleware import ToolCallRequest from langgraph . checkpoint . memory import MemorySaver def writes_outside_workspace ( request : ToolCallRequest ) -> bool : """Pause writes to paths outside the workspace directory.""" path = request . tool_call [ " args " ]. get ( "file_path" , "" ) return not path . startswith ( "/workspace/" ) agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , interrupt_on = { "write_file" : { "allowed_decisions" : [ "approve" , "edit" , "reject" ], "when" : writes_outside_workspace , }, }, checkpointer = MemorySaver (), )
```
```text
from langchain_core . utils . uuid import uuid7 from langgraph . types import Command # Create config with thread_id for state persistence config = { "configurable" : { "thread_id" : str ( uuid7 ())}} # Invoke the agent result = agent . invoke ( { "messages" : [{ "role" : "user" , "content" : "Delete the file temp.txt" }]}, config = config , version = "v2" , ) # Check if execution was interrupted if result . interrupts : # Extract interrupt information interrupt_value = result . interrupts [ 0 ]. value action_requests = interrupt_value [ " action_requests " ] review_configs = interrupt_value [ " review_configs " ] # Create a lookup map from tool name to review config config_map = { cfg [ " action_name " ]: cfg for cfg in review_configs } # Display the pending actions to the user for action in action_requests : review_config = config_map [ action [ " name " ]] print ( f "Tool: { action [ 
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
