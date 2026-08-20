from datetime import timedelta
from typing import Any
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.activities import detect_pii_activity, redact_text_activity

@workflow.defn
class PIIAnonymizerWorkflow:
    def __init__(self):
        self._approved: bool | None = None
        self._entities: list[dict] = []
        self._raw_text: str = ""

    @workflow.signal
    def approve_redaction(self, approved: bool):
        self._approved = approved

    @workflow.query
    def get_pending_report(self) -> dict:
        return {
            "approved": self._approved,
            "entities": self._entities,
            "raw_text": self._raw_text
        }

    @workflow.run
    async def run(self, raw_text: str) -> dict[str, Any]:
        self._raw_text = raw_text

        # Step 1: Detect PII via Agent Activity
        pii_report = await workflow.execute_activity(
            detect_pii_activity,
            args=[raw_text],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        self._entities = pii_report.get("entities", [])

        # Step 2: Pause workflow execution safely until external Signal is received
        if pii_report.get("requires_approval") and self._entities:
            await workflow.wait_condition(lambda: self._approved is not None)

        # Step 3: Reject or Redact
        if self._approved is False:
            return {"status": "REJECTED", "text": raw_text}

        redacted_text = await workflow.execute_activity(
            redact_text_activity,
            args=[{"text": raw_text, "entities": self._entities}],
            start_to_close_timeout=timedelta(seconds=30),
        )

        return {"status": "COMPLETED", "text": redacted_text}