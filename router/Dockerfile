# Use a lightweight Python base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy the router script and network topology
COPY router/router.py .
COPY network_topology.json .

# Command to run the router script
CMD ["python", "router.py"]