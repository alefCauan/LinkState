import networkx as nx
import matplotlib.pyplot as plt
import random
import json

# Step 1: Create the graph
G = nx.Graph()

# Step 2: Define the number of subnets (using 3 subnets as an example)
num_subnets = 3
subnets = []

# Step 3: Create subnets (each with 2 hosts and 1 router)
for i in range(num_subnets):
    subnet = {}
    router = f"R{i+1}"  # Router 1, Router 2, etc.
    host1 = f"H{i*2+1}"  # Host 1, Host 3, Host 5, etc.
    host2 = f"H{i*2+2}"  # Host 2, Host 4, Host 6, etc.
    
    # Add nodes
    G.add_node(router, type="router")
    G.add_node(host1, type="host")
    G.add_node(host2, type="host")
    
    # Add edges within the subnet (hosts to router, sem peso)
    G.add_edge(host1, router)
    G.add_edge(host2, router)
    
    # Store subnet info
    subnet["router"] = router
    subnet["hosts"] = [host1, host2]
    subnets.append(subnet)

# Step 4: Connect routers in a fully connected topology
routers = [subnet["router"] for subnet in subnets]

# Ensure connectivity by creating a chain (R1 -> R2 -> R3 -> ...)
for i in range(len(routers) - 1):
    G.add_edge(routers[i], routers[i + 1], weight=random.randint(1, 10))

# Add additional random edges between routers
for i in range(len(routers)):
    for j in range(i + 2, len(routers)):
        if random.random() > 0.5:
            G.add_edge(routers[i], routers[j], weight=random.randint(1, 10))

# Step 5: Verify the graph is connected
if not nx.is_connected(G):
    print("Warning: Graph is not connected! Adjusting...")
    for i in range(len(routers) - 1):
        G.add_edge(routers[i], routers[i + 1], weight=random.randint(1, 10))

# Step 6: Visualize the graph
pos = nx.spring_layout(G)
node_colors = []
for node in G.nodes(data=True):
    if node[1]["type"] == "router":
        node_colors.append("lightblue")
    else:
        node_colors.append("lightgreen")

plt.figure(figsize=(10, 8))
nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=500)
nx.draw_networkx_edges(G, pos)
# Exibir apenas labels de peso nas arestas entre routers
edge_labels = {(u, v): d["weight"] for u, v, d in G.edges(data=True) if "weight" in d}
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)
nx.draw_networkx_labels(G, pos)
plt.title("Connected Network Graph with Subnets, Hosts, and Routers (Edge Weights Shown)")
plt.show()

# Step 7: Print and save the network structure
print("Network Structure:")
for i, subnet in enumerate(subnets):
    print(f"Subnet {i+1}: {subnet['hosts']} connected to {subnet['router']}")

print("\nEdges and Weights:")
topology = {
    "subnets": [],
    "edges": []
}

# Save subnet info
for i, subnet in enumerate(subnets):
    topology["subnets"].append({
        "subnet_id": i + 1,
        "router": subnet["router"],
        "hosts": subnet["hosts"]
    })

# Save edges and weights
for edge in G.edges(data=True):
    if "weight" in edge[2]:
        print(f"{edge[0]} <-> {edge[1]} : Weight = {edge[2]['weight']}")
        topology["edges"].append({
            "node1": edge[0],
            "node2": edge[1],
            "weight": edge[2]["weight"]
        })
    else:
        print(f"{edge[0]} <-> {edge[1]}")
        topology["edges"].append({
            "node1": edge[0],
            "node2": edge[1]
            # sem campo weight
        })

# Step 8: Save the topology to a JSON file
with open("network_topology.json", "w") as f:
    json.dump(topology, f, indent=4)

with open("router/network_topology.json", "w") as f:
    json.dump(topology, f, indent=4)

print("\nNetwork topology has been saved to 'network_topology.json'.")