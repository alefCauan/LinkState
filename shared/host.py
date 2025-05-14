import os
import time
import sys
import socket
import subprocess
import ipaddress

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

print("Host script started.")

try:
    # Get environment variables set in docker-compose.yml
    connected_to = os.getenv("CONNECTED_TO")
    print(f"Environment variables - CONNECTED_TO: {connected_to}")

    if not connected_to:
        print("Error: Missing environment variables CONNECTED_TO")
        sys.exit(1)

    print(f"Host starting... Connected to {connected_to}")

    # Discover the host's IP address
    def get_host_ip():
        try:
            # Get the IP of the eth0 interface
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            s.connect(("8.8.8.8", 80))  # Connect to a public IP to get the local IP
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            print(f"Error getting host IP: {e}")
            # Fallback: Parse from interface (similar to Bash)
            try:
                result = subprocess.run(["ip", "-4", "addr", "show", "eth0"], capture_output=True, text=True)
                for line in result.stdout.splitlines():
                    if "inet" in line:
                        ip = line.split()[1].split("/")[0]
                        return ip
            except Exception as e:
                print(f"Error parsing IP from eth0: {e}")
                return None

    host_ip = get_host_ip()
    if not host_ip:
        print("Error: Could not determine host IP")
        sys.exit(1)
    print(f"Host IP determined: {host_ip}")

    # Calculate the gateway (assuming .2 as the router IP in the same subnet)
    def get_gateway_ip(host_ip):
        try:
            ip_obj = ipaddress.ip_address(host_ip)
            network = ipaddress.ip_network(f"{host_ip}/24", strict=False)
            gateway = str(network.network_address + 1)  # First usable IP, typically .2 for router
            return gateway
        except ValueError as e:
            print(f"Error calculating gateway: {e}")
            return None

    gateway_ip = get_gateway_ip(host_ip)
    if not gateway_ip:
        print("Error: Could not determine gateway IP")
        sys.exit(1)
    print(f"Calculated gateway IP: {gateway_ip}")

    # Configure the default route
    try:
        subprocess.run(["ip", "route", "del", "default"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pass  # Ignore if no default route exists
    try:
        subprocess.run(["ip", "route", "add", "default", "via", gateway_ip], check=True, capture_output=True)
        print(f"Default gateway configured to {gateway_ip}")
    except subprocess.CalledProcessError as e:
        print(f"Error configuring default route: {e}")
        sys.exit(1)

    # Placeholder: Keep the host running; can be extended for packet sending/receiving
    while True:
        print(f"Host {host_ip} is running with gateway {gateway_ip}...")
        time.sleep(10)

except Exception as e:
    print(f"Host failed with error: {e}")
    sys.exit(1)