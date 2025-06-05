# Use official Python image as base
FROM python:3.10-slim

# Set working directory inside container
WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your app code
COPY ./app ./app
COPY ./model ./model

# Expose port (same as your uvicorn run port)
EXPOSE 8000
# Command to run the app with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
