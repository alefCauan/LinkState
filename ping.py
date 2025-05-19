import subprocess
import re
from statistics import mean

def load_docker_compose() -> tuple:
    """
    Load docker-compose.yml and extract host IPs and container names.

    This function reads the docker-compose.yml file, identifies containers with 'h' in their names
    (assumed to be hosts), and maps their IPv4 addresses to their container names.

    Returns:
        dict: Mapping of IP address to container name.
        list: List of host container names (those containing 'h').

    Raises:
        FileNotFoundError: If docker-compose.yml is not found in the current directory.
        Exception: For other potential file processing errors.
    """
    ip_to_container = {}
    hosts = []
    current_container = None
    
    try:
        with open("docker-compose.yml", "r") as f:
            lines = f.readlines()
            for line in lines:
                # Extract container name
                container_match = re.search(r"container_name:\s*\"?([^\"\n]+)", line)
                if container_match:
                    current_container = container_match.group(1)
                    if "h" in current_container.lower():
                        hosts.append(current_container)
                
                # Extract IPv4 address and associate with the current container
                ip_match = re.search(r"ipv4_address:\s*\"?([^\"\n]+)", line)
                if ip_match and current_container:
                    ip = ip_match.group(1)
                    ip_to_container[ip] = current_container
    except FileNotFoundError:
        print("Error: docker-compose.yml not found.")
        return {}, []
    except Exception as e:
        print(f"Error processing the file: {e}")
        return {}, []
    
    return ip_to_container, hosts

def test_connectivity(ip_to_container: dict, hosts: list) -> None:
    """
    Test ping connectivity between all pairs of hosts and display detailed results.

    This function performs ping tests from each host to all other hosts (excluding self-ping),
    collects latency data for successful pings, and provides a formatted output including
    per-host and global statistics.

    Args:
        ip_to_container (dict): Mapping of IP address to container name.
        hosts (list): List of host container names.

    Note:
        The ping command uses -c 1 (1 packet) and -W 1 (1-second timeout) for efficiency.
        Latency is extracted from ping output in milliseconds.
    """
    global_success = 0
    global_fail = 0
    total_tests = 0
    global_latencies = []
    per_host_stats = {}

    print("=" * 50)
    print(f"{'Host Connectivity Test':^50}")
    print("=" * 50)
    
    for origin in hosts:
        print(hosts)
        print()
        print("-" * 50)
        print(f"{'Pings from ' + origin:^50}")
        print("-" * 50)
        print(f"{'Destination IP':<15} {'Container':<12}  {'Status':<8} {'Latency':<10}")
        print("-" * 50)


        success = 0
        fail = 0
        total_tests += len(ip_to_container) - 1  # Exclude self-ping
        latencies = []

        print(ip_to_container)

        for dest_ip in ip_to_container.keys():
            dest_name = ip_to_container[dest_ip]
            if origin == dest_name:
                continue
            
            try:
                result = subprocess.run(
                    ["docker", "exec", origin, "ping", "-c", "1", "-W", "1", dest_ip],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                if result.returncode == 0:
                    latency_match = re.search(r"time=([\d.]+)\s*ms", result.stdout)
                    latency = float(latency_match.group(1)) if latency_match else 0.0
                    print(f"{dest_ip:<15} {dest_name:<12} {'✔️':<8} {latency:>6.2f} ms")
                    success += 1
                    global_success += 1
                    latencies.append(latency)
                    global_latencies.append(latency)
                else:
                    print(f"{dest_ip:<15} {dest_name:<12} {'❌':<8} {'-':<10}")
                    fail += 1
                    global_fail += 1
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                print(f"{dest_ip:<15} {dest_name:<12} {'❌':<8} {'-':<10}")
                fail += 1
                global_fail += 1
        
        # Print summary for the current host
        total = success + fail
        loss_percent = (fail / total) * 100 if total > 0 else 0
        per_host_stats[origin] = {"success": success, "total": total}
        
        print()
        print("=" * 23 + f"{origin:^5}" + "=" * 22)
        print(f"│ {'Successes:':<20} {success:>21}/{total:<4}│")
        print(f"│ {'Loss Rate:':<20} {loss_percent:>24.2f}% │")
        print("=" * 50)

    
    print(f"\n{'Global Statistics':^50}")
    print("=" * 50)
    print(f"│ {'Total Tests:':<20} {total_tests:>25} │")
    print(f"│ {'Successes:':<20} {global_success:>25} │")
    print(f"│ {'Failures:':<20} {global_fail:>25} │")
    
    if total_tests > 0:
        global_loss_percent = (global_fail / total_tests) * 100
        print(f"│ {'Global Loss Rate:':<20} {global_loss_percent:>24.2f}% │")
    else:
        print(f"│ {'Global Loss Rate:':<20} {'N/A':>25} │")
    
    if global_latencies:
        avg_latency = mean(global_latencies)
        print(f"│ {'Average Latency:':<20} {avg_latency:>23.2f} ms│")
    else:
        print(f"│ {'Average Latency:':<20} {'N/A':>25} │")
    print("=" * 50)
    
    print(f"\n{'Success Rate by Origin':^50}")
    print("-" * 50)
    print(f"{'Origin':<12} {'Success':<8} {'Total':<8} {'Rate (%)':<10}")
    print("-" * 50)
    for origin, stats in per_host_stats.items():
        success_rate = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
        print(f"{origin:<12} {stats['success']:<8} {stats['total']:<8} {success_rate:>6.2f}%")

def main():
    """
    Main function to run the connectivity test.

    This function orchestrates the loading of the docker-compose.yml file and the execution
    of connectivity tests between hosts.

    Note:
        The script assumes that Docker containers are already running. Use 'docker compose up -d'
        beforehand if necessary.
    """
    ip_to_container, hosts = load_docker_compose()
    if not hosts:
        print("No hosts found in docker-compose.yml. Verify the file and container names (must contain 'h').")
        return
    
    test_connectivity(ip_to_container, hosts)

if __name__ == "__main__":
    main()