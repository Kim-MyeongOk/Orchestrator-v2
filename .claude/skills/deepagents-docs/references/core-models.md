# Models

Source: https://docs.langchain.com/oss/python/deepagents/models

## Local Usage Guidance
Use this page when configuring model providers and model parameters.
Read this when choosing a model, setting provider parameters, registering profiles, or swapping models at runtime.

## Extracted Documentation Content

### Key Sections
-  Supported models
-  Suggested models
-  Model evaluations
-  Configure model parameters
-  Provider profiles
-  Select a model at runtime
-  Learn more

### Important Points
- Configure model providers and parameters for Deep Agents
- Provider level — a bare provider key like "openai" applies to every model from the openai provider.
- Model level — a provider:model key like "openai:gpt-5.4" applies only to that specific model, and merges on top of any matching provider-level profile.
- Models in LangChain : chat model features including tool calling, structured output, and multimodality

### Extracted Table/Field Signals
- Provider
- Models
- Google
- gemini-3.1-pro-preview , gemini-3.5-flash
- OpenAI
- gpt-5.5 , gpt-5.4
- Anthropic
- claude-opus-4-8 , claude-opus-4-7 , claude-opus-4-6
- Open-weight
- GLM-5.2 , Kimi-K2.7 Code , MiniMax-M3
- Model
- Overall
- File Ops
- Retrieval
- Tool Use
- Memory
- Conversation
- Summarization
- google_genai:gemini-3.5-flash
- 82%
- 100%
- 90%
- 54%
- 38%

### API And Concept Signals
`Agents`, `Context`, `File`, `Invoke`, `Memory`, `Model`, `ModelRequest`, `ModelResponse`, `Models`, `ProviderProfile`, `Tool`, `agent`, `agents`, `chat_models`, `configurable_model`, `context`, `context_schema`, `create_deep_agent`, `deepagents`, `init_chat_model`, `invoke`, `middleware`, `model`, `model_name`, `models`, `profile`, `profiles`, `register_provider_profile`

### Representative Code Signals
```text
from langchain . chat_models import init_chat_model from deepagents import create_deep_agent model = init_chat_model ( model = "google_genai:gemini-3.5-flash" , thinking_level = "medium" , ) agent = create_deep_agent ( model = model )
```
```text
from deepagents import ProviderProfile , register_provider_profile # Provider-wide default: every openai model gets temperature=0. register_provider_profile ( "openai" , ProviderProfile ( init_kwargs = { "temperature" : 0 }), ) # Model-level override: gpt-5.5 additionally gets a specific reasoning effort. # Inherits temperature=0 from the provider-level profile above. register_provider_profile ( "openai:gpt-5.5" , ProviderProfile ( init_kwargs = { "reasoning_effort" : "medium" }), )
```
```text
from dataclasses import dataclass from langchain . chat_models import init_chat_model from langchain . agents . middleware import wrap_model_call , ModelRequest , ModelResponse from deepagents import create_deep_agent from typing import Callable @dataclass class Context : model : str @wrap_model_call def configurable_model ( request : ModelRequest , handler : Callable [[ ModelRequest ], ModelResponse ], ) -> ModelResponse : model_name = request . runtime . context . model model = init_chat_model ( model_name ) return handler ( request . override ( model = model )) agent = create_deep_agent ( model = "google_genai:gemini-3.5-flash" , middleware = [ configurable_model ], context_schema = Context , ) # Invoke with the user's model selection result = agent . invoke ( { "messages" : [{ "role" : "user" , "content" : "Hello!" }]}, context = Context ( model = "openai:gpt-5.5" ), )
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
