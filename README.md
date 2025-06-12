# 💰 Bank Term Deposit Prediction API

This project provides a robust and scalable API for predicting whether a client will subscribe to a term deposit, based on bank marketing campaign data. It leverages **asynchronous task processing** for handling large batch predictions efficiently, offering **real-time status updates** and **downloadable results**.

---

## ✨ Features

- **Single Prediction**: Instantly predict for individual client data.
- **Asynchronous Batch Prediction**: Upload large CSV datasets for predictions that run in the background.
- **Real-time Status Updates**: Monitor the progress of batch prediction tasks via WebSockets.
- **Direct Status Retrieval**: Poll an API endpoint to get the final status and result download link for your batch tasks.
- **Downloadable Results**: Access and download processed CSV files containing predictions directly from the API.
- **Containerized Broker**: Uses Docker for a reliable and isolated Redis instance.

---

## 🛠️ Technologies Used

- **FastAPI**: High-performance web framework for building the API.
- **Celery**: Distributed task queue for asynchronous background processing of batch predictions.
- **Redis**: Serves as both the Celery broker and for real-time WebSocket Pub/Sub, as well as for manual task status storage.
- **Pandas**: For data manipulation and CSV processing.
- **Scikit-learn**: For running the ML prediction pipeline (`full_pipeline.pkl`).
- **Docker**: For containerizing Redis.
- **python-dotenv**: For managing environment variables.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- `pip` (Python package installer)
- Docker Desktop (or Docker Engine on Linux)

### 📦 Installation

Clone the repository:

```bash
git clone <your-repository-url>
cd bank-api


###activation
python -m venv venv
.\venv\Scripts\activate      # On Windows
# source venv/bin/activate   # On macOS/Linux

###dependencies
pip install -r requirements.txt
pip install python-dotenv

###Environment variables

REDIS_URL=redis://host.docker.internal:6379/0


###Using Docker

docker start my-redis
if not created
docker run --name my-redis -p 6379:6379 -d redis/redis-stack:latest

###Celery Worker

celery -A celery_worker.celery_app worker --loglevel=info --pool=solo

###FASTAPI
uvicorn main:app --reload
http://127.0.0.1:8000/docs


