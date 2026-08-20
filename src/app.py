import asyncio
import os
from temporalio.client import Client
from workflows import LegalAnalysisWorkflow

async def main():
    temporal_addr = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    client = await Client.connect(temporal_addr)

    print("Submitting Legal Analysis Workflow to Temporal...")
    result = await client.execute_workflow(
        LegalAnalysisWorkflow.run,
        "Contract Clause 4B: Termination without cause requires 5-day written notice.",
        id="legal-doc-001",
        task_queue="legal-tasks-queue",
    )
    
    print("\n--- Workflow Result ---")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())