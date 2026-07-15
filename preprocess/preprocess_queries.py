import json
import re
from pathlib import Path

ABBREVIATIONS = {
    r'\bhđnd\b': 'hội đồng nhân dân',
    r'\bhđlđ\b': 'hợp đồng lao động',
    r'\bnlđ\b': 'người lao động',
    r'\btnhh\b': 'trách nhiệm hữu hạn',
    r'\bubnd\b': 'ủy ban nhân dân',
    r'\bbhyt\b': 'bảo hiểm y tế',
    r'\bdn\b': 'doanh nghiệp',
    r'\bkcb\b': 'khám chữa bệnh',
    r'\bhcm\b': 'hồ chí minh',
    r'\bbhxh\b': 'bảo hiểm xã hội',
    r'\bcmnd\b': 'chứng minh nhân dân',
    r'\bnhnn\b': 'ngân hàng nhà nước',
    r'\bcntt\b': 'công nghệ thông tin',
    r'\bcccd\b': 'căn cước công dân',
    r'\bvphc\b': 'vi phạm hành chính',
    r'\bgcn\b': 'giấy chứng nhận',
    r'\bthpt\b': 'trung học phổ thông',
    r'\bcchn\b': 'chứng chỉ hành nghề',
    r'\bcsgt\b': 'cảnh sát giao thông',
    r'\bgplx\b': 'giấy phép lái xe',
    r'\bsgk\b': 'sách giáo khoa',
    r'\bnsnn\b': 'ngân sách nhà nước',
    r'\bbvmt\b': 'bảo vệ môi trường',
    r'\bbhtn\b': 'bảo hiểm thất nghiệp',
    r'\btthc\b': 'thủ tục hành chính',
    r'\bkbnn\b': 'kho bạc nhà nước',
    r'\boda\b': 'hỗ trợ phát triển chính thức',
    r'\bgdqpan\b': 'giáo dục quốc phòng an ninh',
    r'\bthcs\b': 'trung học cơ sở',
    r'\bgdnn\b': 'giáo dục nghề nghiệp',
    r'\btcvn\b': 'tiêu chuẩn việt nam',
    r'\bkcn\b': 'khu công nghiệp',
    r'\bbtp\b': 'bộ tư pháp',
    r'\btp\b': 'thành phố',
    r'\bhtx\b': 'hợp tác xã',
    r'\btandtc\b': 'tòa án nhân dân tối cao',
    r'\bvlxd\b': 'vật liệu xây dựng',
    r'\bcqnn\b': 'cơ quan nhà nước',
    r'\batgt\b': 'an toàn giao thông',
    r'\bthahs\b': 'thi hành án hình sự',
    r'\bdntn\b': 'doanh nghiệp tư nhân',
    r'\bđtm\b': 'đánh giá tác động môi trường',
    r'\battp\b': 'an toàn thực phẩm',
    r'\bbqp\b': 'bộ quốc phòng',
    r'\bpccc\b': 'phòng cháy chữa cháy',
    r'\bgtgt\b': 'giá trị gia tăng',
    r'\bđmc\b': 'đánh giá môi trường chiến lược',
    r'\bbgdđt\b': 'bộ giáo dục và đào tạo',
    r'\bctcp\b': 'công ty cổ phần',
    r'\bnsdlđ\b': 'người sử dụng lao động',
    r'\blđtb&xh\b': 'lao động thương binh và xã hội',
    r'\btb&xh\b': 'thương binh và xã hội',
    r'\bblđtbxh\b': 'bộ lao động thương binh và xã hội',
    r'\btn&mt\b': 'tài nguyên và môi trường',
    r'\bhgđ\b': 'hộ gia đình',
    r'\bqckt\b': 'quy chuẩn kỹ thuật',
    r'\bbch\b': 'ban chỉ huy',
    r'\bkh&đt\b': 'kế hoạch và đầu tư',
    r'\bsđt\b': 'số điện thoại',
    r'\bccthads\b': 'chi cục thi hành án dân sự',
    r'\bmsld\b': 'mất sức lao động',
    r'\bkbc\b': 'khám bệnh, chữa bệnh'
}

def expand_abbreviations(text):
    for abbr, full_form in ABBREVIATIONS.items():
        text = re.sub(abbr, full_form, text, flags=re.IGNORECASE)
    return text

def preprocess_text(text):
    text = text.lower()
    text = expand_abbreviations(text)
    return text

def preprocess_queries(input_file, output_file):
    processed_count = 0
    try:
        with open(input_file, 'r', encoding='utf-8') as f_in, \
             open(output_file, 'w', encoding='utf-8') as f_out:
            
            for line_num, line in enumerate(f_in, 1):
                try:
                    query = json.loads(line.strip())
                    if 'text' in query and query['text']:
                        query['text'] = preprocess_text(query['text'])
                    
                    f_out.write(json.dumps(query, ensure_ascii=False) + '\n')
                    processed_count += 1
                    
                except json.JSONDecodeError as e:
                    print(f"  Lỗi JSON tại dòng {line_num}: {e}")
                    continue
        
        print(f"Hoàn tất! Đã xử lý {processed_count} queries")
        print(f"  - Output: {output_file}")
        
    except FileNotFoundError:
        print(f"Không tìm thấy file: {input_file}")
    except Exception as e:
        print(f"Lỗi khi xử lý: {e}")

if __name__ == "__main__":
    input_path = Path(__file__).parent / "queries.jsonl"
    output_path = Path(__file__).parent / "queries_preprocessed_v2.jsonl"
    preprocess_queries(str(input_path), str(output_path))
