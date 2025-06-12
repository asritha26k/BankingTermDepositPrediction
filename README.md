Bank Term Deposit Prediction API
This project provides a robust and scalable API for predicting whether a client will subscribe to a term deposit, based on bank marketing campaign data. It leverages asynchronous task processing for handling large batch predictions efficiently, offering real-time status updates and downloadable results.

✨ Features
Single Prediction: Instantly predict for individual client data.

Asynchronous Batch Prediction: Upload large CSV datasets for predictions that run in the background.

Real-time Status Updates: Monitor the progress of batch prediction tasks via WebSockets.

Direct Status Retrieval: Poll an API endpoint to get the final status and result download link for your batch tasks.

Downloadable Results: Access and download processed CSV files containing predictions directly from the API.

Containerized Broker: Uses Docker for a reliable and isolated Redis instance.

🛠️ Technologies Used
FastAPI: High-performance web framework for building the API.

Celery: Distributed task queue for asynchronous background processing of batch predictions.

Redis: Serves as both the Celery broker (task queue) and for real-time WebSocket Pub/Sub, as well as for manual task status storage.

Pandas: Data manipulation and analysis, primarily for handling CSV data.

Scikit-learn: Machine Learning library for the prediction pipeline (full_pipeline.pkl).

Docker: For containerizing the Redis instance.

python-dotenv: For managing environment variables.

🚀 Getting Started
Follow these steps to set up and run the project locally.

Prerequisites
Python 3.8+

pip (Python package installer)

Docker Desktop (or Docker Engine on Linux) – Ensure it's running.

📦 Installation
Clone the repository:

git clone <your-repository-url>
cd bank-api

Create and activate a Python virtual environment:

python -m venv venv
.\venv\Scripts\activate  # On Windows
# source venv/bin/activate  # On macOS/Linux

Install Python dependencies:

pip install -r requirements.txt

🔑 Environment Variables
Create a file named .env in the root directory of your project (bank-api/). Add the following line to it:

REDIS_URL=redis://host.docker.internal:6379/0

Note: host.docker.internal is used to allow your Python application (running on your host machine) to connect to Redis inside a Docker container on Windows/macOS. For Linux, you might need to use your host's IP address or the Docker network gateway IP.

🏃 Running the Application
You'll need three separate terminal windows open, all from your project's root directory (E:\bank-api\), with your venv activated for the Python processes.

Start your Redis Docker Container:

Open Terminal 1.

Make sure Docker Desktop is running.

Run:

docker start my-redis

(If you haven't created the my-redis container yet, you'd need to run docker run --name my-redis -p 6379:6379 -d redis/redis-stack:latest once.)

Start your Celery Worker:

Open Terminal 2.

Activate your venv: .\venv\Scripts\activate

Run:

celery -A celery_worker.celery_app worker --loglevel=info --pool=solo

(The --pool=solo is used for stability on Windows; see "Important Notes" below.)

Start your FastAPI Application:

Open Terminal 3.

Activate your venv: .\venv\Scripts\activate

Run:

uvicorn main:app --reload

Your application should now be running!

💡 API Endpoints
Access the interactive API documentation (Swagger UI) in your browser at:
http://127.0.0.1:8000/docs

Core Endpoints
1. POST /predict/single
Description: Get an immediate prediction for a single client's data.

Input: JSON object conforming to InputData schema.

Output: Predicted term deposit (0 or 1) and its probability.

2. POST /predict/batch_upload
Description: Upload a CSV file containing multiple client records for asynchronous prediction.

Input: CSV file (UploadFile).

Output: Returns a 202 Accepted response with a task_id, a status_url to poll for updates, and a websocket_url for real-time notifications.

Example Input CSV (batch_data.csv):

age,job,marital,education,default,balance,housing,loan,contact,day,month,duration,campaign,pdays,previous,poutcome
35,management,married,university.degree,no,1200,yes,no,cellular,5,may,120,2,999,0,nonexistent
42,technician,married,high.school,no,50,yes,no,cellular,10,aug,200,1,999,0,nonexistent

3. GET /tasks/{task_id}/status
Description: Poll this endpoint to check the current status of a batch prediction task.

Path Parameter: {task_id} (the ID returned by /predict/batch_upload).

Output: Returns JSON with task_id, status (PENDING, SUCCESS, FAILURE), message, and results_download_url (if successful).

4. GET /results/{file_name}
Description: Download the generated CSV file containing the batch predictions.

Path Parameter: {file_name} (obtained from the results_download_url in the status response).

⚠️ Important Notes
Celery Concurrency (--pool=solo vs. --pool=threads):

Currently, the Celery worker runs with --pool=solo for maximum stability on Windows. This means it processes tasks sequentially (one at a time).

For concurrent processing (handling multiple batch prediction requests simultaneously), you can change the Celery worker command to use --pool=threads:

celery -A celery_worker.celery_app worker --loglevel=info --pool=threads

This is generally recommended for Windows environments.

Manual Redis Status Storage:

Due to persistent issues with Celery's default result backend not reliably reporting SUCCESS status on Windows, this project implements a manual status storage mechanism in Redis.

The Celery worker directly writes the final task status and result to a Redis key prefixed with task_status_manual: (e.g., task_status_manual:YOUR_TASK_ID).

The FastAPI status endpoint then queries this specific key directly. This ensures robust status reporting even if Celery's standard backend is problematic.

Scikit-learn InconsistentVersionWarning:

You might see warnings about InconsistentVersionWarning related to scikit-learn. This occurs because the pre-trained ML model (full_pipeline.pkl) was saved with a different version of scikit-learn than what you have installed.

For production, it's best practice to ensure the exact same version of scikit-learn is used for both training and deployment. For development, this warning is generally informational and should not prevent functionality.
