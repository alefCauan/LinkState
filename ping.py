import subprocess
import time
import yaml

def test_ping(num_routers=5):
    """
    Test ping connectivity between all pairs of hosts using their IP addresses.

    Args:
        num_routers (int): Number of routers in the topology (default: 5).
    """

    # Load docker-compose.yml to get host IPs
    print("Loading network configuration...")
    with open("docker-compose.yml", "r") as f:
        compose_data = yaml.safe_load(f)

    host_ips = {}
    for service, config in compose_data["services"].items():
        if service.startswith("h"):
            for network, net_config in config["networks"].items():
                if "ipv4_address" in net_config:
                    host_ips[service] = net_config["ipv4_address"]

    # Start containers
    print("Starting containers...")
    subprocess.run(["docker", "compose", "up", "-d"], check=True)

    # Wait for network convergence
    print("Waiting for network convergence...")
    time.sleep(40)  # Increased to 30 seconds for better convergence

    # Test ping between all pairs of hosts using IPs
    hosts = [f"h{i}" for i in range(1, num_routers * 2 + 1)]
    results = []

    for src in hosts:
        for dst in hosts:
            if src != dst:
                src_ip = host_ips[src]
                dst_ip = host_ips[dst]
                print(f"Testing ping from {src} ({src_ip}) to {dst} ({dst_ip})...")
                try:
                    result = subprocess.run(
                        ["docker", "exec", src, "ping", "-c", "4", "-i", "0.2", "-W", "1", dst_ip],
                        capture_output=True,
                        text=True
                    )
                    if "4 received" in result.stdout:
                        # Find the rtt line
                        rtt_line = [line for line in result.stdout.split("\n") if "rtt" in line][0]
                        # Extract the values after "rtt min/avg/max/mdev = "
                        values = rtt_line.split("=")[1].strip().split("/")
                        avg_latency = float(values[1])  # avg is the second value
                        results.append(f"{src} ({src_ip}) -> {dst} ({dst_ip}): Success (avg latency: {avg_latency:.2f} ms)")
                    else:
                        results.append(f"{src} ({src_ip}) -> {dst} ({dst_ip}): Failed")
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                    results.append(f"{src} ({src_ip}) -> {dst} ({dst_ip}): Failed (Error: {str(e)})")

    # Stop containers
    print("Stopping containers...")
    subprocess.run(["docker", "compose", "down", "--remove-orphans"], check=True)
    subprocess.run(["docker", "network", "prune", "-f"], check=True)

    # Print results
    print("\nPing Test Results:")
    for result in results:
        print(result)

if __name__ == "__main__":
    test_ping(num_routers=5)