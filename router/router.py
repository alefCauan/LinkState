import os
import time

# Get environment variables set in docker-compose.yml
connected_to_subnet = os.getenv("CONNECTED_TO_SUBNET")
print(f"Router starting... Connected to subnet {connected_to_subnet}")

# Print connections to other routers
for key, value in os.environ.items():
    if key.startswith("CONNECTED_TO_ROUTER_"):
        router_name = key.replace("CONNECTED_TO_ROUTER_", "")
        print(f"Connected to {router_name} with weight {value}")

# Placeholder: Replace this with actual router logic (e.g., Link State Routing)
while True:
    print("Router is running...")
    time.sleep(10)