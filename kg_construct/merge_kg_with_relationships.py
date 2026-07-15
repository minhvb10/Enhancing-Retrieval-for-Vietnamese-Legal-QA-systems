import json
import networkx as nx
from pathlib import Path

def load_json_graph(json_file):
    print(f"Đang đọc graph từ {json_file}...")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        graph_data = json.load(f)
    
    G = nx.DiGraph()
    
    for node in graph_data['nodes']:
        node_id = node.pop('id')
        G.add_node(node_id, **node)
    
    for edge in graph_data['edges']:
        source = edge.pop('source')
        target = edge.pop('target')
        G.add_edge(source, target, **edge)
    
    print(f"Đã tải graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G

def load_relationships(relationships_file):
    print(f"Đang đọc relationships từ {relationships_file}...")
    
    with open(relationships_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Đã tải {data['total_relationships']} relationships")
    return data['relationships']

def merge_relationships_into_graph(G, relationships):
    print("\nĐang thêm relationships vào graph...")
    
    added_edges = 0
    
    for rel in relationships:
        source_law = rel['source']
        target_law = rel['target']
        rel_type = rel['type']
        
        if G.has_node(source_law) and G.has_node(target_law):
            
            G.add_edge(
                source_law,
                target_law,
                edge_type=rel_type,
                label=rel_type,
                relationship_type=rel_type
            )
            added_edges += 1
    
    print(f"Đã thêm {added_edges} relationship edges")
    return G

def save_combined_graph(G, output_json):
    print("\nĐang lưu combined graph...")
    
    try:
        graph_data = {
            'total_nodes': G.number_of_nodes(),
            'total_edges': G.number_of_edges(),
            'nodes': [
                {
                    'id': node,
                    **G.nodes[node]
                }
                for node in G.nodes()
            ],
            'edges': [
                {
                    'source': source,
                    'target': target,
                    **G.edges[source, target]
                }
                for source, target in G.edges()
            ]
        }
        
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        print(f"Đã lưu JSON: {output_json}")
    except Exception as e:
        print(f"Lỗi lưu JSON: {e}")

def print_graph_stats(G):
    print("\n" + "="*80)
    print("THỐNG KÊ KNOWLEDGE GRAPH HOÀN CHỈNH")
    print("="*80)
    print(f"Tổng nodes: {G.number_of_nodes()}")
    print(f"Tổng edges: {G.number_of_edges()}")
    
    node_types = {}
    for node, attr in G.nodes(data=True):
        node_type = attr.get('node_type', 'UNKNOWN')
        node_types[node_type] = node_types.get(node_type, 0) + 1
    
    print("\nThống kê theo loại node:")
    for node_type, count in sorted(node_types.items()):
        print(f"  - {node_type}: {count}")
    
    edge_types = {}
    for source, target, attr in G.edges(data=True):
        edge_type = attr.get('edge_type', 'UNKNOWN')
        edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
    
    print("\nThống kê theo loại edge:")
    for edge_type, count in sorted(edge_types.items()):
        print(f"  - {edge_type}: {count}")
    
    law_nodes = [node for node, attr in G.nodes(data=True) if attr.get('node_type') == 'LAW']
    print(f"\nTổng số LAW nodes: {len(law_nodes)}")
    
    relationship_edges = [edge for edge in G.edges(data=True) 
                         if edge[2].get('edge_type') in ['AMENDS', 'REPLACES', 'DETAILS', 'REFERENCES', 'IMPLEMENTS', 'SUPERSEDES']]
    print(f"Tổng số relationship edges giữa các LAW: {len(relationship_edges)}")
    
    print("="*80 + "\n")

if __name__ == "__main__":
    base_path = Path(__file__).parent
    
    kg_json_file = base_path / "legal_kg.json"
    relationships_json_file = base_path / "relationships.json"
    
    output_json = base_path / "legal_kg_complete.json"
    
    try:
        G = load_json_graph(str(kg_json_file))
        
        relationships = load_relationships(str(relationships_json_file))
        
        G = merge_relationships_into_graph(G, relationships)
        
        print_graph_stats(G)
        
        save_combined_graph(G, str(output_json))
        
        print("\nHoàn tất tạo Knowledge Graph hoàn chỉnh!")
        
    except Exception as e:
        print(f"\nLỗi: {e}")
        import traceback
        traceback.print_exc()
