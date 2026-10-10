import pandas as pd

for fname, expected_label in [("data/attacks.csv", "attack"),
                               ("data/normals.csv", "normal")]:
    print(f"\n=== {fname} ===")
    df = pd.read_csv(fname)

    # 컬럼 확인
    cols = ["id", "base_id", "label", "language", "goal",
            "difficulty", "is_boundary", "source", "split", "text"]
    if list(df.columns) != cols:
        print("  [경고] 컬럼이 다름:", list(df.columns))
    else:
        print("  컬럼 OK")

    if len(df) == 0:
        print("  (아직 데이터 없음)")
        continue

    print(f"  총 {len(df)}건")
    # 표기 검사
    bad_label = df[~df["label"].isin([expected_label])]
    bad_lang = df[~df["language"].isin(["en", "ko", "mixed"])]
    if len(bad_label): print(f"  [경고] label 이상 {len(bad_label)}건")
    if len(bad_lang): print(f"  [경고] language 이상 {len(bad_lang)}건")

    # 언어별 개수
    print("  언어별:", df["language"].value_counts().to_dict())