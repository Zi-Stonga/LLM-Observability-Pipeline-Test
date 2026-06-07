# 06 Result Schemas

## QualityScore record (ai-obs-scores)
{
  trace_id: string,
  scored_at: ISO timestamp,
  groundedness: string (float 0-1),
  hallucination: string (float 0-1),
  cost_usd: string (decimal),
  total_tokens: number,
  model: string,
  chunk_count: number,
  answer_len: number
}

## Flag record (ai-obs-flags)
{
  flag_id: UUID string,
  trace_id: string,
  timestamp: ISO timestamp,
  rule: string,
  detail: string,
  severity: CRITICAL | HIGH | MEDIUM | LOW,
  status: open | closed
}
