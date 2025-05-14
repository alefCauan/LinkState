import json
import yaml
from collections import defaultdict
from typing import Dict, List, Set, Tuple

def read_topology(filename: str) -> Dict:
    """
    Read network topology from a JSON file.
    
    Args:
        filename (str): Path to the JSON topology file
        
    Returns:
        dict: Dictionary containing network topology data
    """
    with open(filename, "r") as f:
        return json.load(f)

def extract_router_connections(topology: Dict) -> Tuple[Set[str], List[Tuple[str, str, int]], List[Dict]]:
    """
    Extract router connections and information from topology.
    
    Args:
        topology (dict): Network topology dictionary
        
    Returns:
        tuple: Contains:
            - set of router names
            - list of connections (origin, destination, weight)
            - list of subnet information
    """
    routers = set()
    connections = []
    
    for subnet in topology["subnets"]:
        router = subnet["router"]
        routers.add(router)
        
    for edge in topology["edges"]:
        if edge["node1"].startswith("R") and edge["node2"].startswith("R"):
            connections.append((edge["node1"], edge["node2"], edge["weight"]))
            routers.update([edge["node1"], edge["node2"]])
            
    return routers, connections, topology["subnets"]

def create_connection_map(connections: List[Tuple[str, str, int]]) -> Dict[str, List[str]]:
    """
    Create a map of router connections.
    
    Args:
        connections (list): List of router connections
        
    Returns:
        dict: Dictionary mapping routers to their connections
    """
    connections_per_router = defaultdict(list)
    for origin, dest, weight in connections:
        connections_per_router[origin].append(dest)
        connections_per_router[dest].append(origin)
    return connections_per_router

def create_network_structure(connections: List[Tuple[str, str, int]], subnet_count: int) -> Tuple[Dict, Dict, Dict, int]:
    """
    Create network structure with subnets and IP mappings.
    
    Args:
        connections (list): List of router connections
        subnet_count (int): Initial subnet counter
        
    Returns:
        tuple: Contains:
            - networks dictionary
            - IP mapping dictionary
            - subnet cost dictionary
            - updated subnet count
    """
    subnet_base = "10.10.{0}.0/24"
    ip_base = "10.10.{0}.{1}"
    networks = {}
    ip_map = defaultdict(dict)
    subnet_cost = {}
    
    for origin, dest, weight in connections:
        net_name = f"{origin.lower()}_{dest.lower()}_net"
        subnet = subnet_base.format(subnet_count)
        ip_map[origin][net_name] = ip_base.format(subnet_count, 2)
        ip_map[dest][net_name] = ip_base.format(subnet_count, 3)
        networks[net_name] = subnet
        subnet_cost[net_name] = weight
        subnet_count += 1
        
    return networks, ip_map, subnet_cost, subnet_count

def create_router_service(router: str, ip_map: Dict, subnet_cost: Dict, subnet_count: int) -> Tuple[Dict, str, str, str]:
    """
    Create a router service configuration.
    
    Args:
        router (str): Router name
        ip_map (dict): IP mapping dictionary
        subnet_cost (dict): Subnet cost dictionary
        subnet_count (int): Current subnet count
        
    Returns:
        tuple: Contains:
            - router service configuration
            - host network name
            - host subnet
            - gateway IP
    """
    host_subnet_base = "192.168.{0}.0/24"
    host_ip_base = "192.168.{0}.{1}"
    
    service = {
        "build": {"context": ".", "dockerfile": "router/Dockerfile"},
        "container_name": router.lower(),
        "environment": {"CONTAINER_NAME": router.lower()},
        "volumes": ["./shared:/app"],
        "networks": {},
        "cap_add": ["NET_ADMIN"]
    }
    
    for net, ip in ip_map[router].items():
        service["networks"][net] = {"ipv4_address": ip}
        service["environment"][f"CUSTO_{net}"] = str(subnet_cost[net])
    
    host_net = f"{router.lower()}_hosts_net"
    host_subnet = host_subnet_base.format(subnet_count)
    gateway_ip = host_ip_base.format(subnet_count, 2)
    service["networks"][host_net] = {"ipv4_address": gateway_ip}
    
    return service, host_net, host_subnet, gateway_ip

def create_host_service(host: str, router: str, host_net: str, host_ip: str) -> Dict:
    """
    Create a host service configuration.
    
    Args:
        host (str): Host name
        router (str): Router name
        host_net (str): Host network name
        host_ip (str): Host IP address
        
    Returns:
        dict: Host service configuration
    """
    return {
        "build": {"context": ".", "dockerfile": "host/Dockerfile"},
        "container_name": host.lower(),
        "networks": {host_net: {"ipv4_address": host_ip}},
        "environment": [
            f"CONNECTED_TO={router}",
            f"CONTAINER_NAME={host.lower()}"
        ],
        "cap_add": ["NET_ADMIN"],
        "volumes": ["./shared:/app"]
    }

def generate_docker_compose():
    """
    Main function to generate docker-compose.yml file.
    """
    # Read topology and extract information
    topology = read_topology("topologias/network_topology.json")
    routers, connections, subnets = extract_router_connections(topology)
    connections_per_router = create_connection_map(connections)
    
    # Initialize docker-compose structure
    docker_compose = {"services": {}, "networks": {}}
    
    # Create network structure
    networks, ip_map, subnet_cost, subnet_count = create_network_structure(connections, 1)
    
    # Create services for routers and hosts
    for router in sorted(routers):
        # Create router service
        service, host_net, host_subnet, gateway_ip = create_router_service(
            router, ip_map, subnet_cost, subnet_count
        )
        docker_compose["services"][router.lower()] = service
        networks[host_net] = host_subnet
        
        # Find and create host services
        router_hosts = next(
            (subnet["hosts"] for subnet in subnets if subnet["router"] == router),
            []
        )
        
        for idx, host in enumerate(router_hosts):
            host_ip = f"192.168.{subnet_count}.{idx + 3}"
            docker_compose["services"][host.lower()] = create_host_service(
                host, router, host_net, host_ip
            )
        
        subnet_count += 1
    
    # Add networks to docker-compose
    docker_compose["networks"] = {
        net: {
            "driver": "bridge",
            "ipam": {"config": [{"subnet": subnet}]}
        }
        for net, subnet in networks.items()
    }
    
    # Save to file
    with open("docker-compose.yml", "w") as f:
        yaml.dump(docker_compose, f, default_flow_style=False, sort_keys=False)
    
    print("docker-compose.yml file has been generated with updated network logic.")

if __name__ == "__main__":
    generate_docker_compose()