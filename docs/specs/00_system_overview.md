# 00 System Overview

## Purpose
Production-grade observability pipeline for LLM applications deployed on AWS.
Captures every trace, scores quality, flags violations, and surfaces metrics
to operators in real time.

## Code Conventions
- Python 3.12, Black formatter, Ruff linter, mypy strict mode
- All functions fully type-annotated
- No print() in production code; use logging module with getLogger(__name__)
- Config via pydantic BaseSettings, no inline os.getenv()
- Custom exceptions in src/exceptions.py
- Tests: pytest, AAA structure, >80% coverage

## Components
- API Gateway: POST /traces, POST /feedback
- IngestFn: validates, stores span-0, fans out to Kinesis
- ProcessorFn: enriches spans, calculates cost, queues final responses
- ScorerFn: groundedness + hallucination scoring
- FlaggingFn: rule-based quality enforcement
- FeedbackFn: user rating capture
- MetricsFn: scheduled CloudWatch metric aggregation
