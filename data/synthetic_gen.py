"""
Dataset đã được tạo sẵn tại data/golden_dataset.json (50 cases, có answer_points).
Script này chỉ xác nhận file tồn tại.
"""
import os, json

def main():
    path = "data/golden_dataset.json"
    if not os.path.exists(path):
        print(f"❌ Thiếu {path}. Cần tạo bằng data/select_golden.py trước.")
        return
    with open(path) as f:
        data = json.load(f)
    print(f"✅ Dataset sẵn sàng: {len(data)} cases")
    has_points = sum(1 for r in data if r.get("answer_points"))
    print(f"   {has_points}/{len(data)} cases có answer_points")

if __name__ == "__main__":
    main()
