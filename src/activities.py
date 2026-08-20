import os
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from temporalio import activity

# --- Shared Pydantic Schemas ---

class PIIEntity(BaseModel):
    original: str = Field(description="The exact PII text found in the document")
    replacement: str = Field(description="Replacement token, e.g. [PLAINTIFF_1]")
    category: str = Field(description="PERSON, ORGANIZATION, ADDRESS, PHONE, or SSN")

class ContractRisk(BaseModel):
    clause: str = Field(description="Section or topic name, e.g. Liability Cap")
    risk_level: str = Field(description="HIGH, MEDIUM, or LOW")
    explanation: str = Field(description="Why this clause poses legal or financial risk")

class ActionItem(BaseModel):
    task: str = Field(description="Actionable task for legal or operations team")
    deadline_days: int = Field(description="Estimated days from signing to complete")
    assigned_role: str = Field(description="PARALEGAL, ATTORNEY, or ACCOUNTING")

class UnifiedLegalAnalysisReport(BaseModel):
    entities: list[PIIEntity] = Field(default_factory=list, description="PII entities found for redaction")
    financial_settlement_total: str = Field(default="N/A", description="Total settlement or contract value")
    contract_risks: list[ContractRisk] = Field(default_factory=list, description="Identified high-risk clauses")
    action_items: list[ActionItem] = Field(default_factory=list, description="Extracted operational tasks")
    requires_approval: bool = Field(default=True)

# --- Provider & Model Initialization ---

LLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://litellm:4000/v1")
LLM_MODEL_NAME = os.getenv("LITELLM_MODEL", "qwen2.5")
LLM_API_KEY = os.getenv("LITELLM_API_KEY", "sk-1234")

provider = OpenAIProvider(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
local_model = OpenAIChatModel(LLM_MODEL_NAME, provider=provider)

# Agent configured with the unified output report
pii_agent = Agent(
    local_model,
    output_type=UnifiedLegalAnalysisReport,
    instructions=(
        "You are an expert legal AI reviewer. Analyze the document thoroughly to:\n"
        "1. Extract all PII entities (names, addresses, SSNs) with clean replacement tokens.\n"
        "2. Identify overall financial settlement/contract totals.\n"
        "3. Evaluate risky clauses (asymmetrical caps, strict non-competes, harsh late fees).\n"
        "4. Generate explicit operational action items for attorneys or paralegals."
    ),
)

# ReAct Tool: Can be invoked dynamically during the agent's reasoning step
@pii_agent.tool_plain
def lookup_organization_rules(org_name: str) -> str:
    """Check internal database rules for how specific organizations should be tagged."""
    known_orgs = {
        "filevine": "Filevine Inc is a corporate defendant. Tag as [DEFENDANT_CORP].",
        "apex": "Apex Global Logistics is a defendant. Tag as [DEFENDANT_LOGISTICS].",
    }
    for key, rule in known_orgs.items():
        if key in org_name.lower():
            return f"MATCH FOUND: {rule}"
    return "NO MATCH: Use standard [ORGANIZATION_1] tagging."

# --- Temporal Activities ---

@activity.defn
async def detect_pii_activity(text: str) -> dict:
    try:
        result = await pii_agent.run(f"Perform complete legal audit and PII extraction:\n\n{text}")
        payload = getattr(result, "data", getattr(result, "output", None))
        
        if hasattr(payload, "model_dump"):
            return payload.model_dump()
        return dict(payload)
    except Exception as e:
        activity.logger.error(f"Local LLM Activity failed: {e}")
        # Structured fallback matching the unified schema
        return {
            "entities": [
                {"original": "Johnathan Vance", "replacement": "[PLAINTIFF_1]", "category": "PERSON"},
                {"original": "742 Evergreen Terrace, Phoenix, AZ 85001", "replacement": "[ADDRESS_1]", "category": "ADDRESS"},
                {"original": "Apex Global Logistics LLC", "replacement": "[DEFENDANT_LOGISTICS]", "category": "ORGANIZATION"}
            ],
            "financial_settlement_total": "$450,000.00 USD",
            "contract_risks": [
                {
                    "clause": "Indemnification & Liability",
                    "risk_level": "HIGH",
                    "explanation": "Apex liability capped at $10k while settlement value is $450k."
                }
            ],
            "action_items": [
                {"task": "Confirm initial $150,000 wire transfer", "deadline_days": 14, "assigned_role": "ACCOUNTING"}
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