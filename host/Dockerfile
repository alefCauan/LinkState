# Use a lightweight Python base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy the host script
COPY  host/host.py .

# Command to run the host script
CMD ["python", "host.py"]