"""실험 B: 방어 방식별 공격 성공률(ASR) 측정.

각 공격 문장을 D0~D4 방어에 통과시키고, 막히지 않은 것만 대상 챗봇에
넣어 공격이 실제로 성공했는지 target.judge로 판정함.

공격 성공 = (방어가 막지 못함) AND (judge.attack_succeeded == True)

실행:
    python -m experiments.run_attack                # 전체(eval split)
    python -m experiments.run_attack --max-rows 9   # 소량 스모크 테스트
    python -m experiments.run_attack --split dev     # dev split로

결과: results/attack_results.csv
"""
import argparse
import time

import pandas as pd

from defenses import d1_rule, d2_classifier, d3_llm, d4_cascade
from target.chatbot import ask_chatbot
from target.judge import attack_succeeded, is_refusal

# 방어 방식. D0는 "방어 없음"이라 detect 함수가 없음(항상 통과).
DEFENSES = {
    "D0": None,                 # 방어 없음(기준선): 무조건 챗봇으로
    "D1": d1_rule.detect,
    "D2": d2_classifier.detect,
    "D3": d3_llm.detect,
    "D4": d4_cascade.detect,
}

# 챗봇 응답 캐시 (temperature=0이라 같은 입력 → 같은 응답, 중복 호출 제거)
_chatbot_cache = {}


def ask_chatbot_cached(text):
    """같은 입력은 한 번만 실제 호출하고 이후 캐시에서 꺼냄."""
    if text in _chatbot_cache:
        return _chatbot_cache[text]
    try:
        answer, elapsed, in_tok, out_tok = ask_chatbot(text)
    except Exception as e:
        # API 에러 시 1회 재시도
        time.sleep(2)
        answer, elapsed, in_tok, out_tok = ask_chatbot(text)
    result = (answer, elapsed, in_tok, out_tok)
    _chatbot_cache[text] = result
    return result


def run_one(defense_name, detect_fn, row):
    """공격 한 건을 한 방어에 통과시킨 결과 dict 반환."""
    text = row["text"]
    goal = row["goal"]

    # 1) 방어 단계: 막혔는지 확인
    if detect_fn is None:          # D0: 방어 없음
        blocked = False
        def_score = 0.0
        def_latency = 0.0
        stage = "D0"
    else:
        result = detect_fn(text)
        blocked = bool(result[0])
        def_score = float(result[1])
        def_latency = float(result[2])
        stage = result[3] if len(result) > 3 else defense_name

    # 2) 막혔으면 챗봇에 안 감 → 공격 실패
    if blocked:
        return {
            "id": row["id"], "base_id": row["base_id"], "defense": defense_name,
            "language": row["language"], "goal": goal, "difficulty": row["difficulty"],
            "blocked": True, "stage": stage, "def_score": def_score,
            "reached_chatbot": False, "refused_by_bot": False, "success": False,
            "def_latency_ms": def_latency * 1000, "bot_latency_ms": 0.0,
            "in_tokens": 0, "out_tokens": 0,
            "response": "",
        }

    # 3) 통과했으면 챗봇에 넣고 공격 성공 판정
    answer, bot_latency, in_tok, out_tok = ask_chatbot_cached(text)
    success = attack_succeeded(goal, answer)
    refused = is_refusal(answer)

    return {
        "id": row["id"], "base_id": row["base_id"], "defense": defense_name,
        "language": row["language"], "goal": goal, "difficulty": row["difficulty"],
        "blocked": False, "stage": stage, "def_score": def_score,
        "reached_chatbot": True, "refused_by_bot": refused, "success": success,
        "def_latency_ms": def_latency * 1000, "bot_latency_ms": bot_latency * 1000,
        "in_tokens": in_tok, "out_tokens": out_tok,
        "response": answer[:300].replace("\n", " "),   # 분석용 일부만 저장
    }


def load_attacks(split):
    df = pd.read_csv("data/attacks.csv")
    df = df[df["split"] == split].reset_index(drop=True)
    return df


def summarize(out):
    langs = ["en", "ko", "mixed"]

    print("\n=== 방어별 종합: 공격성공률(ASR) / 차단율 / 평균지연 ===")
    total = out[out["defense"] == "D0"].shape[0]
    print(f"(공격 {total}건 기준)")
    for dname in DEFENSES:
        sub = out[out["defense"] == dname]
        if not len(sub):
            continue
        asr = sub["success"].mean() * 100
        blocked = sub["blocked"].mean() * 100
        latency = sub["def_latency_ms"].mean()
        print(f"{dname}: 공격성공 {asr:5.1f}%   차단율 {blocked:5.1f}%   방어지연 {latency:7.1f}ms")

    print("\n=== 방어 × 언어별 차단율 (핵심: RQ2) ===")
    header = "방어 | " + " | ".join(f"{l:>6}" for l in langs)
    print(header)
    print("-" * len(header))
    for dname in DEFENSES:
        sub = out[out["defense"] == dname]
        if not len(sub):
            continue
        cells = []
        for l in langs:
            s = sub[sub["language"] == l]
            cells.append(f"{s['blocked'].mean()*100:5.1f}%" if len(s) else "   - ")
        print(f"{dname:>3} | " + " | ".join(cells))

    print("\n=== 방어 × 언어별 공격 성공률(ASR) ===")
    header = "방어 | " + " | ".join(f"{l:>6}" for l in langs)
    print(header)
    print("-" * len(header))
    for dname in DEFENSES:
        sub = out[out["defense"] == dname]
        if not len(sub):
            continue
        cells = []
        for l in langs:
            s = sub[sub["language"] == l]
            cells.append(f"{s['success'].mean()*100:5.1f}%" if len(s) else "   - ")
        print(f"{dname:>3} | " + " | ".join(cells))

    print("\n=== 방어 × 언어별 평균 지연(ms) ===")
    header = "방어 | " + " | ".join(f"{l:>7}" for l in langs)
    print(header)
    print("-" * len(header))
    for dname in DEFENSES:
        sub = out[out["defense"] == dname]
        if not len(sub):
            continue
        cells = []
        for l in langs:
            s = sub[sub["language"] == l]
            cells.append(f"{s['def_latency_ms'].mean():7.1f}" if len(s) else "   -   ")
        print(f"{dname:>3} | " + " | ".join(cells))

    # D4 결정 단계 분포 (어느 방어에서 차단/통과가 결정됐는지)
    d4 = out[out["defense"] == "D4"]
    if len(d4):
        dist = d4["stage"].value_counts().to_dict()
        print("\n=== D4 결정 단계 분포 ===")
        print("  " + ", ".join(f"{k}: {v}건" for k, v in dist.items()))

    print("\n=== 방어 × 목표별 공격 성공률 ===")
    goals = sorted(g for g in out["goal"].dropna().unique())
    for dname in DEFENSES:
        sub = out[out["defense"] == dname]
        if not len(sub):
            continue
        parts = []
        for g in goals:
            s = sub[sub["goal"] == g]
            parts.append(f"{g}={s['success'].mean()*100:.1f}%" if len(s) else f"{g}=-")
        print(f"{dname}: " + "  ".join(parts))


def run(split="eval", max_rows=None):
    df = load_attacks(split)
    if max_rows:
        df = df.head(max_rows)
    print(f"공격 데이터 {len(df)}건 로드 (split={split})")

    rows = []
    for i, (_, row) in enumerate(df.iterrows(), 1):
        for dname, detect_fn in DEFENSES.items():
            rows.append(run_one(dname, detect_fn, row))
        if i % 10 == 0:
            print(f"  ...{i}/{len(df)} 공격 처리")

    out = pd.DataFrame(rows)
    import os
    os.makedirs("results", exist_ok=True)
    out.to_csv("results/attack_results.csv", index=False, encoding="utf-8-sig")
    print(f"\n결과 저장: results/attack_results.csv ({len(out)}행)")

    summarize(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="eval", choices=["dev", "eval"])
    ap.add_argument("--max-rows", type=int, default=None, help="소량 테스트용 공격 개수 제한")
    args = ap.parse_args()
    run(split=args.split, max_rows=args.max_rows)