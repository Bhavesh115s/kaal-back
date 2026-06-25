FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Upgrade pip
RUN python -m pip install --upgrade pip

# Install dependencies
RUN python -m pip install --no-cache-dir -r requirements.txt

# Debug: confirm Razorpay is installed
RUN python -m pip show razorpay

COPY . .

EXPOSE 9061

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9061"]