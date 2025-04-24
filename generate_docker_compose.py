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
for idx, (u, v, weight) in enumerate(router_edges):
    network_name = f"inter_router_{u.lower()}_{v.lower()}"
    inter_router_networks[(u, v)] = network_name
    inter_router_networks[(v, u)] = network_name  # Bidirectional
    docker_compose["networks"][network_name] = {
        "driver": "bridge",
        "ipam": {
            "config": [{"subnet": f"172.21.{idx+1}.0/24"}]
        }
    }

# Step 5: Add services for hosts and routers
for subnet in subnets:
    subnet_id = subnet["subnet_id"]
    subnet_name = f"subnet_{subnet_id}"
    router = subnet["router"]
    hosts = subnet["hosts"]

    # Add hosts as services
    for host in hosts:
        service_name = host.lower()
        # Find the weight to the router
        weight_to_router = next(edge["weight"] for edge in edges 
                               if (edge["node1"] == host and edge["node2"] == router) or 
                                  (edge["node1"] == router and edge["node2"] == host))
        docker_compose["services"][service_name] = {
            "build": {
                "context": "./host",
                "dockerfile": "Dockerfile"
            },
            "networks": [subnet_name],
            "environment": [f"CONNECTED_TO={router}", f"WEIGHT_TO_ROUTER={weight_to_router}"]
        }

    # Add router as a service
    service_name = router.lower()
    router_networks = [subnet_name]  # The subnet network
    # Add inter-router networks
    for u, v, weight in router_edges:
        if u == router or v == router:
            network_name = inter_router_networks[(u, v)]
            if network_name not in router_networks:
                router_networks.append(network_name)
    
    # Add environment variables for weights to neighboring routers
    env_vars = [f"CONNECTED_TO_SUBNET={subnet_name}"]
    for u, v, weight in router_edges:
        if u == router:
            env_vars.append(f"CONNECTED_TO_ROUTER_{v}={weight}")
        elif v == router:
            env_vars.append(f"CONNECTED_TO_ROUTER_{u}={weight}")
    
    docker_compose["services"][service_name] = {
        "build": {
            "context": "./router",
            "dockerfile": "Dockerfile"
        },
        "networks": router_networks,
        "environment": env_vars
    }

# Step 6: Save the docker-compose.yml file
with open("docker-compose.yml", "w") as f:
    yaml.dump(docker_compose, f, sort_keys=False)

print("docker-compose.yml file has been generated with build contexts (version field removed).")