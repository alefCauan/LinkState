import os
import time
import sys

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

print("Host script started.")  # Debug: Confirm script starts

try:
    # Get environment variables set in docker-compose.yml
    connected_to = os.getenv("CONNECTED_TO")

    print(f"Environment variables - CONNECTED_TO: {connected_to}")  # Debug

    if not connected_to:
        print("Error: Missing environment variables CONNECTED_TO")
        sys.exit(1)

    print(f"Host starting... Connected to {connected_to}")

    # Placeholder: Replace this with actual host logic
    while True:
        print("Host is running...")
        time.sleep(10)

except Exception as e:
    print(f"Host failed with error: {e}")
    sys.exit(1)