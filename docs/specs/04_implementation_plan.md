# 04 Implementation Plan

- [x] Bootstrap: pyproject.toml, ruff, black, mypy, pre-commit
- [x] src/config.py: pydantic BaseSettings
- [x] src/models.py: domain dataclasses
- [x] src/exceptions.py: custom exception hierarchy
- [x] src/validation.py: input validation utilities
- [x] src/scoring.py: groundedness and hallucination algorithms
- [x] Lambda handlers (6): ingest, processor, scorer, flagging, feedback, metrics
- [x] CDK stack: refactored into private methods, per-function IAM roles
- [x] Tests: validation, scoring, ingest, scorer, feedback
- [x] GitHub Actions CI: lint, type-check, test, cdk synth
- [ ] Embedding-based scorer upgrade (see docs/scorer_upgrade.md)
- [ ] VPC endpoints for Lambda-to-AWS service traffic
- [ ] GET /traces query endpoint
