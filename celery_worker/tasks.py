# celery_worker/tasks.py
import os
import pandas as pd
import joblib
from pathlib import Path
import warnings
import json
import redis.asyncio as aioredis # Use async Redis client
import asyncio

from celery_worker.celery_app import celery_app

# Suppress scikit-learn warnings about feature names (if using an older version)
warnings.filterwarnings("ignore", message="X does not have valid feature names, but StandardScaler was fitted with feature names")

# --- Define directories ---
UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("results")
MODEL_ASSETS_DIR = Path("model")

# Ensure these directories exist (worker needs them)
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)
MODEL_ASSETS_DIR.mkdir(exist_ok=True)

# --- Load the full ML pipeline once when the worker starts ---
full_pipeline = None
try:
    FULL_PIPELINE_PATH = MODEL_ASSETS_DIR / "full_pipeline.pkl"
    full_pipeline = joblib.load(FULL_PIPELINE_PATH)
    print(f"Celery Worker: ML Full Pipeline loaded successfully from '{FULL_PIPELINE_PATH}'.")
except FileNotFoundError:
    print("Celery Worker FATAL ERROR: full_pipeline.pkl not found. Batch predictions will fail.")
except Exception as e:
    print(f"Celery Worker ERROR: An unexpected error occurred while loading the full pipeline: {e}")

# Global aioredis client for Pub/Sub and manual status storage (initialized once for worker process)
# We will manage its lifecycle carefully
async_redis_client = None

# Define the exact order of columns that your full pipeline expects in the raw input CSV
EXPECTED_RAW_INPUT_COLS_FOR_PIPELINE = [
    'age', 'job', 'marital', 'education', 'default', 'balance',
    'housing', 'loan', 'contact', 'day', 'month', 'duration',
    'campaign', 'pdays', 'previous', 'poutcome'
]


# --- Helper function to publish task status via Redis Pub/Sub ---
async def publish_task_status_internal(task_id: str, status_message: str):
    """Publishes a status message to a Redis channel for a specific task."""
    global async_redis_client
    redis_url = os.getenv("REDIS_URL", "redis://host.docker.internal:6379/0")
    
    try:
        # If client not connected, try to establish/re-establish connection
        if async_redis_client is None or not (await async_redis_client.ping()): # Ping to check connection
            async_redis_client = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
            await async_redis_client.ping() # Ensure connection is active
            print(f"Celery Worker: Reconnected to Redis successfully for Pub/Sub.")
        
        await async_redis_client.publish(f"task_status:{task_id}", status_message)
        # print(f"Celery Worker Pub/Sub: Published '{status_message}' for task {task_id}")
    except Exception as e:
        print(f"Celery Worker ERROR: Failed to publish status for task {task_id}: {e}")
        # Optionally close client if it seems broken
        if async_redis_client:
            try:
                await async_redis_client.close()
            except Exception as close_e:
                print(f"Celery Worker ERROR: Failed to close broken Redis client: {close_e}")
            finally:
                async_redis_client = None


# --- Helper function to manually store final task result in Redis ---
async def store_final_task_result_in_redis(task_id: str, status: str, result_data: dict = None, error_message: str = None):
    """
    Manually stores the final task status and result data in a dedicated Redis key.
    This bypasses Celery's built-in result backend.
    """
    global async_redis_client
    redis_url = os.getenv("REDIS_URL", "redis://host.docker.internal:6379/0")

    try:
        # If client not connected, try to establish/re-establish connection
        if async_redis_client is None or not (await async_redis_client.ping()): # Ping to check connection
            async_redis_client = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
            await async_redis_client.ping() # Ensure connection is active
            print(f"Celery Worker: Reconnected to Redis for final result storage.")

        data_to_store = {
            "status": status,
            "results_download_url": None, # Default to None
            "message": "Processing...",   # Default message
            "task_id": task_id
        }
        
        if status == "SUCCESS":
            data_to_store["message"] = result_data.get("message", "Batch prediction completed successfully.")
            if result_data and result_data.get("results_file_name"):
                data_to_store["results_download_url"] = f"/results/{result_data['results_file_name']}"
        elif status == "FAILURE":
            data_to_store["message"] = error_message if error_message else "Task failed due to an unknown error."
        
        # Store as JSON string in a dedicated key
        await async_redis_client.set(f"task_status_manual:{task_id}", json.dumps(data_to_store))
        # Optional: Set an expiry for the key if you don't want results to live forever
        # await async_redis_client.expire(f"task_status_manual:{task_id}", 3600) # Expire after 1 hour
        print(f"Celery Worker DEBUG: Manual status stored in Redis for task {task_id}: {status}")

    except Exception as e:
        print(f"Celery Worker ERROR: Failed to manually store result for task {task_id} in Redis: {e}")
        # Optionally close client if it seems broken
        if async_redis_client:
            try:
                await async_redis_client.close()
            except Exception as close_e:
                print(f"Celery Worker ERROR: Failed to close broken Redis client: {close_e}")
            finally:
                async_redis_client = None


@celery_app.task(bind=True)
def process_prediction_batch(self, file_location: str, task_id: str):
    """
    Celery task to process a batch prediction request from a CSV file.
    It reads the CSV, applies the ML pipeline, and saves results to a new CSV.
    This version manually stores the final status/result in Redis.
    """
    print(f"Celery Worker DEBUG: Task {task_id} received! Beginning processing.")

    # Call Pub/Sub for initial status
    asyncio.run(publish_task_status_internal(task_id, "Status: Task received and starting..."))

    if full_pipeline is None:
        error_msg = "ML Full Pipeline not loaded. Cannot process batch prediction."
        print(f"Celery Worker ERROR: {error_msg}")
        asyncio.run(publish_task_status_internal(task_id, f"Failed: {error_msg}"))
        asyncio.run(store_final_task_result_in_redis(task_id, "FAILURE", error_message=error_msg))
        raise Exception(error_msg) # Re-raise to ensure Celery marks task as failed internally

    try:
        asyncio.run(publish_task_status_internal(task_id, "Status: Reading CSV file..."))
        self.update_state(state='PROGRESS', meta={'message': 'Reading CSV file'})
        print(f"Celery Worker DEBUG: Task {task_id} status updated to PROGRESS (Reading CSV).")

        input_df = pd.read_csv(file_location)
        input_df_processed_for_pipeline = input_df.reindex(columns=EXPECTED_RAW_INPUT_COLS_FOR_PIPELINE)
        
        print(f"Celery Worker DEBUG: Input DataFrame columns before pipeline prediction: {input_df_processed_for_pipeline.columns.tolist()}")
        print(f"Celery Worker DEBUG: Input DataFrame shape before pipeline prediction: {input_df_processed_for_pipeline.shape}")

        asyncio.run(publish_task_status_internal(task_id, "Status: Performing predictions..."))
        self.update_state(state='PROGRESS', meta={'message': 'Performing predictions'})
        print(f"Celery Worker DEBUG: Task {task_id} status updated to PROGRESS (Performing predictions).")

        predictions = full_pipeline.predict(input_df_processed_for_pipeline)
        probabilities = full_pipeline.predict_proba(input_df_processed_for_pipeline)[:, 1]

        input_df['predicted_term_deposit'] = predictions
        input_df['prediction_probability'] = probabilities

        original_filename = Path(file_location).name
        results_filename = f"results_{task_id}_{original_filename}"
        results_file_path = RESULTS_DIR / results_filename

        input_df.to_csv(results_file_path, index=False)

        final_result_meta = {
            'message': 'Batch prediction completed successfully.',
            'results_file_name': results_filename
        }
        
        asyncio.run(publish_task_status_internal(task_id, "Status: Completed!"))
        asyncio.run(store_final_task_result_in_redis(task_id, "SUCCESS", result_data=final_result_meta))
        print(f"Celery Worker DEBUG: Task {task_id} completed. Results saved to {results_file_path}")

        # The return value for Celery's internal backend (not used by FastAPI in this approach)
        return final_result_meta
    
    except Exception as e:
        error_msg = f"Error during batch prediction for task {task_id}: {e}"
        print(f"Celery Worker ERROR: {error_msg}")
        asyncio.run(publish_task_status_internal(task_id, f"Failed: {error_msg}"))
        asyncio.run(store_final_task_result_in_redis(task_id, "FAILURE", error_message=error_msg))
        raise

    finally:
        file_to_delete = Path(file_location)
        if file_to_delete.exists():
            try:
                file_to_delete.unlink()
                print(f"Celery Worker: Deleted uploaded file: {file_to_delete}")
            except OSError as e:
                print(f"Celery Worker ERROR: Failed to delete uploaded file {file_to_delete}: {e}")
            except Exception as e:
                print(f"Celery Worker ERROR: An unexpected error occurred while deleting file {file_to_delete}: {e}")
        else:
            print(f"Celery Worker: Uploaded file not found, skipping deletion: {file_to_delete}")
