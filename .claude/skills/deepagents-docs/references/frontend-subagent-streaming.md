# Subagent streaming

Source: https://docs.langchain.com/oss/python/deepagents/frontend/subagent-streaming

## Local Usage Guidance
Use this page when a frontend must show delegated subagent work.
Read this when building UIs for parallel research, background workers, or task trees.

## Extracted Documentation Content

### Key Sections
-  Why selector-based subagent streams
-  Setting up useStream
-  Submitting messages
-  The SubagentDiscoverySnapshot
-  Building the SubagentCard
-  Progress tracking
-  Rendering messages with subagent cards
-  Best practices

### Important Points
- Display specialist subagents with streaming content, progress tracking, and collapsible cards
- stream.messages contains only the coordinator’s messages
- stream.subagents contains discovery snapshots with identity, namespace, and status
- Each subagent’s messages, tool calls, and values are read with selector helpers
- The UI stays clean: the coordinator’s reasoning is separate from the specialists’ work
- Mount selectors only where needed . Scoped messages and tool calls stream when a card calls useMessages(stream, subagent) or useToolCalls(stream, subagent) .
- Show specialist names . subagent.name tells users which worker is active.
- Use collapsible cards . In workflows with 5+ subagents, auto-collapse completed cards so users can focus on active work.
- Override recursion only when needed . Deep Agents sets a high default recursion limit; pass config.recursion_limit only for unusually deep custom workflows.
- Handle errors per subagent . One subagent failing shouldn’t crash the entire UI. Show the error in that subagent’s card while others continue running.

### API And Concept Signals
`AGENT_URL`, `Agents`, `AnyStream`, `DeepAgentChat`, `DeepAgentLayout`, `Subagent`, `SubagentCard`, `SubagentDiscoverySnapshot`, `SubagentProgress`, `deep_agent_subagent_cards`, `myAgent`, `stream`, `streaming`, `streams`, `subagent`, `subagents`, `subagentsByCallId`, `tool`, `toolCalls`, `tool_calls`, `turnSubagents`, `useState`, `useStream`, `useToolCalls`

### Representative Code Signals
```text
import { useStream } from "@langchain/react" ; import { AIMessage , HumanMessage } from "langchain" ; const AGENT_URL = "http://localhost:2024" ; export function DeepAgentChat () { const stream = useStream < typeof myAgent > ( { apiUrl : AGENT_URL , assistantId : "deep_agent_subagent_cards" , } ) ; const subagents = [ ... stream . subagents . values ()] ; const subagentsByCallId = new Map (subagents . map ( ( s ) => [s . id , s])) ; return ( < div > { stream . messages . map ( ( msg ) => { const turnSubagents = AIMessage . isInstance (msg) ? (msg . tool_calls ?? []) . map ( ( tc ) => subagentsByCallId . get (tc . id ?? "" )) . filter ( ( s ) : s is NonNullable < typeof s > => !! s) : [] ; return ( < div key = { msg . id } > { HumanMessage . isInstance (msg) && < HumanBubble > { msg . text } </ HumanBubble > } { AIMessage . isInstance (msg) && msg . text . trim () && ( < AIBubble > { msg 
```
```text
stream . submit ( { messages : [ { type : "human" , content : text } ] }, { config : { recursion_limit : 100 } } ) ;
```
```text
import { useState } from "react" ; import { AIMessage } from "langchain" ; import { useMessages , useToolCalls , type AnyStream , type SubagentDiscoverySnapshot , } from "@langchain/react" ; function SubagentCard ({ stream , subagent , } : { stream : AnyStream ; subagent : SubagentDiscoverySnapshot ; }) { const [ expanded , setExpanded ] = useState ( true ) ; const messages = useMessages (stream , subagent) ; const toolCalls = useToolCalls (stream , subagent) ; const lastAIMessage = messages . filter (AIMessage . isInstance) . at ( - 1 ) ; const displayContent = lastAIMessage ?. text ?? subagent . output ?? "" ; return ( < div className = "rounded-lg border bg-white shadow-sm" > < button onClick = {() => setExpanded ( ! expanded) } className = "flex w-full items-center justify-between p-4" > < div className = "flex items-center gap-3" > < StatusIcon status = { subagent . status } /> < di
```
```text
function SubagentProgress ({ subagents , } : { subagents : SubagentDiscoverySnapshot[] ; }) { const completed = subagents . filter ( ( s ) => s . status === "complete" ) . length ; const total = subagents . length ; const percentage = total > 0 ? Math . round ((completed / total) * 100 ) : 0 ; return ( < div className = "space-y-1" > < div className = "flex items-center justify-between text-xs text-gray-500" > < span > Subagent progress </ span > < span > { completed } / { total } complete </ span > </ div > < div className = "h-2 overflow-hidden rounded-full bg-gray-200" > < div className = "h-full rounded-full bg-blue-500 transition-all duration-300" style = {{ width : ` ${ percentage } %` }} /> </ div > </ div > ) ; }
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
