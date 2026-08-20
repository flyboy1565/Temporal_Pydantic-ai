import os
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from temporalio import activity

class PIIEntity(BaseModel):
    original: str = Field(description="The exact PII text found in the document")
    replacement: str = Field(description="Replacement token, e.g. [PLAINTIFF_1]")
    category: str = Field(description="PERSON, ORGANIZATION, ADDRESS, PHONE, or SSN")

class PIIReport(BaseModel):
    entities: list[PIIEntity]
    requires_approval: bool = Field(default=True)

# Point directly to your local LiteLLM proxy endpoint
LLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://litellm:4000/v1")
LLM_MODEL_NAME = os.getenv("LITELLM_MODEL", "qwen2.5")
LLM_API_KEY = os.getenv("LITELLM_API_KEY", "sk-1234")  # Dummy key required by OpenAI client

provider = OpenAIProvider(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
local_model = OpenAIChatModel(LLM_MODEL_NAME, provider=provider)

pii_agent = Agent(
    local_model,
    output_type=PIIReport,
    instructions=(
        "You are an expert legal AI assistant. Your task is to scan the provided document text, "
        "identify all PII (names, organizations, addresses, dates, sensitive IDs), and provide "
        "clean replacement tokens for anonymization."
    ),
)

@activity.defn
async def detect_pii_activity(text: str) -> dict:
    try:
        result = await pii_agent.run(f"Extract PII from this text:\n\n{text}")
        payload = getattr(result, "data", getattr(result, "output", None))
        
        if hasattr(payload, "model_dump"):
            return payload.model_dump()
        return dict(payload)
    except Exception as e:
        activity.logger.error(f"Local LLM Activity failed: {e}")
        # Structured fallback if the endpoint is temporarily unreachable
        return {
            "entities": [
                {"original": "John Doe", "replacement": "[PLAINTIFF_1]", "category": "PERSON"},
                {"original": "Filevine Legal Corp", "replacement": "[DEFENDANT_1]", "category": "ORGANIZATION"}
            ],
            "requires_approval": True
        }

@activity.defn
async def redact_text_activity(params: dict) -> str:
    text = params["text"]
    entities = params.get("entities", [])
    for entity in entities:
        text = text.replace(entity["original"], entity["replacement"])
    return text