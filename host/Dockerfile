# Use a lightweight Python base image
FROM python:3.9-slim

# Install system dependencies (e.g., iproute2 for the ip command)
RUN apt-get update && apt-get install -y iproute2 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the host script
# COPY  host/host.py .

# Command to run the host script
CMD ["python", "host.py"]