# Use a lightweight Python base image
FROM python:3.9-slim

# Install system dependencies (e.g., iproute2 for ip command and iputils-ping for ping)
RUN apt-get update && apt-get install -y iproute2 iputils-ping && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements (if any)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Copy the host script
# COPY  host/host.py .

# Command to run the host script
CMD ["python", "host.py"]