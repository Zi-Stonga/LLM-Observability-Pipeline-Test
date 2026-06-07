# 02 Data Model

## DynamoDB Tables

### ai-obs-traces
PK: trace_id (String), SK: span_id (String)
GSI: session-index (PK: session_id, SK: timestamp)
TTL: ttl attribute (90 days)
Streams: NEW_AND_OLD_IMAGES

### ai-obs-scores
PK: trace_id (String)
Streams: NEW_AND_OLD_IMAGES (triggers FlaggingFn)

### ai-obs-flags
PK: flag_id (String), SK: trace_id (String)

### ai-obs-prompts
PK: prompt_id (String), SK: version (String)

## Python data models
See src/models.py for Span, QualityScore, Flag, IngestRequest, ScoringMessage.
