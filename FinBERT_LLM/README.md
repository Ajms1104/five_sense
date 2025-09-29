# KR 금융 뉴스 감성 분석 파이프라인 (FinBERT + Gemini)

> **한 줄 요약**: PostgreSQL에 저장된 한국어 기업/증시 뉴스의 제목(모델: FinBERT)과 본문(모델: Gemini)을 각기 점수화한 뒤 **가중 평균**으로 최종 감성 라벨(positive/neutral/negative)을 산출하고, 결과를 **CSV 저장 + DB 업데이트**까지 자동화한 파이프라인입니다.

---

## 기능 요약
- **DB 준비**: `company_news` 테이블에 `label`, `score` 컬럼이 없으면 자동 추가
- **데이터 수집**: 아직 분석되지 않은 레코드만 `id` 오름차순으로 조회
- **제목 감성 분석(FinBERT)**: 문장 분할 후 배치 추론 → -1~1 스케일의 점수 산출
- **본문 감성 분석(Gemini)**: 시스템 프롬프트 기반 일괄 추론 + 재시도/백오프 처리
- **점수 결합·라벨링**: 설정된 가중치·임계값으로 최종 스코어와 라벨 생성
- **결과 출력**: CSV 저장 + DB에 `label`, `score` 업데이트

---

## 아키텍처 개요
```
PostgreSQL (company_news)
      │  (id, title, description ...)
      ▼
[데이터 로더] db_handler.fetch_news_data()
      │
      ├─► [제목 스코어] finbert_analyzer.analyze_titles()
      │
      ├─► [본문 스코어] gemini_analyzer.analyze_descriptions()
      │
      ▼
[스코어 결합] 가중 평균 → 최종 점수/라벨
      │
      ├─► CSV 저장 (News_DB_sentiment_results.csv)
      └─► DB 업데이트 (label, score)
```

---

## 설계 및 운영 포인트
- **제목/본문 분리 추론**: FinBERT(제목) + Gemini(본문) 앙상블로 역할 분리.
- **ID 기반 정합성 유지**: `id` 키를 기준으로 결과를 매핑하여 혼선을 방지.
- **운영 고려 사항 포함**: 배치 처리, 재시도/백오프, 트랜잭션 기반 일괄 업데이트.
- **환경/보안 분리**: `.env`로 자격 증명 및 환경 값을 분리하여 이식성 확보.

---

## 빠른 시작

### 1) 요구 사항
- Python 3.10+
- PostgreSQL 13+ (또는 호환 버전)
- (선택) CUDA가속 환경

### 2) 설치
```bash
pip install -r requirements.txt
```

### 3) .env 설정
```bash
# DB
DB_NAME=News_data
DB_USER=postgres
DB_PASSWORD=********
DB_HOST=localhost
DB_PORT=5432

# Gemini
GEMINI_API_KEY=api_key
GEMINI_PROMPT=prompt
```

### 4) DB 테이블
```sql
CREATE TABLE IF NOT EXISTS company_news (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL, -- 제목 텍스트
  description TEXT,    -- 요약된 뉴스 텍스트
  label VARCHAR(10),   -- positive/neutral/negative 감성 라벨
  score FLOAT          -- -1 ~ 1 사이의 감성 점수 값(1에 가까울 수록 positive, -1에 가까울 수록 negative)
);
```

### 5) 실행
```bash
python main.py
```
- 결과 CSV: `News_DB_sentiment_results.csv`
- DB: `label`/`score` 컬럼이 채워집니다.

---

## 파일 구성
```
.
├─ config.py                 # 환경 변수 로드, 모델/가중치/배치 설정
├─ db_handler.py             # DB 준비/조회/업데이트 (ex. company_news)
├─ finbert_analyzer.py       # 제목 감성 점수 산출(FinBERT)
├─ gemini_analyzer.py        # 본문 감성 점수 산출(Gemini, 배치/재시도)
├─ main.py                   # 파이프라인 오케스트레이션(결합/라벨/저장/업데이트)
├─ requirements.txt          # 파이썬 의존성 목록
└─ News_DB_sentiment_results.csv  # (실행 후) 결과 CSV
```

---

## 동작 방식

### 1) 환경/설정
- `.env`에서 DB 및 API 정보를 불러옵니다.
- 모델 이름, 가중치, 배치/재시도 파라미터 등은 `config.py`로 중앙화되어 있습니다.

### 2) 데이터 로딩
- `company_news` 테이블에서 아직 라벨/스코어가 없는 레코드만 `id` 오름차순으로 가져옵니다(기본 100개).

### 3) 제목 스코어 (FinBERT)
- 한국어 뉴스 **제목**을 문장 단위로 분할한 뒤, 사전학습된 FinBERT(필요 시 커스텀 가중치 로드)를 이용해 각 문장을 분류 확률로 추론합니다.
- 클래스 가중치 `[-1, 0, 1]`과 소프트맥스를 이용해 문장별 점수를 계산하고 **평균**하여 제목 스코어를 만듭니다.

### 4) 본문 스코어 (Gemini)
- 명시적인 **시스템 프롬프트**로 금융 도메인 규칙을 고정합니다.
- 본문 텍스트를 **배치 처리**하며, 파싱 불일치/일시적 오류를 고려해 **재시도와 지수 백오프**를 수행합니다.
- 출력은 -1(부정) ~ 1(긍정) 범위의 **연속 점수**입니다.

### 5) 스코어 결합과 라벨링
- 최종 점수 = `finbert_score * W_f` + `gemini_score * W_g` (기본 0.3 / 0.7)
- 라벨링 기준(기본 임계값 0.1):
  - > +0.1 → **positive**
  - < -0.1 → **negative**
  - 나머지 → **neutral**

### 6) 결과 저장 및 반영
- CSV 파일로 전체 결과를 저장하며, DB에는 `label`, `score`만 업데이트합니다(배치 업데이트).

---

## 설정값(기본)
- **FinBERT 모델**: `snunlp/KR-FinBert-SC` (필요 시 `best_model.pt` 가중치 로드)
- **Gemini 모델**: `gemini-2.0-flash`
- **가중치**: FinBERT 0.3 / Gemini 0.7
- **배치/재시도**: `BATCH_SIZE=100`, `MAX_RETRIES=3`, `RETRY_DELAY_MULTIPLIER=2`, `API_REQUEST_DELAY=30s`
- **라벨 임계값**: 0.1
- **출력 파일명**: `News_DB_sentiment_results.csv`

---

## 테스트 & 재현 팁
- 소량 데이터로 `.env`/DB 연결 확인 → 배치/재시도 로직 정상 동작 체크
- `FINBERT_WEIGHT_PATH`를 비워 사전학습 가중치 vs. 커스텀 가중치 비교
- 임계값(0.1)과 가중치(0.3/0.7)를 조정해 라벨 분포 민감도 분석

---

## 한계 & 주의 사항
- **API 비용/쿼터**: Gemini 호출은 비용/쿼터가 있으니 배치/지연 설정을 운영 환경에 맞게 조정하세요.
- **데이터 품질**: 본문 결측치/잡음이 많을 경우 결과 품질이 하락할 수 있습니다.
- **모델 편향**: 도메인/기간별 편향 가능성 → 주기적 재학습/검증 권장.
- **보안**: API 키/DB 비밀번호는 반드시 `.env`로 관리하고 커밋 금지.
