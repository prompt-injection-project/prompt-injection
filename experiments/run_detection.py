import pandas as pd
import time

from defenses import d1_rule, d2_classifier, d3_llm, d4_cascade

# 테스트할 방어 방식들 (D0는 항상 통과라 탐지 성능 측정에서 제외)
DEFENSES = {
    "D1": d1_rule.detect,
    "D2": d2_classifier.detect,
    "D3": d3_llm.detect,
    "D4": d4_cascade.detect,
}


def load_data():
    """공격·정상 데이터를 합쳐서 불러옴"""
    attacks = pd.read_csv("data/attacks.csv")
    normals = pd.read_csv("data/normals.csv")
    df = pd.concat([attacks, normals], ignore_index=True)
    # 평가용만 사용
    df = df[df["split"] == "eval"].reset_index(drop=True)
    return df


def run():
    df = load_data()
    print(f"평가 데이터 {len(df)}건 로드")

    rows = []
    for _, row in df.iterrows():
        text = row["text"]
        true_label = row["label"]   # attack / normal

        for dname, detect_fn in DEFENSES.items():
            result = detect_fn(text)
            blocked = result[0]       # 차단 여부
            score = result[1]         # 점수
            elapsed = result[2]       # 시간

            rows.append({
                "id": row["id"],
                "defense": dname,
                "language": row["language"],
                "goal": row["goal"],
                "difficulty": row["difficulty"],
                "is_boundary": row["is_boundary"],
                "true_label": true_label,
                "blocked": blocked,
                "score": score,
                "latency_ms": elapsed * 1000,
            })

    out = pd.DataFrame(rows)
    out.to_csv("results/detection_results.csv", index=False, encoding="utf-8-sig")
    print(f"결과 저장: results/detection_results.csv ({len(out)}행)")

    # 간단 요약 출력
    print("\n=== 방어별 탐지율·오탐률 ===")
    for dname in DEFENSES:
        sub = out[out["defense"] == dname]
        # 공격을 막은 비율 (탐지율)
        atk = sub[sub["true_label"] == "attack"]
        detection = (atk["blocked"] == True).mean() if len(atk) else 0
        # 정상을 막은 비율 (오탐률)
        nor = sub[sub["true_label"] == "normal"]
        fpr = (nor["blocked"] == True).mean() if len(nor) else 0
        print(f"{dname}: 탐지율 {detection*100:.1f}%  오탐률 {fpr*100:.1f}%")


if __name__ == "__main__":
    run()