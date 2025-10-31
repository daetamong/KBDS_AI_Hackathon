import json, os

# 저장된 data 디렉토리 경로
DATA_DIR = "data"
user_id = "d06b5981-2262-4f39-9157-1308e57740a7"  # 혹은 파일 이름에 맞게 수정
file_path = os.path.join(DATA_DIR, f"user_state_{user_id}.json")

if not os.path.exists(file_path):
    print(f"⚠️ 파일이 존재하지 않습니다: {file_path}")
else:
    with open(file_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    print("🧩 UI 설정:")
    print(json.dumps(state.get("ui_settings", {}), ensure_ascii=False, indent=2))

    print("\n🍱 주간 식사 기록:")
    print(json.dumps(state.get("weekly_meals", {}), ensure_ascii=False, indent=2))