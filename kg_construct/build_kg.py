import json
import re
import networkx as nx
from pathlib import Path
from collections import defaultdict

def extract_law_id(section_id):
    match = re.match(r'^(.+?)\+\d+$', section_id)
    if match:
        return match.group(1)
    return section_id

def extract_section_number(section_id):
    match = re.search(r'\+(\d+)$', section_id)
    if match:
        return int(match.group(1))
    return 0

def split_into_paragraphs(text):
    if not text:
        return []
    
    paragraph_pattern = r'^[\s]*([\d]+[\.\)]\s*|[a-z][\)\.\s]|[ivxlcdm]+[\)\.\s])'
    
    paragraphs = []
    current_paragraph = None
    current_label = None
    
    lines = text.split('\n')
    
    for line in lines:
        match = re.match(paragraph_pattern, line, re.IGNORECASE)
        
        if match and line.strip():
            if current_paragraph is not None:
                paragraphs.append((current_label, current_paragraph.strip()))
            
            current_label = match.group(1).strip()
            current_paragraph = re.sub(paragraph_pattern, '', line, count=1, flags=re.IGNORECASE).strip()
        else:
            if current_paragraph is not None:
                current_paragraph += '\n' + line
            else:
                if not paragraphs:
                    current_paragraph = line
                    current_label = "1."
    
    if current_paragraph is not None:
        paragraphs.append((current_label, current_paragraph.strip()))
    
    if not paragraphs:
        return [("1.", text)]
    
    return paragraphs

def build_knowledge_graph(corpus_file):
    G = nx.DiGraph()
    law_sections = defaultdict(list)
    
    print(f"Đang đọc file {corpus_file}...")
    
    try:
        with open(corpus_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    sample = json.loads(line.strip())
                    
                    section_id = sample.get('_id', '')
                    title = sample.get('title', '')
                    text = sample.get('text', '')
                    
                    if not section_id:
                        continue
                    
                    law_id = extract_law_id(section_id)
                    section_num = extract_section_number(section_id)
                    
                    law_sections[law_id].append({
                        'section_id': section_id,
                        'section_num': section_num,
                        'title': title,
                        'text': text
                    })
                    
                except json.JSONDecodeError as e:
                    print(f"  Lỗi JSON tại dòng {line_num}: {e}")
                    continue
        
        print(f"Đã đọc {len(law_sections)} văn bản pháp luật")
        print("Building KG")
        
        node_count = 0
        edge_count = 0
        
        for law_id, sections in law_sections.items():
            G.add_node(law_id, node_type='LAW', label=law_id)
            node_count += 1
            
            sections.sort(key=lambda x: x['section_num'])
            
            for section in sections:
                section_id = section['section_id']
                title = section['title']
                text = section['text']
                
                G.add_node(
                    section_id,
                    node_type='SECTION',
                    label=f"Điều {section['section_num']}",
                    title=title,
                    text=text[:200] + '...' if len(text) > 200 else text
                )
                node_count += 1
                
                G.add_edge(
                    law_id,
                    section_id,
                    edge_type='HAS_SECTION',
                    label='HAS_SECTION'
                )
                edge_count += 1
                
                paragraphs = split_into_paragraphs(text)
                
                for para_idx, (para_label, para_content) in enumerate(paragraphs):
                    paragraph_id = f"{section_id}_para_{para_idx}"
                    G.add_node(
                        paragraph_id,
                        node_type='PARAGRAPH',
                        label=para_label,
                        content=para_content,
                        section_title=title
                    )
                    node_count += 1
                    
                    G.add_edge(
                        section_id,
                        paragraph_id,
                        edge_type='HAS_PARAGRAPH',
                        label='HAS_PARAGRAPH'
                    )
                    edge_count += 1
        
        print(f"Hoàn tất xây dựng graph")
        print(f"  - Tổng nodes: {node_count}")
        print(f"  - Tổng edges: {edge_count}")
        
        return G
        
    except FileNotFoundError:
        print(f"Không tìm thấy file: {corpus_file}")
        return None
    except Exception as e:
        print(f"Lỗi khi xây dựng: {e}")
        return None

def save_json_graph(G, output_file):
    try:
        graph_data = {
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
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        print(f"Đã lưu graph JSON vào: {output_file}")
    except Exception as e:
        print(f"Lỗi khi lưu JSON: {e}")

def print_graph_stats(G):
    print("\n" + "="*50)
    print("THỐNG KÊ KNOWLEDGE GRAPH")
    print("="*50)
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
    print("="*50 + "\n")

if __name__ == "__main__":
    input_file = Path(__file__).parent / "corpus_preprocessed_v2.jsonl"
    
    output_json = Path(__file__).parent / "legal_kg.json"
    
    G = build_knowledge_graph(str(input_file))
    
    if G is not None:
        print_graph_stats(G)
        
        save_json_graph(G, str(output_json))
