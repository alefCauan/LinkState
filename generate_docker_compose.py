import json
import yaml
from collections import defaultdict

# Step 1: Read the network topology from the JSON file
with open("topologias/network_topology.json", "r") as f:
    topology = json.load(f)

subnets = topology["subnets"]
edges = topology["edges"]

# Step 2: Extract router connections (similar to CSV parsing in the example)
routers = set()
connections = []
for subnet in subnets:
    router = subnet["router"]
    routers.add(router)
for edge in edges:
    if edge["node1"].startswith("R") and edge["node2"].startswith("R"):
        connections.append((edge["node1"], edge["node2"], edge["weight"]))
        routers.update([edge["node1"], edge["node2"]])

# Create a graph of connections (who is connected to whom)
connections_per_router = defaultdict(list)
for origin, dest, weight in connections:
    connections_per_router[origin].append(dest)
    connections_per_router[dest].append(origin)

# Step 3: Prepare subnet and IP models
subnet_base = "10.10.{0}.0/24"  # For inter-router networks
host_subnet_base = "192.168.{0}.0/24"  # For host subnets
ip_base = "10.10.{0}.{1}"  # For inter-router IPs
host_ip_base = "192.168.{0}.{1}"  # For host IPs
networks = {}
ip_map = defaultdict(dict)
subnet_cost = {}
subnet_count = 1

# Step 4: Create the docker-compose structure
docker_compose = {
    "services": {},
    "networks": {}
}

# Step 5: Create inter-router networks and assign IPs
for origin, dest, weight in connections:
    net_name = f"{origin.lower()}_{dest.lower()}_net"
    subnet = subnet_base.format(subnet_count)
    ip_map[origin][net_name] = ip_base.format(subnet_count, 2)
    ip_map[dest][net_name] = ip_base.format(subnet_count, 3)
    networks[net_name] = subnet
    subnet_cost[net_name] = weight
    subnet_count += 1

# Step 6: Create services for routers and their hosts
for router in sorted(routers):
    # Router service
    service = {
        "build": {
            "context": ".",
            "dockerfile": "router/Dockerfile"
        },
        "container_name": router.lower(),
        "environment": {
            "CONTAINER_NAME": router.lower(),
        },
        "volumes": ["./shared:/app"],
        "networks": {},
        "cap_add": ["NET_ADMIN"]
    }

    # Add inter-router networks and their costs
    for net, ip in ip_map[router].items():
        service["networks"][net] = {"ipv4_address": ip}
        service["environment"][f"CUSTO_{net}"] = str(subnet_cost[net])

    # Create the host subnet for this router
    host_net = f"{router.lower()}_hosts_net"
    host_subnet = host_subnet_base.format(subnet_count)
    networks[host_net] = host_subnet
    gateway_ip = host_ip_base.format(subnet_count, 2)  # Router as gateway (.2)
    service["networks"][host_net] = {"ipv4_address": gateway_ip}

    docker_compose["services"][router.lower()] = service

    # Find hosts for this router from the subnets
    router_hosts = []
    for subnet in subnets:
        if subnet["router"] == router:
            router_hosts = subnet["hosts"]
            break

    # Create hosts for this router (similar to the example's 2 hosts per router)
    for idx, host in enumerate(router_hosts):
        host_name = host.lower()
        host_ip = host_ip_base.format(subnet_count, idx + 3)  # Hosts get .3, .4
        docker_compose["services"][host_name] = {
            "build": {
                "context": ".",
                "dockerfile": "host/Dockerfile"
            },
            "container_name": host_name,
            "networks": {
                host_net: {"ipv4_address": host_ip}
            },
            "environment": [
                f"CONNECTED_TO={router}",
                f"CONTAINER_NAME={host_name}"
            ],
            "cap_add": ["NET_ADMIN"],
            "volumes": ["./shared:/app"]
        }

    subnet_count += 1

# Step 7: Create all networks in docker-compose
docker_compose["networks"] = {}
for net, subnet in networks.items():
    docker_compose["networks"][net] = {
        "driver": "bridge",
        "ipam": {
            "config": [{"subnet": subnet}]
        }
    }

# Step 8: Save the docker-compose.yml file
with open("topologias/docker-compose.yml", "w") as f:
    yaml.dump(docker_compose, f, default_flow_style=False, sort_keys=False)
with open("docker-compose.yml", "w") as f:
    yaml.dump(docker_compose, f, default_flow_style=False, sort_keys=False)

print("docker-compose.yml file has been generated with updated network logic.")