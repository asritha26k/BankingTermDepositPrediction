# main.py
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse
from typing import Dict, Literal, Optional
import uuid
import os
import asyncio
import pandas as pd
import redis.asyncio as aioredis
import json # New import for JSON parsing
from pydantic import BaseModel, Field


from celery import Celery # Keep Celery import for sending tasks
from pathlib import Path 

from app.model import predict_with_pipeline
from app.schemas import InputData, TaskStatusResponse

app = FastAPI(title="Term Deposit Prediction API with Async Processing & Real-time Notifications")

async_redis_client: aioredis.Redis = None
celery_app_instance: Celery = None # Keep this for sending tasks

# Define common directories relative to project root (where main.py resides)
PROJECT_ROOT_FOR_MAIN_PY = Path(__file__).resolve().parent
UPLOAD_DIR = PROJECT_ROOT_FOR_MAIN_PY / "uploads"
RESULTS_DIR = PROJECT_ROOT_FOR_MAIN_PY / "results"

@app.on_event("startup")
async def startup_event():
    """
    Connects to Redis, initializes Celery app instance for FastAPI's use, and ensures necessary directories exist.
    """
    global async_redis_client
    global celery_app_instance

    redis_url_for_fastapi_and_celery = os.getenv("REDIS_URL", "redis://host.docker.internal:6379/0")

    try:
        async_redis_client = aioredis.from_url(redis_url_for_fastapi_and_celery, encoding="utf-8", decode_responses=True)
        await async_redis_client.ping()
        print(f"FastAPI application connected to Redis successfully at {redis_url_for_fastapi_and_celery}.")
    except Exception as e:
        print(f"FastAPI ERROR: Failed to connect to Redis at {redis_url_for_fastapi_and_celery}: {e}. Ensure Redis server is running and accessible.")
        raise RuntimeError(f"Failed to connect to Redis: {e}")

    # --- Celery App Instance Configuration for FastAPI's Side ---
    # This instance is still used by FastAPI to send tasks.
    # Its backend configuration is less critical now for status retrieval, but good for consistency.
    celery_app_instance = Celery(
        "term_deposit_predictor_fastapi_celery_client",
        broker=redis_url_for_fastapi_and_celery,
        backend=redis_url_for_fastapi_and_celery # Keep for consistency, though not used for status retrieval now
    )
    celery_app_instance.conf.update(
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
        timezone='Asia/Kolkata',
        enable_utc=False,
        # Match serializer settings with worker for consistency
        result_serializer='json',
        task_serializer='json',
        accept_content=['json'],
    )
    celery_app_instance.autodiscover_tasks(['celery_worker']) 

    print(f"FastAPI DEBUG: Celery App Backend (for query) configured as: {celery_app_instance.backend.as_uri()} (Note: Status now retrieved manually from Redis)")

    UPLOAD_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    (PROJECT_ROOT_FOR_MAIN_PY / "celery_results").mkdir(exist_ok=True) # Keep for consistency of project structure
    print(f"Directories created/verified: {UPLOAD_DIR}, {RESULTS_DIR}, {PROJECT_ROOT_FOR_MAIN_PY / 'celery_results'}")

@app.on_event("shutdown")
async def shutdown_event():
    if async_redis_client:
        await async_redis_client.close()
        print("FastAPI application shut down and Redis connection closed.")

# --- Root endpoint for API status ---
@app.get("/", summary="Root endpoint", tags=["Status"])
async def root():
    return {"message": "Welcome to the Bank Marketing Prediction API! Use /predict/single to get predictions or /docs for API documentation."}

# --- Single Prediction Endpoint ---
@app.post("/predict/single", summary="Predict for a single client", tags=["Prediction"])
async def predict_single(data: InputData):
    try:
        input_df = pd.DataFrame([data.model_dump()])
        expected_input_cols_for_pipeline = [
            'age', 'job', 'marital', 'education', 'default', 'balance',
            'housing', 'loan', 'contact', 'day', 'month', 'duration',
            'campaign', 'pdays', 'previous', 'poutcome'
        ]
        input_df = input_df.reindex(columns=expected_input_cols_for_pipeline, fill_value=None)
        predictions, probabilities = predict_with_pipeline(input_df)
        predicted_value = predictions[0]
        predicted_term_deposit_int = 1 if predicted_value == 'yes' else 0
        return {
            "predicted_term_deposit": predicted_term_deposit_int,
            "prediction_probability": float(probabilities[0])
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Prediction failed: {e}")

# --- Batch Prediction Endpoint ---
@app.post("/predict/batch_upload", status_code=status.HTTP_202_ACCEPTED, tags=["Batch Prediction"])
async def submit_batch_prediction(file: UploadFile = File(...)):
    """
    Submits a CSV file for asynchronous batch prediction.
    Returns a task_id and WebSocket URL for real-time status updates.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV files are allowed.")

    task_id = str(uuid.uuid4())
    file_location = UPLOAD_DIR / f"{task_id}_{file.filename}"

    try:
        with open(file_location, "wb") as file_object:
            while contents := await file.read(1024 * 1024):
                file_object.write(contents)

        try:
            # We still send task via Celery's send_task
            task = celery_app_instance.send_task('celery_worker.tasks.process_prediction_batch', args=[str(file_location), task_id])
            print(f"FastAPI: Enqueued Celery task with ID: {task.id} for batch: {task_id}")
        except Exception as e:
            print(f"FastAPI ERROR: Failed to enqueue Celery task: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to enqueue batch prediction task. Check Celery broker (Redis) connection: {e}")

        return JSONResponse(
            content={
                "message": "Batch prediction request received and is being processed.",
                "task_id": task_id,
                "status_url": f"/tasks/{task_id}/status",
                "websocket_url": f"/ws/task/{task_id}"
            },
            status_code=status.HTTP_202_ACCEPTED
        )
    except Exception as e:
        if file_location.exists():
            os.remove(file_location)
        print(f"FastAPI ERROR: Error submitting batch prediction or saving file: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to submit batch prediction: {e}")

# --- Task Status Polling Endpoint (NOW QUERIES REDIS DIRECTLY) ---
@app.get("/tasks/{task_id}/status", response_model=TaskStatusResponse, tags=["Batch Prediction"])
async def get_task_status(task_id: str):
    # --- IMPORTANT: No longer using celery_app_instance.AsyncResult(task_id) ---
    # We are now retrieving the status manually stored by the worker in Redis
    manual_status_key = f"task_status_manual:{task_id}"
    stored_status_json = await async_redis_client.get(manual_status_key)

    print(f"\n--- FastAPI DEBUG for Task {task_id} (Manual Redis Check) ---")
    print(f"  Redis key checked: {manual_status_key}")
    print(f"  Raw value from Redis: {stored_status_json}")
    
    status_message = "Processing..."
    results_url = None
    status_enum = "PENDING"

    if stored_status_json:
        try:
            status_data = json.loads(stored_status_json)
            status_enum = status_data.get("status", "UNKNOWN_STATUS")
            status_message = status_data.get("message", "Status updated.")
            results_url = status_data.get("results_download_url")

            # Translate internal statuses if needed (e.g., 'PROGRESS' from Pub/Sub)
            if status_enum == "SUCCESS":
                status_enum = "SUCCESS" # Ensure it's the schema's literal
            elif status_enum == "FAILURE":
                status_enum = "FAILURE" # Ensure it's the schema's literal
            else:
                status_enum = "PENDING" # Treat anything else as still pending/processing
        except json.JSONDecodeError:
            print(f"FastAPI ERROR: Could not decode JSON from Redis for task {task_id}.")
            status_message = "Error retrieving status (malformed data)."
            status_enum = "UNKNOWN_STATUS"
    else:
        # Key not found, so task is still pending or has not started processing yet
        status_enum = "PENDING"
        status_message = "Processing..."

    print(f"  Parsed Status: {status_enum}")
    print(f"  Parsed Message: {status_message}")
    print(f"  Parsed Results URL: {results_url}")
    print(f"-------------------------------------\n")
    
    return {"task_id": task_id, "status": status_enum, "message": status_message, "results_download_url": results_url}

# --- WebSocket Endpoint for Real-time Notifications ---
@app.websocket("/ws/task/{task_id}")
async def websocket_task_status(websocket: WebSocket, task_id: str):
    await websocket.accept()
    print(f"WebSocket connected for task: {task_id}")

    pubsub = async_redis_client.pubsub()
    await pubsub.subscribe(f"task_status:{task_id}")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                notification_data = message['data']
                print(f"Received WebSocket notification for task {task_id}: {notification_data}")
                await websocket.send_text(notification_data)
                
                if "Completed" in notification_data or "Failed" in notification_data:
                    break

            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for task: {task_id}")
    except Exception as e:
        print(f"WebSocket error for task {task_id}: {e}")
    finally:
        await pubsub.unsubscribe(f"task_status:{task_id}")
        print(f"WebSocket unsubscribed from Pub/Sub for task: {task_id}")
        try:
            await websocket.close()
        except RuntimeError:
            pass

# --- Endpoint to download results ---
@app.get("/results/{file_name}", tags=["Batch Prediction"])
async def download_results(file_name: str):
    file_path = RESULTS_DIR / file_name
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Results file not found.")
    
    return FileResponse(path=file_path, filename=file_name, media_type="text/csv")
