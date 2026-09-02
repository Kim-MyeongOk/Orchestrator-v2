# Multimodal inputs and outputs

Source: https://docs.langchain.com/oss/python/deepagents/multimodal

## Local Usage Guidance
Use this page for image, audio, video, and document inputs or tool outputs.
The multimodality page explains how Deep Agents work with non-text content through supported message/content block types, file reading, and model capability constraints.
Read this before writing examples that pass images, inspect PDFs, process media files, or return multimodal tool results.

## Extracted Documentation Content

### Key Sections
-  Multimodal user input
-  Built-in read_file tool
-  Custom tool outputs
-  Context compression and multimodal content

### Important Points
- Use images, audio, video, and documents with Deep Agents when your model supports multimodal inputs and tool results
- Supported multimodal file extensions
- Offloading measures text tokens only. Non-text blocks (including images) are preserved in replacement messages rather than compressed. A message that contains only an image is not offloaded based on image size alone.
- Summarization compacts older messages into a text-only summary. Image, audio, video, and file blocks in that range are not carried forward—the model only sees what the summarizer writes about them. Recent messages below the keep threshold stay unchanged. When summarization runs, media blocks in older turns drop out of the active context:
- Store images, screenshots, and charts in a filesystem backend or external object store, then pass file paths or URLs through messages.
- Prefer references over base64-encoded image blocks in long-running conversations.
- Use subagents for image-heavy inspection so the main agent receives a compact text result.
- Tune summarization thresholds or provide a custom token counter when your provider charges many tokens for images.

### Extracted Table/Field Signals
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
`Agent`, `Agents`, `Context`, `File`, `Store`, `Tool`, `ToolMessage`, `agent`, `backend`, `context`, `file`, `filesystem`, `invoke`, `model`, `read_file`, `store`, `subagents`, `tool`, `tool_call_id`, `tools`

### Representative Code Signals
```text
result = agent . invoke ({ "messages" : [{ "role" : "user" , "content" : [ { "type" : "text" , "text" : "What is in this screenshot?" }, { "type" : "image" , "url" : "https://example.com/screenshot.png" }, ], }], })
```
```text
from langchain . tools import tool @tool def capture_screenshot () -> list [ dict ]: """Capture a screenshot of the current page.""" return [ { "type" : "text" , "text" : "Screenshot of the current page:" }, { "type" : "image" , "url" : "https://example.com/page.png" }, ]
```
```text
# Before — model receives image blocks in older turns [ HumanMessage ( content = [ { "type" : "text" , "text" : "What trends do you see in this chart?" }, { "type" : "image" , "base64" : IMG , "mime_type" : "image/png" }, ] ), ToolMessage ( content = [ { "type" : "text" , "text" : "Updated chart:" }, { "type" : "image" , "base64" : IMG , "mime_type" : "image/png" }, ], tool_call_id = "call_chart_1" , ), AIMessage ( content = "Revenue rose in Q3 based on the chart trend." ), HumanMessage ( content = "Reply with one sentence summarizing our analysis." ), ] # After — those turns collapse to text; image blocks are gone { "content" : ( "User asked about trends in a chart screenshot. " "Tool returned an updated chart. Agent identified Q3 revenue growth." )}
```

## Verification Note
This file contains a compact extraction from the linked documentation, not a full copy. For exact API signatures, changed defaults, or provider-specific details, open the source URL.
