# Use official lightweight Python image
FROM python:3.10-slim
 
# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Ensure logs are shown immediately
ENV PYTHONUNBUFFERED=1
 
# Set working directory inside container
WORKDIR /app
 
# Install system dependencies (optional but recommended)
RUN apt-get update && apt-get install -y \
    build-essential \
    ca-certificates \
&& rm -rf /var/lib/apt/lists/*
 
# Copy requirements file first (for better Docker caching)
COPY requirements.txt .
 
# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
 
# Copy the rest of the application code
COPY . .
 
# Expose FastAPI port
EXPOSE 9061
 
# Run FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9061"]
