# Profiles

Source: https://docs.langchain.com/oss/python/deepagents/profiles

## Local Usage Guidance
Use this page for provider profiles and harness profiles.
Read this when configuring defaults for multiple agents, model families, or deployment environments.

## Extracted Documentation Content

### Key Sections
-  Harness profiles
-  Registration keys
-  Merge semantics
-  Provider profiles
-  Load profiles from config files
-  Ship a profile as a plugin
-  Related

### Important Points
- Package per-provider and per-model defaults that Deep Agents applies when a model is selected
- A middleware class (matched by exact type), or a plain string that matches AgentMiddleware.name . Use plain strings for built-ins and public aliases such as "SummarizationMiddleware" .
- An module:Class import ref (for example, "my_pkg.middleware:TelemetryMiddleware" ) to target an exact middleware class from a config file. Import refs resolve lazily, so use them only for trusted local configuration — loading one imports Python code.
- Lookup order for preconfigured model instances
- Exact provider:identifier match
- Identifier-only (only when the identifier already contains : )
- Provider-level — a bare provider name like "openai" applies to every model from that provider.
- Model-level — a fully qualified provider:model key like "openai:gpt-5.5" applies only to that specific model.
- Class-form excluded_middleware entries serialize as a public alias (when the class exposes one via serialized_name: ClassVar[str] ) or as a module:Class import ref.
- Non-empty extra_middleware and middleware classes declared in __main__ or inside a function scope cannot be serialized — export raises ValueError .
- Harness Overview — harness capabilities overview
- Models — configure model providers and parameters
- Customization — full create_deep_agent configuration surface

### Extracted Table/Field Signals
- Field
- Merge behavior
- base_system_prompt , system_prompt_suffix
- New value wins when set; otherwise inherits
- tool_description_overrides
- Mappings merge per key; new value wins on a shared key
- excluded_tools , excluded_middleware
- Set union
- extra_middleware
- Merged by name: new instance replaces existing at its position, novel entries append
- general_purpose_subagent
- Merged field-wise (unset fields inherit)

### API And Concept Signals
`AgentMiddleware`, `Agents`, `GeneralPurposeSubagentProfile`, `HarnessProfile`, `HarnessProfileConfig`, `Model`, `Models`, `Profiles`, `ProviderProfile`, `SummarizationMiddleware`, `TelemetryMiddleware`, `create_deep_agent`, `deepagents`, `excluded_middleware`, `excluded_tools`, `extra_middleware`, `file`, `files`, `general_purpose_subagent`, `harness_profiles`, `middleware`, `model`, `profile`, `profiles`, `provider_profiles`, `register_harness_profile`, `register_provider_profile`, `tool`

### Representative Code Signals
```text
from deepagents import ( GeneralPurposeSubagentProfile , HarnessProfile , register_harness_profile , ) register_harness_profile ( "openai:gpt-5.5" , HarnessProfile ( system_prompt_suffix = "Respond in under 100 words." , excluded_tools = { "execute" }, excluded_middleware = { "SummarizationMiddleware" }, general_purpose_subagent = GeneralPurposeSubagentProfile ( enabled = False ), ), )
```
```text
from deepagents import ProviderProfile , register_provider_profile register_provider_profile ( "openai" , ProviderProfile ( init_kwargs = { "temperature" : 0 }), )
```
```text
# openai.yaml base_system_prompt : You are helpful. system_prompt_suffix : Respond briefly. excluded_tools : - execute - grep excluded_middleware : - SummarizationMiddleware - my_pkg.middleware:TelemetryMiddleware general_purpose_subagent : enabled : false
```
```text
import yaml from deepagents import HarnessProfileConfig , register_harness_profile with open ( "openai.yaml" ) as f : register_harness_profile ( "openai" , HarnessProfileConfig . from_dict ( yaml . safe_load ( f )), )
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
