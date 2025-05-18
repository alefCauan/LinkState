import networkx as nx
import matplotlib.pyplot as plt
import random
import json

def create_subnet(G, subnet_index: int):
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

def connect_routers(G, routers: list):
    """
    Connect routers in a topology with random weights.
    
    Args:
        G (nx.Graph): The network graph
        routers (list): List of router names
    """
    # Create initial chain connectivity
    for i in range(len(routers) - 1):
        G.add_edge(routers[i], routers[i + 1], weight=random.randint(1, 10))
    
    # Add additional random connections with lower probability
    for i in range(len(routers)):
        for j in range(i + 2, len(routers)):
            if random.random() > 0.9:  
                G.add_edge(routers[i], routers[j], weight=random.randint(1, 10))

def custom_grid_layout(G, rows=None, cols=None):
    """
    Custom layout to position nodes in a rectangular grid.
    
    Args:
        G (nx.Graph): The network graph
        rows (int, optional): Number of rows (default: sqrt of number of nodes)
        cols (int, optional): Number of columns (default: sqrt of number of nodes)
    
    Returns:
        dict: Positions of nodes in a grid layout
    """
    nodes = list(G.nodes())
    n = len(nodes)
    
    if rows is None or cols is None:
        rows = int(n ** 0.5)
        cols = (n + rows - 1) // rows
    
    pos = {}
    for i, node in enumerate(nodes):
        row = i // cols
        col = i % cols
        pos[node] = (col , -row )  # Increased spacing with 1.5 multiplier
    
    return pos

def visualize_network(G, filename: str, layout_type="circular"):
    """
    Visualize and save the network topology with only routers, using a specified layout.
    
    Args:
        G (nx.Graph): The network graph
        filename (str): Path to save the image
        layout_type (str): Type of layout ("circular" for sphere)
    """
    # Create a subgraph with only router nodes
    router_nodes = [node for node, data in G.nodes(data=True) if data["type"] == "router"]
    router_subgraph = G.subgraph(router_nodes)
    
    # Choose layout based on layout_type
    if layout_type == "circular":
        pos = nx.circular_layout(router_subgraph, scale=2)
    elif layout_type == "grid":
        pos = custom_grid_layout(router_subgraph)
    else:
        pos = nx.spring_layout(router_subgraph)
    
    plt.figure(figsize=(10, 8))
    nx.draw_networkx_nodes(router_subgraph, pos, node_color='lightblue', node_size=500, label='Routers')
    nx.draw_networkx_edges(router_subgraph, pos)
    
    edge_labels = {(u, v): d["weight"] for u, v, d in router_subgraph.edges(data=True) 
                  if "weight" in d}
    nx.draw_networkx_edge_labels(router_subgraph, pos, edge_labels=edge_labels, label_pos=0.8)
    nx.draw_networkx_labels(router_subgraph, pos)
    
    plt.title(f"Network Topology - (Routers Only)")
    plt.legend()
    plt.axis('off')  # Remove axes for cleaner image
    plt.savefig(filename)
    plt.close()  # Close the figure to free memory

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
    for topologies in range(4):
        G = nx.Graph()
        num_subnets = [5, 10, 15, 20]
        subnets = []
        
        # Create subnets
        for i in range(num_subnets[topologies]):
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
        visualize_network(G, f"topologies/network_topology_{num_subnets[topologies]}.png", layout_type="grid")
        save_topology(G, subnets, f"topologies/network_topology_{num_subnets[topologies]}.json")
        
        G.clear()
        subnets.clear()
        print("Network topology has been generated and saved.")

if __name__ == "__main__":
    main()