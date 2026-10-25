"""실험 C: 방어 방식별 지연(latency)·비용(cost) 측정.

계획서 반영 사항
  - 워밍업 10건: 첫 호출(모델 로딩·커넥션)은 느리므로 측정에서 제외
  - D3/D4 API 비용 산정, reason 필드 제외 비용 별도 계산(결정 2)
  - 지연은 방어별/언어별 평균·중앙·p95

실행:
    python -m experiments.run_cost                 # 전체(eval split)
    python -m experiments.run_cost --max-rows 30   # 소량 테스트
    python -m experiments.run_cost --warmup 10

결과: results/cost_rows.csv (행별), 콘솔 요약
"""
import argparse
import statistics
import time

import pandas as pd

from defenses import d1_rule, d2_classifier, d3_llm, d4_cascade

# gpt-4o-mini-2024-07-18 단가 (USD per 1M tokens)
PRICE_IN = 0.15 / 1_000_000
PRICE_OUT = 0.60 / 1_000_000

# reason 토큰 수를 세기 위한 토크나이저 (없으면 글자 기반 근사)
try:
    import tiktoken
    _enc = tiktoken.get_encoding("o200k_base")   # gpt-4o 계열
    def ntok(s):
        return len(_enc.encode(s or ""))
except Exception:
    def ntok(s):
        return max(1, len(s or "") // 2)   # 근사치


def pct(values, p):
    """간단 백분위수 (오름차순 정렬 후 선형 보간)."""
    if not values:
        return 0.0
    xs = sorted(values)
    k = (len(xs) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def load_data(split, max_rows):
    atk = pd.read_csv("data/attacks.csv")
    nor = pd.read_csv("data/normals.csv")
    df = pd.concat([atk, nor], ignore_index=True)
    df = df[df["split"] == split].reset_index(drop=True)
    if max_rows:
        df = df.head(max_rows)
    return df


def warmup(df, n):
    """측정 전 n건으로 각 방어를 미리 호출해 첫 호출 지연 제거."""
    texts = df["text"].head(n).tolist()
    print(f"워밍업 {len(texts)}건...")
    for t in texts:
        try:
            d1_rule.detect(t)
            d2_classifier.detect(t)
            d3_llm.detect(t)
            d4_cascade.detect(t)
        except Exception:
            pass


def run(split="eval", max_rows=None, n_warmup=10):
    df = load_data(split, max_rows)
    print(f"측정 데이터 {len(df)}건 (split={split})")
    warmup(df, n_warmup)

    # 방어별 지연 리스트 / 언어별 지연
    lat = {d: [] for d in ["D1", "D2", "D3", "D4"]}
    lat_lang = {d: {"en": [], "ko": [], "mixed": []} for d in ["D1", "D2", "D3", "D4"]}

    # D3 비용 집계
    d3_in = d3_out = d3_reason_tok = d3_calls = 0
    # D4가 실제로 D3를 부른 횟수(= D4 API 비용 유발)
    d4_d3_calls = 0

    rows = []
    for i, (_, r) in enumerate(df.iterrows(), 1):
        text = r["text"]
        lang = r["language"]

        # D1
        _, _, e1 = d1_rule.detect(text)
        # D2
        _, _, e2 = d2_classifier.detect(text)
        # D3 (classify로 호출 → usage·reason까지 확보)
        result, e3, usage = d3_llm.classify(text)
        d3_calls += 1
        if usage is not None:
            d3_in += usage.prompt_tokens
            d3_out += usage.completion_tokens
        reason_tok = ntok(str(result.get("reason", "")))
        d3_reason_tok += reason_tok
        # D4
        _, _, e4, stage = d4_cascade.detect(text)
        if stage == "D3":
            d4_d3_calls += 1

        for d, e in [("D1", e1), ("D2", e2), ("D3", e3), ("D4", e4)]:
            lat[d].append(e * 1000)
            lat_lang[d][lang].append(e * 1000)

        rows.append({
            "id": r["id"], "language": lang,
            "d1_ms": e1 * 1000, "d2_ms": e2 * 1000,
            "d3_ms": e3 * 1000, "d4_ms": e4 * 1000,
            "d4_stage": stage, "d3_reason_tokens": reason_tok,
        })
        if i % 20 == 0:
            print(f"  ...{i}/{len(df)}")

    import os
    os.makedirs("results", exist_ok=True)
    pd.DataFrame(rows).to_csv("results/cost_rows.csv", index=False, encoding="utf-8-sig")
    print(f"\n결과 저장: results/cost_rows.csv ({len(rows)}행)")

    # ===== 지연 요약 =====
    print("\n=== 방어별 지연(ms): 평균 / 중앙 / p95 ===")
    for d in ["D1", "D2", "D3", "D4"]:
        v = lat[d]
        print(f"{d}: 평균 {statistics.mean(v):8.1f}  중앙 {statistics.median(v):8.1f}  p95 {pct(v,95):8.1f}")

    print("\n=== 방어 × 언어별 평균 지연(ms) ===")
    print("방어 |     en |     ko |  mixed")
    for d in ["D1", "D2", "D3", "D4"]:
        cells = []
        for L in ["en", "ko", "mixed"]:
            vv = lat_lang[d][L]
            cells.append(f"{statistics.mean(vv):7.1f}" if vv else "   -   ")
        print(f" {d}  | " + " | ".join(cells))

    # ===== 비용 요약 =====
    print("\n=== D3 비용 (gpt-4o-mini 단가) ===")
    cost_in = d3_in * PRICE_IN
    cost_out = d3_out * PRICE_OUT
    cost_full = cost_in + cost_out
    # reason 제외: 출력 토큰에서 reason 분을 뺀 비용
    cost_out_noreason = max(d3_out - d3_reason_tok, 0) * PRICE_OUT
    cost_noreason = cost_in + cost_out_noreason
    print(f"호출 수       : {d3_calls}")
    print(f"입력 토큰 합  : {d3_in:,}  (${cost_in:.4f})")
    print(f"출력 토큰 합  : {d3_out:,}  (${cost_out:.4f})")
    print(f"  └ 그중 reason: {d3_reason_tok:,} 토큰")
    print(f"총 비용(full)       : ${cost_full:.4f}  (호출당 ${cost_full/max(d3_calls,1):.6f})")
    print(f"총 비용(reason 제외): ${cost_noreason:.4f}  → reason 생성 비용 ${cost_full-cost_noreason:.4f} 절감")

    # D4: D1/D2는 무료, D3 호출분만 비용
    d3_cost_per_call = cost_full / max(d3_calls, 1)
    d4_cost = d4_d3_calls * d3_cost_per_call
    print("\n=== D4 비용 ===")
    print(f"D4의 D3 호출 수: {d4_d3_calls} / {len(df)}  (나머지는 D1·D2에서 무료 처리)")
    print(f"D4 추정 비용    : ${d4_cost:.4f}  (D3 단독 ${cost_full:.4f} 대비 {d4_cost/max(cost_full,1e-9)*100:.1f}%)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="eval", choices=["dev", "eval"])
    ap.add_argument("--max-rows", type=int, default=None)
    ap.add_argument("--warmup", type=int, default=10)
    args = ap.parse_args()
    run(split=args.split, max_rows=args.max_rows, n_warmup=args.warmup)