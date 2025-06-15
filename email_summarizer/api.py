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
    stop_summarizer,
    is_running as get_summarizer_status,
    get_processing_status
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
connected_clients: List[WebSocket] = []
notify_user_global = True

date_range_thread = None

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

class ScheduleConfig(BaseModel):
    interval_minutes: int = 30
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class DateRange(BaseModel):
    start_date: date
    end_date: date

@app.get("/status")
async def get_status():
    processing_status = get_processing_status()
    return {
        "is_running": get_summarizer_status(),
        "last_run": get_last_run_time(),
        "next_run": get_next_run_time(),
        "current_batch": processing_status
    }

@app.post("/start")
async def start_email_summarizer(background_tasks: BackgroundTasks):
    global summarizer_thread
    
    if get_summarizer_status():
        raise HTTPException(status_code=400, detail="Summarizer is already running")
    
    summarizer_thread = threading.Thread(
        target=start_summarizer,
        daemon=True
    )
    summarizer_thread.start()
    
    # Broadcast status update
    await broadcast_status_update()
    return {"status": "started"}

@app.post("/stop")
async def stop_email_summarizer():
    global summarizer_thread
    
    if not get_summarizer_status():
        raise HTTPException(status_code=400, detail="Summarizer is not running")
    
    stop_summarizer()
    if summarizer_thread:
        summarizer_thread.join(timeout=5)
        summarizer_thread = None
    
    # Broadcast status update
    await broadcast_status_update()
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
async def summarize_date_range(date_range: DateRange, background_tasks: BackgroundTasks):
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
    
    global date_range_thread

    # Prevent overlapping range processing jobs
    if date_range_thread and date_range_thread.is_alive():
        raise HTTPException(status_code=400, detail="A date-range processing job is already running")

    # Start processing in a background thread so the event loop remains responsive
    date_range_thread = threading.Thread(
        target=process_date_range,
        args=(date_range.start_date, date_range.end_date, notify_user_global),
        daemon=True
    )
    date_range_thread.start()

    # Immediately broadcast initial status to clients
    await broadcast_status_update()
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
            # Send current status
            await send_status_to_client(websocket)
    except:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

async def send_status_to_client(websocket: WebSocket):
    """Send current status to a specific client."""
    try:
        processing_status = get_processing_status()
        await websocket.send_json({
            "type": "status",
            "data": {
                "is_running": get_summarizer_status(),
                "last_run": get_last_run_time(),
                "next_run": get_next_run_time(),
                "current_batch": processing_status
            }
        })
    except:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

async def broadcast_status_update():
    """Broadcast status update to all connected clients."""
    processing_status = get_processing_status()
    status_data = {
        "type": "status",
        "data": {
            "is_running": get_summarizer_status(),
            "last_run": get_last_run_time(),
            "next_run": get_next_run_time(),
            "current_batch": processing_status
        }
    }
    for client in connected_clients[:]:
        try:
            await client.send_json(status_data)
        except:
            if client in connected_clients:
                connected_clients.remove(client)

async def status_broadcast_loop():
    """Background task to periodically broadcast status updates."""
    while True:
        try:
            await broadcast_status_update()
        except Exception as e:
            logger.error(f"Error in status broadcast loop: {e}")
        await asyncio.sleep(0.5)  # Broadcast every 500ms for more responsive updates

@app.on_event("startup")
async def startup_event():
    """Initialize the application."""
    try:
        # Start the status broadcast loop
        asyncio.create_task(status_broadcast_loop())
        logger.info("Status broadcast loop started")
    except Exception as e:
        logger.error(f"Error starting status broadcast loop: {e}")

@app.get("/notification-preference")
async def get_notification_preference():
    return {"notify_user": notify_user_global}

@app.post("/notification-preference")
async def set_notification_preference(value: dict):
    global notify_user_global
    notify_user_global = bool(value.get("notify_user", True))
    return {"notify_user": notify_user_global} 