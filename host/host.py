import os
import time
import sys

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

print("Host script started.")  # Debug: Confirm script starts

try:
    # Get environment variables set in docker-compose.yml
    connected_to = os.getenv("CONNECTED_TO")
    weight_to_router = os.getenv("WEIGHT_TO_ROUTER")

    print(f"Environment variables - CONNECTED_TO: {connected_to}, WEIGHT_TO_ROUTER: {weight_to_router}")  # Debug

    if not connected_to or not weight_to_router:
        print("Error: Missing environment variables CONNECTED_TO or WEIGHT_TO_ROUTER")
        sys.exit(1)

    print(f"Host starting... Connected to {connected_to} with weight {weight_to_router}")

    # Placeholder: Replace this with actual host logic
    while True:
        print("Host is running...")
        time.sleep(10)

except Exception as e:
    print(f"Host failed with error: {e}")
    sys.exit(1)