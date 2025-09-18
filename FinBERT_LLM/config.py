import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

# --- 데이터베이스 정보 ---
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

# --- 모델 정보 ---
FINBERT_MODEL_NAME = "snunlp/KR-FinBert-SC" # FinBert 모델
FINBERT_WEIGHT_PATH = "best_model.pt"  # 학습된 가중치 파일 경로
GEMINI_MODEL_NAME = "gemini-2.0-flash" # gemini 모델

# --- Gemini 분석 설정 ---
BATCH_SIZE = 100
MAX_RETRIES = 3
RETRY_DELAY_MULTIPLIER = 2
API_REQUEST_DELAY = 30

# --- 결과 저장 파일 이름 ---
OUTPUT_CSV_NAME = "News_DB_sentiment_results.csv" # CSV로 저장