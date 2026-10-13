# C 파트 (보안·방어) — 소재일

C가 담당하는 파일 목록과 작업 공간.
실험 코드가 직접 불러 쓰는 파일은 기능별 폴더에 그대로 두고, C 혼자 쓰는 작업물만 이 폴더에 모은다.

## C 담당 파일 위치

| 파일 | 내용 | 누가 쓰나 |
| --- | --- | --- |
| `target/system_prompt.txt` | 대상 챗봇 시스템 프롬프트 (논문 부록 공개용 원본) | `target/chatbot.py` |
| `defenses/d1_rule.py` | D1 규칙 필터 (영어·한국어·영한 혼합 정규식) | D4, 실험 A |
| `defenses/prompts/d3_system.txt`, `d3_user.txt` | D3 LLM 탐지기 판정 프롬프트 | `defenses/d3_llm.py` |
| `tests/test_d1_rule.py` | D1 단위 테스트 | `python -m unittest tests.test_d1_rule` |
| `data/normals.csv` | 정상·경계 사례 450건 (`c/normals/build_normals.py`로 생성) | 실험 A·B |

## 이 폴더 (`c/`)

| 파일 | 내용 |
| --- | --- |
| `design.md` | 설계 메모: 결정 사항과 이유, 팀 결정이 필요한 항목 |
| `prompt_check.py` | 시스템 프롬프트·D3 프롬프트 간이 점검 (`python -m c.prompt_check`) |
| `normals/normals_source.csv` | 정상·경계 사례 원본. 한 행에 같은 질문의 en·ko·mixed를 나란히 둠 → **수정은 여기서** |
| `normals/build_normals.py` | 원본 검사 + `data/normals.csv` 생성 + dev/eval 분할 (`python -m c.normals.build_normals`) |
| `normals/boundary_review.csv` | 경계 사례 40개 2인 검토 시트 (둘 다 "정상"인 것만 사용) |

## 일정

- ~10/11: 시스템 프롬프트 확정, D1 규칙 초안, D3 판정 프롬프트 초안
- 10/12~16: 정상·경계 사례 450건 생성·검토, D1 규칙 완성(개발용 데이터 기준), D4 구간 확정
- 10/27~: 탐지율·오탐률·서비스 성공률 분석, 그래프 / 11/3 초고 통합
