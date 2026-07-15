import json
import re
from collections import Counter
ABBREV_PATTERN = re.compile(r"\b[A-ZÀ-ỸĐ]{2,10}\b")

input_file = "queries.jsonl"

counter = Counter()

with open(input_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()

        if not line:
            continue

        try:
            data = json.loads(line)
            text = data.get("text", "")

            matches = ABBREV_PATTERN.findall(text)

            for m in matches:
                counter[m] += 1

        except json.JSONDecodeError:
            print("Lỗi parse JSON:", line[:100])

print("Các từ viết tắt tìm được:\n")

for word, freq in counter.most_common():
    print(f"{word}: {freq}")