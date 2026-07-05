import os
import json
import logging
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import google.auth
from google.auth.transport.requests import Request as AuthRequest
import httpx
from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
REGION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-east1")
AGENT_RUNTIME_ID = os.environ.get("AGENT_RUNTIME_ID")

class ActionRequest(BaseModel):
    action: str

html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Expense Manager Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0d1117;
            --card-bg: rgba(22, 27, 34, 0.6);
            --border-color: rgba(255, 255, 255, 0.1);
            --text-main: #e6edf3;
            --text-muted: #8b949e;
            --accent-glow: radial-gradient(circle at 50% 0%, rgba(88, 166, 255, 0.15), transparent 50%);
            --approve-color: #238636;
            --approve-hover: #2ea043;
            --reject-color: #da3633;
            --reject-hover: #f85149;
        }
        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            background-image: var(--accent-glow);
            color: var(--text-main);
            margin: 0;
            padding: 2rem;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        h1 {
            font-weight: 600;
            margin-bottom: 2rem;
            text-align: center;
            letter-spacing: 1px;
        }
        .dashboard {
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
            justify-content: center;
            max-width: 1200px;
            width: 100%;
        }
        .card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            width: 320px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
        }
        .card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 4px;
            background: linear-gradient(90deg, #58a6ff, #8a2be2);
        }
        .expense-amount {
            font-size: 2.2rem;
            font-weight: 600;
            margin: 0.5rem 0;
            color: #58a6ff;
        }
        .expense-detail {
            margin: 0.25rem 0;
            font-size: 0.95rem;
            color: #c9d1d9;
        }
        .expense-detail strong {
            color: var(--text-muted);
            font-weight: 400;
        }
        .risk-summary {
            margin-top: 1rem;
            padding: 0.75rem;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            font-size: 0.85rem;
            line-height: 1.4;
            flex-grow: 1;
        }
        .actions {
            display: flex;
            gap: 1rem;
            margin-top: 1.5rem;
        }
        button {
            flex: 1;
            padding: 0.75rem;
            border: none;
            border-radius: 8px;
            font-family: 'Outfit', sans-serif;
            font-weight: 600;
            font-size: 1rem;
            cursor: pointer;
            color: #fff;
            transition: background-color 0.2s, transform 0.1s;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 44px;
        }
        button:active {
            transform: scale(0.97);
        }
        button:disabled {
            opacity: 0.7;
            cursor: not-allowed;
            transform: none;
        }
        .btn-approve { background-color: var(--approve-color); }
        .btn-approve:hover:not(:disabled) { background-color: var(--approve-hover); }
        .btn-reject { background-color: var(--reject-color); }
        .btn-reject:hover:not(:disabled) { background-color: var(--reject-hover); }
        
        .spinner {
            border: 3px solid rgba(255,255,255,0.3);
            border-top: 3px solid #fff;
            border-radius: 50%;
            width: 18px;
            height: 18px;
            animation: spin 1s linear infinite;
            display: none;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        /* Modal Styles */
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(5px);
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
            z-index: 1000;
        }
        .modal-overlay.active {
            opacity: 1;
            pointer-events: auto;
        }
        .modal {
            background: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 2.5rem;
            width: 90%;
            max-width: 500px;
            transform: translateY(30px);
            transition: transform 0.3s ease;
            box-shadow: 0 20px 50px rgba(0,0,0,0.5);
            text-align: center;
        }
        .modal-overlay.active .modal {
            transform: translateY(0);
        }
        .modal h2 { margin-top: 0; color: #fff; }
        .modal-content {
            margin: 1.5rem 0;
            color: #c9d1d9;
            line-height: 1.5;
            text-align: left;
            background: rgba(255, 255, 255, 0.03);
            padding: 1rem;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            word-wrap: break-word;
        }
        .modal-close {
            background: transparent;
            color: var(--text-main);
            border: 1px solid var(--border-color);
            width: 100%;
        }
        .modal-close:hover {
            background: rgba(255,255,255,0.1);
        }
    </style>
</head>
<body>
    <h1>Pending Approvals</h1>
    <div id="dashboard" class="dashboard">
        <div style="text-align: center; width: 100%; color: var(--text-muted); font-size: 1.1rem; padding: 2rem;">Loading pending expenses...</div>
    </div>

    <div class="modal-overlay" id="modalOverlay">
        <div class="modal" id="modal">
            <h2 id="modalTitle">Review Finalized</h2>
            <div id="modalContent" class="modal-content"></div>
            <button class="modal-close" onclick="closeModal()">Close</button>
        </div>
    </div>

    <script>
        async function fetchPending() {
            try {
                const res = await fetch('/api/pending');
                const data = await res.json();
                const container = document.getElementById('dashboard');
                container.innerHTML = '';
                
                if (data.length === 0) {
                    container.innerHTML = '<div style="text-align: center; width: 100%; color: var(--text-muted); padding: 2rem;">No pending approvals.</div>';
                    return;
                }

                data.forEach(item => {
                    const payload = typeof item.payload === 'string' ? JSON.parse(item.payload) : (item.payload || {});
                    let submitter = 'Unknown';
                    let amount = '0';
                    let category = 'N/A';
                    let description = 'N/A';
                    let riskText = 'Waiting for manager review...';
                    
                    if (payload.payload && payload.payload.expense) {
                        const exp = payload.payload.expense;
                        submitter = exp.submitter || submitter;
                        amount = exp.amount || amount;
                        category = exp.category || category;
                        description = exp.description || description;
                        if (payload.payload.review) {
                            riskText = `<strong>Risk Level:</strong> ${payload.payload.review.risk_level}<br>` +
                                       `<strong>Summary:</strong> ${payload.payload.review.summary}`;
                        }
                    } else if (payload.message) {
                        try {
                            const msg = typeof payload.message === 'string' ? JSON.parse(payload.message) : payload.message;
                            submitter = msg.submitter || submitter;
                            amount = msg.amount || amount;
                            category = msg.category || category;
                            description = msg.description || description;
                        } catch(e) {}
                    } else {
                        submitter = payload.submitter || submitter;
                        amount = payload.amount || amount;
                        category = payload.category || category;
                        description = payload.description || description;
                    }
                    
                    const card = document.createElement('div');
                    card.className = 'card';
                    card.id = `card-${item.session_id}`;
                    
                    card.innerHTML = `
                        <div class="expense-detail"><strong>Submitter:</strong> ${submitter}</div>
                        <div class="expense-amount">$${amount}</div>
                        <div class="expense-detail"><strong>Category:</strong> ${category}</div>
                        <div class="expense-detail"><strong>Description:</strong> ${description}</div>
                        <div class="risk-summary">
                            ${riskText}
                        </div>
                        <div class="actions">
                            <button class="btn-approve" onclick="takeAction('${item.session_id}', true, this)">
                                <span class="btn-text">Approve</span>
                                <div class="spinner"></div>
                            </button>
                            <button class="btn-reject" onclick="takeAction('${item.session_id}', false, this)">
                                <span class="btn-text">Reject</span>
                                <div class="spinner"></div>
                            </button>
                        </div>
                    `;
                    container.appendChild(card);
                });
            } catch (err) {
                console.error(err);
                document.getElementById('dashboard').innerHTML = '<div style="color: var(--reject-color); padding: 2rem;">Error loading approvals. Check console.</div>';
            }
        }

        async function takeAction(sessionId, approved, btnElement) {
            const btnText = btnElement.querySelector('.btn-text');
            const spinner = btnElement.querySelector('.spinner');
            const allBtns = document.querySelectorAll(`#card-${sessionId} button`);
            
            // UI Loading state
            allBtns.forEach(btn => btn.disabled = true);
            btnText.style.display = 'none';
            spinner.style.display = 'block';

            try {
                const res = await fetch(`/api/action/${sessionId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: approved ? 'approve' : 'reject' })
                });
                
                const result = await res.json();
                
                if (!res.ok) {
                    throw new Error(result.detail || "Server error");
                }
                
                // Show modal with final result
                const statusColor = approved ? 'var(--approve-color)' : 'var(--reject-color)';
                const statusText = approved ? 'Approved' : 'Rejected';
                
                document.getElementById('modalTitle').innerText = `Expense ${statusText}`;
                document.getElementById('modalTitle').style.color = statusColor;
                
                document.getElementById('modalContent').innerHTML = `
                    <p style="margin-bottom: 0.5rem"><strong>Session ID:</strong> ${sessionId}</p>
                    <p style="margin-top: 0"><strong>Agent Response:</strong><br/> ${result.agent_response || 'Processed successfully.'}</p>
                `;
                
                // Remove card
                document.getElementById(`card-${sessionId}`).remove();
                
                // Open modal
                document.getElementById('modalOverlay').classList.add('active');
                
                // Check if empty
                if (document.querySelectorAll('.card').length === 0) {
                    document.getElementById('dashboard').innerHTML = '<div style="text-align: center; width: 100%; color: var(--text-muted); padding: 2rem;">No pending approvals.</div>';
                }
                
            } catch (err) {
                console.error(err);
                alert("Action failed: " + err.message);
                allBtns.forEach(btn => btn.disabled = false);
                btnText.style.display = 'block';
                spinner.style.display = 'none';
            }
        }
        
        function closeModal() {
            document.getElementById('modalOverlay').classList.remove('active');
        }

        // Initial fetch
        fetchPending();
    </script>
</body>
</html>
"""

@app.get("/")
def get_dashboard():
    return HTMLResponse(content=html_content)

def get_session_service():
    if not PROJECT_ID or not AGENT_RUNTIME_ID:
        raise ValueError("GOOGLE_CLOUD_PROJECT and AGENT_RUNTIME_ID must be set in environment variables")
    return VertexAiSessionService(
        project=PROJECT_ID,
        location=REGION,
        agent_engine_id=AGENT_RUNTIME_ID
    )

def safe_to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    elif hasattr(obj, "to_dict"):
        return obj.to_dict()
    elif isinstance(obj, dict):
        return obj
    else:
        try:
            return dict(obj)
        except Exception:
            return str(obj)

@app.get("/api/pending")
async def get_pending():
    try:
        service = get_session_service()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    pending = []
    user_id = "default-user"
    
    try:
        resp = await service.list_sessions(user_id=user_id, app_name="app")
        sessions = getattr(resp, "sessions", [])
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return []
        
    for sess in sessions:
        try:
            sess_obj = await service.get_session(user_id=user_id, session_id=sess.id, app_name="app")
            history = getattr(sess_obj, "events", getattr(sess_obj, "history", []))
        except Exception as e:
            logger.error(f"Error reading history for session {sess.id}: {e}")
            continue
            
        unresolved_interrupt = None
        expense_payload = {}
        
        call_events = {}
        response_events = set()
        
        for event in history:
            content = getattr(event, "content", None)
            parts = getattr(content, "parts", []) if content else getattr(event, "parts", [])
            for part in parts:
                fc = getattr(part, "function_call", None)
                if fc and getattr(fc, "name", "") == "adk_request_input":
                    call_events[getattr(fc, "id", "")] = fc
                    
                fr = getattr(part, "function_response", None)
                if fr and getattr(fr, "name", "") == "adk_request_input":
                    response_events.add(getattr(fr, "id", ""))
                    
        for call_id, call in call_events.items():
            if call_id not in response_events:
                unresolved_interrupt = call_id
                args = getattr(call, "args", {})
                expense_payload = safe_to_dict(args)
                break
                
        if unresolved_interrupt:
            pending.append({
                "session_id": sess.id,
                "interrupt_id": unresolved_interrupt,
                "payload": expense_payload
            })
            
    return pending

def get_access_token():
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(AuthRequest())
    return credentials.token

@app.post("/api/action/{session_id}")
async def take_action(session_id: str, req: ActionRequest):
    approved = (req.action == "approve")
    
    try:
        service = get_session_service()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    user_id = "default-user"
    
    try:
        sess_obj = await service.get_session(user_id=user_id, session_id=session_id, app_name="app")
        history = getattr(sess_obj, "events", getattr(sess_obj, "history", []))
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Session not found: {e}")
        
    unresolved_interrupt = None
    call_events = {}
    response_events = set()
    
    for event in history:
        content = getattr(event, "content", None)
        parts = getattr(content, "parts", []) if content else getattr(event, "parts", [])
        for part in parts:
            fc = getattr(part, "function_call", None)
            if fc and getattr(fc, "name", "") == "adk_request_input":
                call_events[getattr(fc, "id", "")] = fc
            fr = getattr(part, "function_response", None)
            if fr and getattr(fr, "name", "") == "adk_request_input":
                response_events.add(getattr(fr, "id", ""))
                    
    for call_id in call_events:
        if call_id not in response_events:
            unresolved_interrupt = call_id
            break
            
    if not unresolved_interrupt:
        raise HTTPException(status_code=400, detail="No pending approval found for this session")
        
    resume_payload = {
        "role": "user",
        "parts": [
            {
                "function_response": {
                    "id": unresolved_interrupt,
                    "name": "adk_request_input",
                    "response": {"decision": "approve" if approved else "reject"}
                }
            }
        ]
    }
    
    try:
        token = get_access_token()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth error: {e}")
        
    url = f"https://{REGION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/{REGION}/reasoningEngines/{AGENT_RUNTIME_ID}:streamQuery"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    body = {
        "class_method": "stream_query",
        "input": {
            "user_id": user_id,
            "session_id": session_id,
            "message": resume_payload
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=body, timeout=60.0)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Request to Agent Runtime failed: {e}")
            
    if resp.status_code != 200:
        logger.error(f"Error from Agent Runtime: {resp.text}")
        raise HTTPException(status_code=resp.status_code, detail=f"Failed to resume session: {resp.text}")
        
    final_text = ""
    for line in resp.text.split("\\n"):
        if line.strip():
            try:
                data = json.loads(line)
                parts = data.get("content", {}).get("parts", [])
                for p in parts:
                    if "text" in p:
                        final_text += p["text"]
            except Exception:
                pass
                
    return {"status": "success", "agent_response": final_text.strip()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
