from fastapi import FastAPI, WebSocket, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import asyncio
from datetime import datetime, date, timedelta
import threading
from loguru import logger

from . import database
from . import (
    configure_schedule,
    get_last_run_time,
    get_next_run_time,
    process_date_range,
    start_summarizer,
    stop_summarizer
)

app = FastAPI(title="Email Summarizer API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
summarizer_thread = None
is_running = False
connected_clients: List[WebSocket] = []

class ScheduleConfig(BaseModel):
    interval_minutes: int = 30
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class DateRange(BaseModel):
    start_date: date
    end_date: date

@app.get("/status")
async def get_status():
    return {
        "is_running": is_running,
        "last_run": get_last_run_time(),
        "next_run": get_next_run_time(),
    }

@app.post("/start")
async def start_email_summarizer(background_tasks: BackgroundTasks):
    global summarizer_thread, is_running
    
    if is_running:
        raise HTTPException(status_code=400, detail="Summarizer is already running")
    
    is_running = True
    summarizer_thread = threading.Thread(
        target=start_summarizer,
        daemon=True
    )
    summarizer_thread.start()
    
    return {"status": "started"}

@app.post("/stop")
async def stop_email_summarizer():
    global is_running, summarizer_thread
    
    if not is_running:
        raise HTTPException(status_code=400, detail="Summarizer is not running")
    
    is_running = False
    stop_summarizer()
    if summarizer_thread:
        summarizer_thread.join(timeout=5)
    
    return {"status": "stopped"}

@app.post("/configure")
async def configure_run_schedule(config: ScheduleConfig):
    configure_schedule(
        interval_minutes=config.interval_minutes,
        start_time=config.start_time,
        end_time=config.end_time
    )
    return {"status": "configured"}

@app.post("/summarize-range")
async def summarize_date_range(date_range: DateRange):
    today = date.today()
    min_date = today - timedelta(days=7)
    
    if date_range.start_date < min_date or date_range.end_date > today:
        raise HTTPException(
            status_code=400,
            detail="Date range must be within the last 7 days and not include today"
        )
    
    if date_range.start_date > date_range.end_date:
        raise HTTPException(
            status_code=400,
            detail="Start date must be before end date"
        )
    
    session = database.get_session()
    process_date_range(date_range.start_date, date_range.end_date)
    return {"status": "processing"}

@app.get("/summaries")
async def get_summaries(start_date: date, end_date: date):
    session = database.get_session()
    summaries = database.get_daily_summaries(session, start_date, end_date)
    return [{
        "date": summary.date,
        "total_amount": summary.total_amount,
        "transaction_count": summary.transaction_count,
        "summary_text": summary.summary_text,
        "created_at": summary.created_at
    } for summary in summaries]

@app.get("/transactions")
async def get_transactions(start_date: date, end_date: date):
    session = database.get_session()
    transactions = database.get_transactions_by_date_range(session, start_date, end_date)
    return [{
        "date": trans.date,
        "vendor": trans.vendor,
        "amount": trans.amount,
        "type": trans.type,
        "category": trans.category,
        "ref": trans.ref
    } for trans in transactions]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
            # Keep connection alive
            await websocket.send_json({
                "type": "status",
                "data": {
                    "is_running": is_running,
                    "last_run": get_last_run_time(),
                    "next_run": get_next_run_time(),
                }
            })
    except:
        connected_clients.remove(websocket)

# Broadcast status updates to all connected clients
async def broadcast_status():
    while True:
        if connected_clients:
            status_data = {
                "type": "status",
                "data": {
                    "is_running": is_running,
                    "last_run": get_last_run_time(),
                    "next_run": get_next_run_time(),
                }
            }
            for client in connected_clients:
                try:
                    await client.send_json(status_data)
                except:
                    connected_clients.remove(client)
        await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    background_tasks = BackgroundTasks()
    background_tasks.add_task(broadcast_status) 