import networkx as nx
import matplotlib.pyplot as plt
import random
import json

def create_subnet(G, subnet_index):
    """
    Create a subnet with 2 hosts and 1 router.
    
    Args:
        G (nx.Graph): The network graph
        subnet_index (int): Index of the subnet
        
    Returns:
        dict: Subnet information containing router and hosts
    """
    subnet = {}
    router = f"R{subnet_index+1}"
    host1 = f"H{subnet_index*2+1}"
    host2 = f"H{subnet_index*2+2}"
    
    G.add_node(router, type="router")
    G.add_node(host1, type="host")
    G.add_node(host2, type="host")
    
    G.add_edge(host1, router)
    G.add_edge(host2, router)
    
    return {"router": router, "hosts": [host1, host2]}

def connect_routers(G, routers):
    """
    Connect routers in a topology with random weights.
    
    Args:
        G (nx.Graph): The network graph
        routers (list): List of router names
    """
    # Create initial chain connectivity
    for i in range(len(routers) - 1):
        G.add_edge(routers[i], routers[i + 1], weight=random.randint(1, 10))
    
    # Add additional random connections
    for i in range(len(routers)):
        for j in range(i + 2, len(routers)):
            if random.random() > 0.5:
                G.add_edge(routers[i], routers[j], weight=random.randint(1, 10))

def visualize_network(G, filename):
    """
    Visualize and save the network topology.
    
    Args:
        G (nx.Graph): The network graph
        filename (str): Path to save the image
    """
    pos = nx.spring_layout(G)
    node_colors = ['lightblue' if node[1]["type"] == "router" else 'lightgreen' 
                   for node in G.nodes(data=True)]
    
    plt.figure(figsize=(10, 8))
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=500)
    nx.draw_networkx_edges(G, pos)
    
    edge_labels = {(u, v): d["weight"] for u, v, d in G.edges(data=True) 
                  if "weight" in d}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)
    nx.draw_networkx_labels(G, pos)
    plt.title("Connected Network Graph with Subnets, Hosts, and Routers")
    plt.savefig(filename)
    plt.show()

def save_topology(G, subnets, filename):
    """
    Save network topology to JSON file.
    
    Args:
        G (nx.Graph): The network graph
        subnets (list): List of subnet information
        filename (str): Path to save the JSON file
    """
    topology = {
        "subnets": [
            {
                "subnet_id": i + 1,
                "router": subnet["router"],
                "hosts": subnet["hosts"]
            } for i, subnet in enumerate(subnets)
        ],
        "edges": [
            {
                "node1": edge[0],
                "node2": edge[1],
                "weight": edge[2].get("weight", None)
            } for edge in G.edges(data=True)
        ]
    }
    
    with open(filename, "w") as f:
        json.dump(topology, f, indent=4)

def main():
    """Main function to generate network topology."""
    G = nx.Graph()
    num_subnets = 5
    subnets = []
    
    # Create subnets
    for i in range(num_subnets):
        subnet = create_subnet(G, i)
        subnets.append(subnet)
    
    # Connect routers
    routers = [subnet["router"] for subnet in subnets]
    connect_routers(G, routers)
    
    # Ensure connectivity
    if not nx.is_connected(G):
        print("Warning: Graph is not connected! Adjusting...")
        for i in range(len(routers) - 1):
            G.add_edge(routers[i], routers[i + 1], weight=random.randint(1, 10))
    
    # Visualize and save
    visualize_network(G, "topologias/network_topology.png")
    save_topology(G, subnets, "topologias/network_topology.json")
    
    print("Network topology has been generated and saved.")

if __name__ == "__main__":
    main()