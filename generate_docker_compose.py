import json
import yaml

# Step 1: Read the network topology from the JSON file
with open("network_topology.json", "r") as f:
    topology = json.load(f)

subnets = topology["subnets"]
edges = topology["edges"]

# Step 2: Create the docker-compose structure (remove the 'version' field)
docker_compose = {
    "services": {},
    "networks": {}
}

# Step 3: Define networks for each subnet
for subnet in subnets:
    subnet_id = subnet["subnet_id"]
    subnet_name = f"subnet_{subnet_id}"
    docker_compose["networks"][subnet_name] = {
        "driver": "bridge",
        "ipam": {
            "config": [{"subnet": f"172.20.{subnet_id}.0/24"}]
        }
    }

# Step 4: Define inter-router networks for router connections
router_edges = [(edge["node1"], edge["node2"], edge["weight"]) for edge in edges 
                if edge["node1"].startswith("R") and edge["node2"].startswith("R")]
inter_router_networks = {}

# Substitua o network_ranges fixo por uma função que gera ranges dinamicamente
def get_network_range(router_pair, base_network="172"):
    """Generate a unique network range for each router pair"""
    # Hash the router pair to get a unique number
    pair_str = f"{router_pair[0]}_{router_pair[1]}"
    pair_hash = hash(pair_str) & 0xFFFF  # Use apenas 16 bits do hash
    second_octet = 21 + (pair_hash % 74)  # Limita de 172.21.0.0 até 172.94.0.0
    return f"{base_network}.{second_octet}"

# E então use assim no código:
for idx, (u, v, weight) in enumerate(router_edges):
    network_name = f"inter_router_{u.lower()}_{v.lower()}"
    inter_router_networks[(u, v)] = network_name
    inter_router_networks[(v, u)] = network_name  # Bidirectional
    
    # Sort router names to get consistent network range
    routers = tuple(sorted([u, v]))
    base_ip = get_network_range(routers)
    
    docker_compose["networks"][network_name] = {
        "driver": "bridge",
        "ipam": {
            "config": [{"subnet": f"{base_ip}.0.0/24"}]
        }
    }

# Step 5: Add services for hosts and routers (modified version)
for subnet in subnets:
    subnet_id = subnet["subnet_id"]
    subnet_name = f"subnet_{subnet_id}"
    router = subnet["router"]
    hosts = subnet["hosts"]

    # Add hosts as services
    for host in hosts:
        service_name = host.lower()
        
        docker_compose["services"][service_name] = {
            "build": {
                "context": ".",
                "dockerfile": "host/Dockerfile"
            },
            "container_name": service_name,
            "networks": [subnet_name],
            "environment": [f"CONNECTED_TO={router}"]
        }

     # Add router as a service
    service_name = router.lower()
    router_networks = [subnet_name]  # The subnet network
    router_env = {}  # Use dictionary instead of list for environment variables
    
    # Add base subnet connection
    router_env["CONNECTED_TO_SUBNET"] = subnet_name
    
    # Add inter-router networks and their weights
    for u, v, weight in router_edges:
        if u == router:
            network_name = inter_router_networks[(u, v)]
            if network_name not in router_networks:
                router_networks.append(network_name)
            router_env[f"CONNECTED_TO_ROUTER_{v}"] = str(weight)
        elif v == router:
            network_name = inter_router_networks[(u, v)]
            if network_name not in router_networks:
                router_networks.append(network_name)
            router_env[f"CONNECTED_TO_ROUTER_{u}"] = str(weight)
    
    docker_compose["services"][service_name] = {
        "build": {
            "context": ".",
            "dockerfile": "router/Dockerfile"
        },
        "container_name": service_name,
        "networks": router_networks,
        "environment": router_env  # Use the dictionary directly
    }

# Step 6: Save the docker-compose.yml file
with open("docker-compose.yml", "w") as f:
    yaml.dump(docker_compose, f, default_flow_style=False, sort_keys=False)

print("docker-compose.yml file has been generated with updated build contexts.")