# src/worker.py
import asyncio
import os
from temporalio.client import Client
from temporalio.worker import Worker, UnsandboxedWorkflowRunner
from src.activities import detect_pii_activity, redact_text_activity
from src.workflows import PIIAnonymizerWorkflow

async def main():
    temporal_addr = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    client = await Client.connect(temporal_addr)

    worker = Worker(
        client,
        task_queue="legal-tasks-queue",
        workflows=[PIIAnonymizerWorkflow],
        activities=[detect_pii_activity, redact_text_activity],
        workflow_runner=UnsandboxedWorkflowRunner(),
    )
    print("Worker running...")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())