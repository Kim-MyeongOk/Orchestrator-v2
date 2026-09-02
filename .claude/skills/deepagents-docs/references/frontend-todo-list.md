# Todo list

Source: https://docs.langchain.com/oss/python/deepagents/frontend/todo-list

## Local Usage Guidance
Use this page for displaying or synchronizing the agent's task plan.
The todo-list pattern shows how a frontend can render the built-in planning state and update users as tasks move through pending, in-progress, and completed states.
Read this when users need visibility into what the agent is doing over a long run.

## Extracted Documentation Content

### Key Sections
-  How it works
-  Setting up useStream
-  Building the TodoList component
-  Progress bar
-  Individual todo items
-  Calculating progress
-  Combining with chat messages
-  Use cases
-  Handling empty and loading states
-  Best practices

### Important Points
- Track agent progress with a real-time todo list synced from agent state
- Agent creates a plan and populates todos in its state
- Agent begins executing each todo transitions through pending → in_progress → completed
- stream.values.todos updates in real time as the agent progresses
- Your UI re-renders the todo list with current statuses
- Project planning : agent breaks a project into tasks and works through them sequentially
- Research workflows : each research question becomes a todo that the agent investigates and completes
- Data processing : steps like ingestion, validation, transformation, and export each get their own todo
- Onboarding flows : agent walks through setup steps, checking off each one as it configures services
- Report generation : sections of a report become todos: gather data, analyze trends, write summary, format output
- Show the todo list prominently . It’s the primary progress indicator for plan-based agents. Don’t bury it below the fold.
- Animate status transitions . Smooth transitions make the agent feel more responsive. Use CSS transitions on background color, text decoration, and opacity.
- Only highlight one in_progress item . Agents typically work on one task at a time. If multiple items show as in_progress , the UI gets noisy. Consider only pulsing the first one.
- Collapse or dim completed items . As the list grows, completed items become less relevant. Reduce their visual weight so users focus on what’s still happening.
- Show the progress percentage . A single number like “67% complete” is immediately understandable, even from across the room.
- Keep the todo list in sync . Because stream.values updates reactively, the todo list stays current automatically. Don’t add manual polling or refresh logic.

### API And Concept Signals
`AGENT_URL`, `Agent`, `Agents`, `Todo`, `TodoAgent`, `TodoAgentLayout`, `TodoItem`, `TodoList`, `agent`, `agents`, `creates`, `deep_agent_todo_list`, `myAgent`, `state`, `states`, `stream`, `task`, `tasks`, `todo`, `todos`, `useStream`

### Representative Code Signals
```text
import { useStream } from "@langchain/react" ; const AGENT_URL = "http://localhost:2024" ; export function TodoAgent () { const stream = useStream < typeof myAgent > ( { apiUrl : AGENT_URL , assistantId : "deep_agent_todo_list" , } ) ; const todos = stream . values ?. todos ?? [] ; return ( < div > < TodoList todos = { todos } /> { stream . messages . map ( ( msg ) => ( < Message key = { msg . id } message = { msg } /> )) } </ div > ) ; }
```
```text
function TodoList ({ todos } : { todos : Todo[] }) { const completed = todos . filter ( ( t ) => t . status === "completed" ) . length ; const percentage = todos . length ? Math . round ((completed / todos . length) * 100 ) : 0 ; return ( < div className = "rounded-lg border bg-white p-4 shadow-sm" > < div className = "mb-4 flex items-center justify-between" > < h2 className = "text-lg font-semibold" > Agent Progress </ h2 > < span className = "text-sm text-gray-500" > { completed } / { todos . length } tasks </ span > </ div > < ProgressBar percentage = { percentage } /> < ul className = "mt-4 space-y-2" > { todos . map ( ( todo , i ) => ( < TodoItem key = { i } todo = { todo } /> )) } </ ul > </ div > ) ; }
```
```text
function ProgressBar ({ percentage } : { percentage : number }) { return ( < div className = "space-y-1" > < div className = "flex items-center justify-between text-xs text-gray-500" > < span > Progress </ span > < span > { percentage } % </ span > </ div > < div className = "h-2 overflow-hidden rounded-full bg-gray-200" > < div className = "h-full rounded-full bg-green-500 transition-all duration-500" style = {{ width : ` ${ percentage } %` }} /> </ div > </ div > ) ; }
```
```text
function TodoItem ({ todo } : { todo : Todo }) { const config = { pending : { icon : "○" , textClass : "text-gray-600" , bgClass : "bg-gray-50" , iconClass : "text-gray-400" , }, in_progress : { icon : "◉" , textClass : "text-amber-800" , bgClass : "bg-amber-50 border-amber-200" , iconClass : "text-amber-500 animate-pulse" , }, completed : { icon : "✓" , textClass : "text-green-800 line-through" , bgClass : "bg-green-50 border-green-200" , iconClass : "text-green-500" , }, }; const style = config[todo . status] ; return ( < li className = { `flex items-start gap-3 rounded-md border px-3 py-2 ${ style . bgClass } ` } > < span className = { `mt-0.5 text-lg leading-none ${ style . iconClass } ` } > { style . icon } </ span > < span className = { `text-sm ${ style . textClass } ` } > { todo . content } </ span > </ li > ) ; }
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
