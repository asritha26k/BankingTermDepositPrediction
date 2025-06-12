# celery_worker/celery_app.py
from celery import Celery
import os
from pathlib import Path

# --- REMOVED: from celery_worker.celery_app import celery_app ---
# This line caused the circular import. celery_app is defined below.

# Ensure consistent Redis URL for both broker and backend
REDIS_URL = os.getenv("REDIS_URL", "redis://host.docker.internal:6379/0")

# Define directories (even if not used for backend directly, needed for other parts)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FILESYSTEM_BACKEND_DIR = PROJECT_ROOT / "celery_results"
FILESYSTEM_BACKEND_DIR.mkdir(exist_ok=True) # Keep this for consistency of project structure

celery_app = Celery(
    "term_deposit_predictor_celery_app", # A unique name for your Celery app
    broker=REDIS_URL,
    backend=REDIS_URL # Back to Redis backend
)

celery_app.conf.update(
    task_acks_late=True, # Recommended for long-running tasks, acknowledges task after completion
    worker_prefetch_multiplier=1, # Worker fetches one task at a time for long tasks
    task_track_started=True, # Allows tracking "started" state for tasks
    timezone='Asia/Kolkata', # Set your desired timezone
    enable_utc=False, # Use local timezone
    # result_expires=3600, # Optional: uncomment to auto-delete results from Redis after 1 hour

    # --- CRITICAL NEW SETTINGS FOR RESULT SERIALIZATION ---
    result_serializer='json', # Explicitly use JSON for results
    task_serializer='json',   # Explicitly use JSON for tasks
    accept_content=['json'],  # Accept content only in JSON format
)

celery_app.autodiscover_tasks(['celery_worker']) # This line tells Celery to find tasks

# Optional logging config (as before)
# from celery.signals import setup_logging
# @setup_logging.connect
# def config_loggers(*args, **kwargs):
#     from logging.config import dictConfig
#     from logging import getLogger
#     dictConfig({
#         'version': 1,
#         'disable_existing_loggers': False,
#         'formatters': {
#             'standard': {
#                 'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
#             },
#         },
#         'handlers': {
#             'console': {
#                 'class': 'logging.StreamHandler',
#                 'formatter': 'standard',
#             },
#         },
#         'loggers': {
#             'celery': {
#                 'handlers': ['console'],
#                 'level': 'INFO',
#                 'propagate': False
#             },
#             'celery_worker.tasks': { # Logger for your tasks module
#                 'handlers': ['console'],
#                 'level': 'INFO',
#                 'propagate': False
#             }
#         },
#         'root': {
#             'handlers': ['console'],
#             'level': 'WARNING',
#         }
#     })
