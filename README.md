# Temporal + Pydantic-AI PII Anonymizer

A Temporal workflow that uses pydantic-ai with a local LiteLLM proxy (Ollama/Qwen2.5-coder) to detect and redact PII from legal documents.

## Architecture

```
FastAPI → Temporal Workflow → Worker → LiteLLM (holfam:4000) → Ollama (Qwen2.5-coder)
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| temporal | 7233, 8233 | Temporal server + UI |
| worker | 8222 | FastAPI endpoint |
| task-runner | - | Temporal worker (LLM calls) |

## Setup

```bash
docker compose up -d --build
```

## Usage

Submit a PII redaction workflow via the API or `src/app.py`.
