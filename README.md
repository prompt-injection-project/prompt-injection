# Prompt Injection 방어 미들웨어 비교 연구

LLM 기반 서비스(사내 IT 헬프데스크 챗봇)에서 Prompt Injection 방어 방식별
보안 성능·서비스 오버헤드를 비교하는 실험 코드 저장소임.
영어·한국어·영한 혼합 공격을 중심으로 비교함.

## 폴더 구조

```
prompt-injection/
├── data/                   # 실험 데이터 (B 담당)
│   ├── attacks.csv         # 공격 문장
│   └── normals.csv         # 정상 문장
├── defenses/               # 방어 방식 (A·C 담당)
│   ├── __init__.py
│   ├── d1_rule.py          # D1 규칙 필터
│   ├── d2_classifier.py    # D2 경량 분류 모델 (Prompt Guard)
│   ├── d3_llm.py           # D3 LLM 탐지기 (GPT)
│   └── d4_cascade.py       # D4 단계별 방어 (D1→D2→D3)
├── target/
│   └── chatbot.py          # 대상 LLM (헬프데스크 챗봇)
├── experiments/
│   └── run_detection.py    # 실험 A: 탐지 성능
├── results/                # 실험 결과 저장 (자동 생성)
├── check_data.py           # 데이터 형식 검사
├── .env                    # API 키 (git에 올리지 말 것)
└── .gitignore
```

## 처음 세팅

1. 저장소 클론 후 폴더 진입

2. 라이브러리 설치
```
pip install "openai==1.54.0" "httpx<0.28" python-dotenv transformers torch pandas
```

3. `.env` 파일 생성 (각자 발급받은 키 입력)
```
OPENAI_API_KEY=sk-본인_키
HF_TOKEN=hf_본인_토큰
```
- OpenAI 키: https://platform.openai.com/api-keys
- HF 토큰: https://huggingface.co/settings/tokens (Read 권한)
- D2 모델 접근 신청 필요: meta-llama/Llama-Prompt-Guard-2-86M

4. 동작 확인
```
python -m defenses.d4_cascade        # 방어 4개 조립 테스트
python -m experiments.run_detection  # 실험 A 테스트
```

## 방어 방식 (D0~D4)

| 방어 | 방식 | 실행 위치 | 비용 |
|---|---|---|---|
| D0 | 방어 없음 (기준선) | - | - |
| D1 | 규칙 필터 (정규식) | 서버 내부 | 무료 |
| D2 | 경량 분류 모델 (Prompt Guard) | 서버 내부 | 무료 |
| D3 | LLM 탐지기 (GPT에게 질의) | 외부 API | 유료 |
| D4 | 단계별 (D1→D2→애매하면 D3) | 혼합 | 일부 유료 |

모든 방어는 `detect(text)` 형식으로 통일됨.
반환값: `(차단 여부(bool), 점수(0~1), 처리 시간(초))`

## 데이터 형식 (중요)

공격은 `data/attacks.csv`, 정상은 `data/normals.csv`에 작성함.
컬럼은 아래 10개로 고정:

| 컬럼 | 값 | 비고 |
|---|---|---|
| id | 1, 2, 3... | 고유 번호 |
| base_id | a001, n001... | 같은 공격의 3개 언어가 공유 |
| label | attack / normal | |
| language | en / ko / mixed | |
| goal | leak / hijack / (빈칸) | 공격만 |
| difficulty | L1 / L2 / L3 / (빈칸) | 공격만 |
| is_boundary | true / false | 경계 사례 여부 |
| source | tensortrust / deepset / generated | |
| split | dev / eval | 개발용 / 평가용 |
| text | 문장 | 쉼표·줄바꿈 있으면 큰따옴표로 감쌈 |

**표기 규칙**
- 전부 소문자 (difficulty의 L만 대문자: L1, L2, L3)
- 정상 문장의 goal·difficulty는 빈칸 (none, - 쓰지 말 것)
- 같은 공격의 영어·한국어·영한 혼합은 base_id 똑같이
- 파일은 UTF-8로 저장
- 작성 후 `python check_data.py`로 형식 검사

## 역할 분담

| 역할 | 담당 | 작업 |
|---|---|---|
| A (백엔드) | - | API·모델 연동, 방어 구현, 실험 실행, 지연·비용 측정 |
| B (공격) | - | 공격 데이터 선정·변환·난이도 분류, 공격 성공 판정 |
| C (방어) | - | D1 규칙·D3 프롬프트·시스템 프롬프트 설계, 정상·경계 사례 작성 |

## 현재 진행 상황 (2026-10-10)

- [x] 방어 D1~D4 뼈대 완료 (동작 확인됨)
- [x] 대상 LLM 호출 함수 완료
- [x] 실험 A (탐지 성능) 스크립트 완료
- [ ] 실험 B (공격 성공률) 스크립트
- [ ] 실험 C (지연·비용) 스크립트
- [ ] 시스템 프롬프트 확정 (C)
- [ ] 데이터 450건 작성 (B·C)

## 주의

- `.env`는 절대 git에 올리지 말 것 (API 키 유출 방지, .gitignore에 포함됨)
- API 사용 한도를 OpenAI 설정에서 걸어둘 것
