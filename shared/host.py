import os
import time
import sys
import socket
import subprocess
import ipaddress

""" ----------------------------------------------------------------------------
    This script implements a network host configuration system that:
    - Retrieves network configuration from environment variables
    - Discovers the host's IP address
    - Calculates and configures the default gateway
    - Maintains a continuous running state

    Dependencies:
    - Python standard libraries
    - Linux networking tools (ip command)
"""

def get_host_ip():
    """
    Discovers the host's IP address using either socket connection or interface parsing.
    
    Returns:
        str: The host's IP address or None if discovery fails
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        print(f"Error getting host IP: {e}")
        try:
            result = subprocess.run(["ip", "-4", "addr", "show", "eth0"], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if "inet" in line:
                    return line.split()[1].split("/")[0]
        except Exception as e:
            print(f"Error parsing IP from eth0: {e}")
            return None


def configure_gateway(gateway_ip):
    """
    Configures the system's default gateway.
    
    Args:
        gateway_ip (str): The gateway IP address to configure
    
    Returns:
        bool: True if configuration succeeds, False otherwise
    """
    try:
        subprocess.run(["ip", "route", "del", "default"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pass
 
    try:
        subprocess.run(["ip", "route", "add", "default", "via", gateway_ip], check=True, capture_output=True)
        print(f"Default gateway configured to {gateway_ip}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error configuring default route: {e}")
        return False

def main():
    """
    Main function that orchestrates the host configuration and running process.
    """
    sys.stdout.reconfigure(line_buffering=True)
    print("Host script started.")

    try:
        connected_to = os.getenv("CONNECTED_TO")
        gateway_ip = os.getenv("GATEWAY_IP")  # Get gateway IP from environment
        print(f"Environment variables - CONNECTED_TO: {connected_to}, GATEWAY_IP: {gateway_ip}")

        if not connected_to or not gateway_ip:
            print("Error: Missing environment variables CONNECTED_TO or GATEWAY_IP")
            return 1

        print(f"Host starting... Connected to {connected_to}")

        host_ip = get_host_ip()
        if not host_ip:
            print("Error: Could not determine host IP")
            return 1
        print(f"Host IP determined: {host_ip}")

        if not configure_gateway(gateway_ip):
            return 1

        while True:
            print(f"Host {host_ip} is running with gateway {gateway_ip}...")
            time.sleep(10)

    except Exception as e:
        print(f"Host failed with error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())