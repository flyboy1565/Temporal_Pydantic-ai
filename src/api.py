import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from temporalio.client import Client
from src.workflows import PIIAnonymizerWorkflow

app = FastAPI()
TEMPORAL_ADDR = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8")
    workflow_id = f"pii-doc-{uuid.uuid4().hex[:8]}"
    
    client = await Client.connect(TEMPORAL_ADDR)
    await client.start_workflow(
        PIIAnonymizerWorkflow.run,
        content,
        id=workflow_id,
        task_queue="legal-tasks-queue",
    )
    return {"workflow_id": workflow_id}

@app.get("/api/status/{workflow_id}")
async def get_status(workflow_id: str):
    client = await Client.connect(TEMPORAL_ADDR)
    handle = client.get_workflow_handle(workflow_id)
    report = await handle.query(PIIAnonymizerWorkflow.get_pending_report)
    return report

@app.post("/api/approve/{workflow_id}")
async def approve_workflow(workflow_id: str, approved: bool = Form(...)):
    client = await Client.connect(TEMPORAL_ADDR)
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(PIIAnonymizerWorkflow.approve_redaction, approved)
    result = await handle.result()
    return result

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <title>Legal PII Anonymizer</title>
      <style>
        body { font-family: monospace; max-width: 800px; margin: 20px auto; padding: 20px; background: #1e1e1e; color: #d4d4d4; }
        button { background: #0e639c; color: white; border: none; padding: 8px 16px; cursor: pointer; margin-right: 8px; }
        pre { background: #252526; padding: 12px; border: 1px solid #3c3c3c; overflow-x: auto; }
      </style>
    </head>
    <body>
      <h2>Legal Document PII Anonymizer</h2>
      <input type="file" id="fileInput" />
      <button onclick="uploadDoc()">Upload & Process</button>
      
      <div id="statusSection" style="margin-top:20px;"></div>

      <script>
        let currentWorkflowId = null;

        async function uploadDoc() {
          const file = document.getElementById('fileInput').files[0];
          if (!file) return alert('Select a text file first');
          const formData = new FormData();
          formData.append('file', file);
          
          const res = await fetch('/api/upload', { method: 'POST', body: formData });
          const data = await res.json();
          currentWorkflowId = data.workflow_id;
          document.getElementById('statusSection').innerHTML = `<p>Workflow Started ID: <b>${currentWorkflowId}</b>. Polling for PII report...</p>`;
          pollStatus();
        }

        async function pollStatus() {
          const res = await fetch(`/api/status/${currentWorkflowId}`);
          const data = await res.json();
          
          if (data.entities && data.entities.length > 0 && data.approved === null) {
            document.getElementById('statusSection').innerHTML = `
              <h3>PII Detected:</h3>
              <pre>${JSON.stringify(data.entities, null, 2)}</pre>
              <button onclick="sendSignal(true)">Approve Redaction</button>
              <button onclick="sendSignal(false)" style="background:#a1260d">Reject</button>
            `;
          } else {
            setTimeout(pollStatus, 1000);
          }
        }

        async function sendSignal(approved) {
          const formData = new FormData();
          formData.append('approved', approved);
          const res = await fetch(`/api/approve/${currentWorkflowId}`, { method: 'POST', body: formData });
          const result = await res.json();
          document.getElementById('statusSection').innerHTML = `
            <h3>Final Workflow Output (Status: ${result.status}):</h3>
            <pre>${result.text}</pre>
          `;
        }
      </script>
    </body>
    </html>
    """