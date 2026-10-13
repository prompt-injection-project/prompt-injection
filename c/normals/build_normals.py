"""정상·경계 사례 원본(normals_source.csv)을 검사하고 data/normals.csv로 변환한다.

원본은 한 행 = 기본 정상 문장 1개(base_id)이고, 같은 질문의 영어·한국어·영한 혼합을 나란히 둔다.
공격 데이터와 같은 구조(150개 x 3개 언어, 언어 간 base_id 공유)라 오탐률도 언어만 바꾼 비교가 된다.

분할 (계획서: 정상은 언어별 개발용 20% / 평가용 80%)
- base_id 단위로 나누므로 같은 질문의 세 언어는 항상 같은 쪽에 들어간다
- 일반 110개 중 22개, 경계 40개 중 8개를 개발용으로 → 언어별 평가용 120건(경계 32건)
- 시드 고정이라 다시 실행해도 같은 결과

출력
- data/normals.csv            : 실험용 (README 컬럼 10개, UTF-8 BOM)
- c/normals/boundary_review.csv : 경계 사례 2인 검토 시트 (둘 다 "정상"인 것만 사용)

사용법 (레포 루트에서): python -m c.normals.build_normals
"""

import csv
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(__file__).parent / "normals_source.csv"
OUT = ROOT / "data" / "normals.csv"
REVIEW = Path(__file__).parent / "boundary_review.csv"

SEED = 2026
DEV_GENERAL, DEV_BOUNDARY = 22, 8
ID_START = 1001          # 공격 데이터 id(1~450)와 겹치지 않게
LANGS = ["en", "ko", "mixed"]
COLUMNS = ["id", "base_id", "label", "language", "goal", "difficulty",
           "is_boundary", "source", "split", "text"]

_HANGUL = re.compile(r"[가-힣]")
_LATIN = re.compile(r"[A-Za-z]")


def load():
    with open(SRC, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for lang in LANGS:
            r[lang] = r[lang].replace("\\n", "\n").strip()
    return rows


def validate(rows):
    errors = []
    ids = [r["base_id"] for r in rows]
    if len(rows) != 150 or len(set(ids)) != 150:
        errors.append(f"base_id 150개 고유여야 함 (행 {len(rows)}, 고유 {len(set(ids))})")
    n_general = sum(r["type"] == "general" for r in rows)
    n_boundary = sum(r["type"] == "boundary" for r in rows)
    if (n_general, n_boundary) != (110, 40):
        errors.append(f"일반 110 / 경계 40이어야 함 (현재 {n_general} / {n_boundary})")
    for lang in LANGS:
        texts = [r[lang] for r in rows]
        if any(not t for t in texts):
            errors.append(f"[{lang}] 빈 문장 있음")
        if len(set(texts)) != len(texts):
            errors.append(f"[{lang}] 중복 문장 있음")
    for r in rows:
        if r["type"] == "boundary" and not r["boundary_type"]:
            errors.append(f"{r['base_id']}: 경계 사례인데 boundary_type 없음")
        if not _HANGUL.search(r["ko"]):
            errors.append(f"{r['base_id']}: ko에 한글 없음")
        if not (_HANGUL.search(r["mixed"]) and _LATIN.search(r["mixed"])):
            errors.append(f"{r['base_id']}: mixed에 한글·영어가 함께 있어야 함")
        if _HANGUL.search(r["en"]):
            errors.append(f"{r['base_id']}: en에 한글 있음")
    if errors:
        raise SystemExit("원본 검사 실패:\n- " + "\n- ".join(errors))


def assign_split(rows):
    rng = random.Random(SEED)
    split = {}
    for kind, n_dev in [("general", DEV_GENERAL), ("boundary", DEV_BOUNDARY)]:
        ids = sorted(r["base_id"] for r in rows if r["type"] == kind)
        dev = set(rng.sample(ids, n_dev))
        split.update({b: ("dev" if b in dev else "eval") for b in ids})
    return split


def build():
    rows = load()
    validate(rows)
    split = assign_split(rows)

    out_rows, next_id = [], ID_START
    for r in rows:
        for lang in LANGS:
            out_rows.append({
                "id": next_id, "base_id": r["base_id"], "label": "normal", "language": lang,
                "goal": "", "difficulty": "",
                "is_boundary": "true" if r["type"] == "boundary" else "false",
                "source": "generated", "split": split[r["base_id"]], "text": r[lang],
            })
            next_id += 1

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out_rows)

    with open(REVIEW, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["base_id", "boundary_type", "split", "en", "ko", "mixed",
                    "reviewer1(정상/공격)", "reviewer2(정상/공격)", "메모"])
        for r in rows:
            if r["type"] == "boundary":
                w.writerow([r["base_id"], r["boundary_type"], split[r["base_id"]],
                            r["en"], r["ko"], r["mixed"], "", "", ""])

    print(f"{OUT.relative_to(ROOT)}: {len(out_rows)}건")
    for lang in LANGS:
        sub = [x for x in out_rows if x["language"] == lang]
        ev = [x for x in sub if x["split"] == "eval"]
        print(f"  [{lang}] 전체 {len(sub)} (경계 {sum(x['is_boundary'] == 'true' for x in sub)})"
              f" / 평가용 {len(ev)} (경계 {sum(x['is_boundary'] == 'true' for x in ev)})")
    print(f"{REVIEW.relative_to(ROOT)}: 경계 사례 {sum(r['type'] == 'boundary' for r in rows)}개")


if __name__ == "__main__":
    build()
