# 03 Workflows and API

## POST /traces
Auth: x-api-key header required
Request: { session_id, model, prompt_version, temperature, environment, question, trace_id? }
Response 200: { trace_id, status: "accepted" }
Response 400: { error: "<validation message>" }

## POST /feedback
Auth: x-api-key header required
Request: { trace_id, rating: "thumbs_up" | "thumbs_down" }
Response 200: { status: "recorded" }
Response 400: { error: "<validation message>" }
