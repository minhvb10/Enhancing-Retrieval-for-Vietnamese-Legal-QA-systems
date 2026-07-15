import json
import re
from pathlib import Path
from collections import defaultdict

RELATIONSHIP_PATTERNS = {
    'AMENDS': [
        r'sửa\s+đổi\s+(?:và\s+)?bổ\s+sung',
        r'sửa\s+đổi.*?(?:Luật|Quyết\s+định|Thông\s+tư|Nghị\s+định)',
        r'bổ\s+sung',
    ],
    'REPLACES': [
        r'thay\s+thế',
        r'bãi\s+bỏ',
        r'hủy\s+bỏ',
        r'không\s+còn\s+hiệu\s+lực',
    ],
    'DETAILS': [
        r'quy\s+định\s+chi\s+tiết',
        r'hướng\s+dẫn\s+thi\s+hành',
        r'hướng\s+dẫn',
        r'chi\s+tiết',
    ],
    'REFERENCES': [
        r'theo\s+(?:quy\s+định\s+tại\s+)?(?:Luật|Quyết\s+định|Thông\s+tư|Nghị\s+định)',
        r'căn\s+cứ\s+(?:Luật|Quyết\s+định|Thông\s+tư|Nghị\s+định)',
        r'(?:Luật|Quyết\s+định|Thông\s+tư|Nghị\s+định)',
    ],
}


LAW_REFERENCE_PATTERN = r'(?:Luật|Quyết\s+định|Thông\s+tư|Nghị\s+định|NĐ|QĐ|TT)\s+(?:số\s+)?([0-9]+/[0-9]+/[^\s,;\.)\]]+)'

def extract_law_id(section_id):
    match = re.match(r'^(.+?)\+\d+$', section_id)
    if match:
        return match.group(1)
    return section_id

def find_relationship_type(text):
    for rel_type, patterns in RELATIONSHIP_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return (rel_type, match.group(0))
    return (None, None)

def extract_referenced_law_ids(text):
    referenced_ids = set()
    
    matches = re.finditer(LAW_REFERENCE_PATTERN, text, re.IGNORECASE)
    for match in matches:
        law_id = match.group(1).lower()
        referenced_ids.add(law_id)
    
    return list(referenced_ids)

def extract_context(text, matched_phrase, context_size=100):
    idx = text.lower().find(matched_phrase.lower())
    if idx == -1:
        return matched_phrase
    
    start = max(0, idx - context_size)
    end = min(len(text), idx + len(matched_phrase) + context_size)
    
    return text[start:end].strip()

def extract_relationships(corpus_file):
    relationships = defaultdict(list)
    
    print(f"Đang đọc file {corpus_file}...")
    print("="*80)
    
    try:
        with open(corpus_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    sample = json.loads(line.strip())
                    
                    section_id = sample.get('_id', '')
                    text = sample.get('text', '')
                    title = sample.get('title', '')
                    
                    if not section_id or not text:
                        continue
                    
                    law_id = extract_law_id(section_id)
                    
                    full_text = f"{title}\n{text}"
                    
                    rel_type, matched_phrase = find_relationship_type(full_text)
                    
                    if rel_type and matched_phrase:
                        referenced_laws = extract_referenced_law_ids(full_text)
                        
                        if referenced_laws:
                            context = extract_context(full_text, matched_phrase)
                            
                            for ref_law_id in referenced_laws:
                                relationship_key = (law_id, ref_law_id, rel_type)
                                relationships[relationship_key].append({
                                    'section_id': section_id,
                                    'relationship_type': rel_type,
                                    'matched_phrase': matched_phrase,
                                    'context': context,
                                    'full_text': text[:200] + '...' if len(text) > 200 else text
                                })
                
                except json.JSONDecodeError as e:
                    print(f"Lỗi JSON tại dòng {line_num}: {e}")
                    continue
        
        return relationships
        
    except FileNotFoundError:
        print(f"Không tìm thấy file: {corpus_file}")
        return None
    except Exception as e:
        print(f"Lỗi khi xử lý: {e}")
        return None

def print_relationships(relationships):
    if not relationships:
        print("Không tìm thấy relationship nào")
        return
    
    print(f"\n{'='*80}")
    print(f"TỔNG CỘNG: {len(relationships)} relationships tìm được")
    print(f"{'='*80}\n")
    
    by_type = defaultdict(list)
    for (source_law, target_law, rel_type), instances in relationships.items():
        by_type[rel_type].append((source_law, target_law, instances))
    
    for rel_type in sorted(by_type.keys()):
        items = by_type[rel_type]
        print(f"\n{'─'*80}")
        print(f"MỐI QUAN HỆ: {rel_type} ({len(items)} mối quan hệ)")
        print(f"{'─'*80}\n")
        
        for source_law, target_law, instances in sorted(items):
            print(f"{source_law}")
            print(f"   └─ [{rel_type}] ──> {target_law}")
            
            for instance in instances:
                print(f"\n Từ điều: {instance['section_id']}")
                print(f"  Cụm từ: \"{instance['matched_phrase']}\"")
                print(f"  Ngữ cảnh: ...{instance['context']}...")
                print()

def save_relationships_json(relationships, output_file):
    data = {
        'total_relationships': len(relationships),
        'relationships': []
    }
    
    for (source_law, target_law, rel_type), instances in relationships.items():
        data['relationships'].append({
            'source': source_law,
            'target': target_law,
            'type': rel_type,
            'instances': instances
        })
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nĐã lưu relationships vào: {output_file}")
    except Exception as e:
        print(f"Lỗi khi lưu: {e}")

if __name__ == "__main__":
    input_file = Path(__file__).parent / "corpus_preprocessed_v2.jsonl"
    
    output_json = Path(__file__).parent / "relationships.json"
    
    relationships = extract_relationships(str(input_file))
    
    if relationships:
        print_relationships(relationships)
        
        save_relationships_json(relationships, str(output_json))
