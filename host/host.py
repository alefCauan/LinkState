import os
import time

# Get environment variables set in docker-compose.yml
connected_to = os.getenv("CONNECTED_TO")
weight_to_router = os.getenv("WEIGHT_TO_ROUTER")

print(f"Host starting... Connected to {connected_to} with weight {weight_to_router}")

# Placeholder: Replace this with actual host logic
while True:
    print("Host is running...")
    time.sleep(10)