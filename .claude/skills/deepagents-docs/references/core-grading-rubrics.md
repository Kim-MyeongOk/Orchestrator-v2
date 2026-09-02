# Grading rubrics

Source: https://docs.langchain.com/oss/python/deepagents/rubric

## Local Usage Guidance
Use this page for evaluating agent behavior with rubrics.
Read this when the user asks how to evaluate Deep Agents objectively.

## Extracted Documentation Content

### Key Sections
-  Configure the middleware
-  Pass rubric on invocation
-  Rubric verdicts
-  Observe iteration progress
-  Grader pass events
-  Persist rubrics across invocations
-  Example: generate vetted Python code

### Important Points
- LLM-as-a-judge grading for agents that iterate against a rubric until done
- grading_run_id : shared across all events within one rubric attempt
- iteration : zero-based index of the current grading run
- iteration : zero-based index of the current grader pass
- result : terminal verdict for this pass
- explanation : summary from the grader
- criteria : per-criterion verdicts
- Invoke with a human message and rubric

### Extracted Table/Field Signals
- Argument
- Required
- Default
- Description
- model
- Yes
- None
- system_prompt
- Built-in grader prompt
- Custom grading instructions. Falls back to a default system prompt that teaches the grader the verdict format and what tools it has at its disposal.
- tools
- max_iterations
- on_evaluation
- Event
- When fired
- Payload fields
- rubric_evaluation_start
- Before the grader runs.
- rubric_evaluation_end
- After the grader returns or after a grader exception.
- Status
- Meaning
- Loops back?
- satisfied

### API And Concept Signals
`BaseChatModel`, `InMemorySaver`, `Invoke`, `RubricMiddleware`, `Tools`, `agent`, `agents`, `create_deep_agent`, `deepagents`, `files`, `invoke`, `invoked`, `memory`, `middleware`, `model`, `rubric_middleware`, `state`, `stream`, `stream_events`, `tool`, `tools`

### Representative Code Signals
```text
from deepagents import RubricMiddleware , create_deep_agent from langgraph . checkpoint . memory import InMemorySaver agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , middleware = [ RubricMiddleware ( model = "anthropic:claude-haiku-4-5" , max_iterations = 3 , ), ], checkpointer = InMemorySaver (), )
```
```text
from langchain . messages import HumanMessage config = { "configurable" : { "thread_id" : "my-rubric-thread" }} result = agent . invoke ( { "messages" : [ HumanMessage ( "Write a haiku about spring." )], "rubric" : ( "- The poem has three lines \n " "- Lines follow a 5-7-5 syllable pattern \n " "- The theme is spring" ), }, config = config , )
```
```text
from langchain . messages import HumanMessage from langgraph . stream import CustomTransformer config = { "configurable" : { "thread_id" : "my-rubric-thread" }} stream = agent . stream_events ( { "messages" : [ HumanMessage ( "Write a haiku about spring." )], "rubric" : ( "- The poem has three lines \n " "- Lines follow a 5-7-5 syllable pattern \n " "- The theme is spring" ), }, config = config , version = "v3" , transformers = [ CustomTransformer ], ) for event in stream . custom : event_type = event . get ( "type" ) if event_type == "rubric_evaluation_start" : print ( f "Grading iteration { event [ ' iteration ' ] } " f "(run { event [ ' grading_run_id ' ] } )" ) elif event_type == "rubric_evaluation_end" : print ( f "Verdict: { event [ ' result ' ] } — { event . get ( 'explanation' , '' ) } " )
```
```text
from deepagents import RubricMiddleware , create_deep_agent from deepagents . middleware . rubric import RubricEvaluation from langchain . messages import HumanMessage from langgraph . checkpoint . memory import InMemorySaver def log_evaluation ( ev : RubricEvaluation ) -> None : print ( f "iteration { ev [ ' iteration ' ] } : { ev [ ' result ' ] } — { ev [ ' explanation ' ] } " ) agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , middleware = [ RubricMiddleware ( model = "anthropic:claude-haiku-4-5" , on_evaluation = log_evaluation , ), ], checkpointer = InMemorySaver (), ) config = { "configurable" : { "thread_id" : "rubric-eval-session" }} agent . invoke ( { "messages" : [ HumanMessage ( "Write a one-sentence summary of photosynthesis." )], "rubric" : ( "- The answer is one sentence \n " "- The answer mentions light and chlorophyll" ), }, config = config , )
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
