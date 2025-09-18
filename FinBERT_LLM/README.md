# 금융 뉴스 감성 분석 파이프라인

이 프로젝트는 PostgreSQL 데이터베이스에서 수집된 한국어 금융 뉴스의 감성을 자동으로 분석하고, 그 결과를 다시 데이터베이스에 저장하는 파이프라인입니다.

**KR-FinBERT**와 **Google Gemini** 모델을 결합한 하이브리드 접근 방식을 사용하여, 뉴스의 제목과 본문을 각각 분석하고 종합적인 결론을 도출함으로써 분석의 정확도를 높였습니다.

---

## 🌟 주요 기능

* **하이브리드 감성 분석**:
    * **제목 분석**: 한국어 금융 도메인에 특화된 `KR-FinBERT` 모델을 사용하여 빠르고 정확하게 제목의 핵심 감성을 분석합니다.
    * **본문 분석**: Google의 강력한 LLM인 `Gemini`를 사용하여 기사 본문 전체의 깊이 있는 문맥과 뉘앙스를 파악합니다.
* **보수적 최종 라벨링**: 제목과 본문의 감성 분석 결과가 불일치할 경우, 해당 뉴스는 해석이 모호하다고 판단하여 최종 라벨을 `neutral`로 지정함으로써 노이즈를 최소화합니다.
* **자동화된 데이터 처리**: PostgreSQL DB에서 아직 라벨링되지 않은 뉴스를 자동으로 불러와 분석하고, 최종 결과를 DB에 다시 업데이트합니다.
* **안정적인 API 연동**: Gemini API 호출 시 발생할 수 있는 네트워크 오류나 응답 길이 불일치 문제에 대응하기 위해, **자동 재시도 및 지연(Exponential Backoff)** 로직을 구현했습니다.
* **체계적인 모듈 구조**: 설정, DB 핸들링, 모델 분석 등 각 기능이 별도의 파일로 분리되어 있어 코드의 가독성과 유지보수성을 높였습니다.
* **안전한 자격 증명 관리**: 데이터베이스 비밀번호, API 키 등 민감한 정보는 `.env` 파일을 통해 안전하게 관리합니다.

---

## ⚙️ 프로젝트 아키텍처

프로젝트는 다음과 같은 순서로 작동합니다.

1.  **`main.py` 실행**: 전체 분석 파이프라인을 시작합니다.
2.  **데이터 로드 (`db_handler.py`)**: PostgreSQL에서 `label`이 비어있는 뉴스 데이터를 불러옵니다.
3.  **제목 분석 (`finbert_analyzer.py`)**: KR-FinBERT 모델을 사용하여 각 뉴스의 **제목**을 분석하고 1차 감성 라벨(`predicted_label`)을 부여합니다.
4.  **본문 분석 (`gemini_analyzer.py`)**: Gemini API를 사용하여 각 뉴스의 **본문**을 분석하고 2차 감성 라벨(`gemini_label`)을 부여합니다.
5.  **결과 종합 (`main.py`)**: 두 라벨을 비교하여 최종 라벨(`final_label`)을 결정합니다. (불일치 시 `neutral`)
6.  **결과 저장**:
    * 분석의 모든 과정이 포함된 DataFrame을 `News_DB_sentiment_results.csv` 파일로 저장합니다.
    * 최종 라벨을 PostgreSQL 데이터베이스의 `label` 컬럼에 업데이트합니다 (`db_handler.py`).



---

## 🚀 시작하기

### 1. 사전 요구사항

* Python 3.8 이상
* PostgreSQL 데이터베이스
    * `News_data`라는 이름의 데이터베이스
    * `id`, `title`, `description` 등의 컬럼을 포함하는 `company_news` 테이블
* Google Gemini API 키

### 2. 설치 및 설정

1.  **필요 라이브러리 설치**
    ```bash
    pip install -r requirements.txt
    ```

2.  **환경 변수 설정**
    * `.env.example` 파일을 참고하여 `.env` 파일을 생성합니다.
    * 생성된 `.env` 파일을 열어 실제 데이터베이스 정보와 Gemini API 키를 입력합니다.
    ```ini
    # .env
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY"

    DB_USER="postgres"
    DB_PASSWORD="YOUR_DATABASE_PASSWORD"
    DB_HOST="localhost"
    DB_PORT="5432"
    DB_NAME="News_data"
    ```

3.  **학습된 FinBERT 가중치 준비** (선택 사항)
    * 직접 파인튜닝한 FinBERT 모델 가중치 파일(`best_model.pt`)이 있다면, 프로젝트 최상위 폴더에 위치시킵니다.
    * 파일이 없을 경우, `finbert_analyzer.py`는 기본 `snunlp/KR-FinBert-SC` 모델을 사용합니다.

### 3. 실행 방법

모든 설정이 완료되었다면, 터미널에서 다음 명령어를 실행하여 전체 분석 파이프라인을 시작합니다.

```bash
python main.py
```

실행 시 각 단계의 진행 상황이 터미널에 출력되며, 완료 후에는 CSV 파일이 생성되고 데이터베이스가 업데이트됩니다.

---

## 📂 프로젝트 구조

```
📁 project_folder/
├── 📄 .env.example           # .env 파일 구성을 위한 템플릿
├── 📄 requirements.txt       # 프로젝트 의존성 라이브러리 목록
|
├── 🐍 config.py             # 모델 이름, DB 정보 등 주요 설정 값 관리
├── 🐍 db_handler.py         # PostgreSQL 연결, 데이터 조회 및 업데이트 담당
├── 🐍 finbert_analyzer.py   # KR-FinBERT 모델 로딩 및 제목 분석 로직 담당
├── 🐍 gemini_analyzer.py    # Gemini API 호출, 본문 분석 및 재시도 로직 담당
└── 🐍 main.py               # 전체 분석 파이프라인을 조율하고 실행하는 메인 파일
```
