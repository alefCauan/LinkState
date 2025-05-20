# host/Dockerfile
FROM python:3.9-slim  

# Install system dependencies (e.g., iproute2 for ip, iputils-ping for ping, traceroute)
RUN apt-get update && apt-get install -y \
  iproute2 \
  iputils-ping \
  net-tools \
  nano \
  curl \
  traceroute \
  && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements (if any)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script
COPY host.py /app/host.py

# Run the script
CMD ["python", "/app/host.py"]