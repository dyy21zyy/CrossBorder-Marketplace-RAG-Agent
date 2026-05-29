# Evaluation Report

Results are based on sample data and are intended for demonstration.

## 1. Retrieval Evaluation

### Context Relevance Metrics
| module | Precision@5 | Recall@5 | F1@5 | MRR | MAP | Context Relevance | Avg Latency |
|---|---:|---:|---:|---:|---:|---:|---:|

## 2. Risk Evaluation
| risk type | Accuracy | High-risk Recall | Unknown Handling | False Positive Rate | False Negative Rate |
|---|---:|---:|---:|---:|---:|
| trademark_risk | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| platform_policy_risk | 0.091 | 0.000 | 1.000 | 0.000 | 1.000 |
| patent_claim_risk | 0.909 | 0.000 | 1.000 | 0.000 | 0.000 |
| litigation_risk | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 |

## 3. Response Evaluation
| Faithfulness | Answer Relevance | Unsupported Claim Rate | Citation Coverage | Disclaimer Coverage | Forbidden Claim Rate |
|---:|---:|---:|---:|---:|---:|
| 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 |

## Chinese Response Evaluation
| Chinese Answer Rate | Chinese Disclaimer Coverage | Brand Preservation | Mixed Language Penalty |
|---:|---:|---:|---:|
| 1.000 | 1.000 | 0.000 | 0.000 |

## 4. Failure Cases
- 检索失败样例：见 retrieval per_query 中 recall_at_k=0 的条目。
- 风险误判样例：见 risk per_sample 中 expected != predicted 的条目。
- unsupported 样例：见 response per_sample 中 unsupported_claim_rate>0 的条目。

## 5. Summary
- 检索瓶颈优先看低 recall 模块。
- Reranker 提升需结合 latency 一起判断。
- 风险判断可能偏保守，unknown 样例需人工复核。
- 生成回答应持续降低 unsupported claim 风险。
