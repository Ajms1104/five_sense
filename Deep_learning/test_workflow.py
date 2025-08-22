import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
import psycopg2 # PostgreSQL DB 연결을 위한 라이브러리
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

# --- 0. 환경 변수 및 DB 정보 불러오기 ---
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# DB 정보가 하나라도 누락되었는지 확인
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise EnvironmentError(".env 파일에 DB 환경변수가 모두 설정되어야 합니다.")

# --- 1. 데이터 준비 ---
try:
    df = pd.read_csv('final_combined_data.csv')
except FileNotFoundError:
    print("Error: 'final_combined_data.csv' 파일을 찾을 수 없습니다.")
    exit()

df['Date'] = pd.to_datetime(df['Date'])

if len(df) < 5:
    print(f"Warning: 데이터가 {len(df)}개로 너무 적어 의미 있는 학습이 어렵습니다.")
    exit()
elif len(df) < 30:
    SEQUENCE_LENGTH = len(df) // 2
    print(f"Info: 데이터가 부족하여 SEQUENCE_LENGTH를 {SEQUENCE_LENGTH}(으)로 자동 조정합니다.")
else:
    SEQUENCE_LENGTH = 30

# --- 2. 모델 학습 ---
features = df[['lstm_pred_log', 'sentiment_score']].values
target = df['true_target_log_return'].values.reshape(-1, 1)

feature_scaler = MinMaxScaler()
target_scaler = MinMaxScaler()

scaled_features = feature_scaler.fit_transform(features)
scaled_target = target_scaler.fit_transform(target)

X_train, y_train = [], []
for i in range(len(scaled_features) - SEQUENCE_LENGTH):
    X_train.append(scaled_features[i:i+SEQUENCE_LENGTH])
    y_train.append(scaled_target[i+SEQUENCE_LENGTH])

X_train = np.array(X_train)
y_train = np.array(y_train)

model = Sequential([
    LSTM(50, return_sequences=True, input_shape=(X_train.shape[1], X_train.shape[2])),
    LSTM(50),
    Dense(1)
])
model.compile(optimizer='adam', loss='mse')

print("\n===== 모델 학습 시작 =====")
model.fit(X_train, y_train, epochs=50, batch_size=16, verbose=1)
print("===== 모델 학습 완료 =====")

# --- 3. 다음 영업일 예측 ---
last_sequence = scaled_features[-SEQUENCE_LENGTH:]
last_sequence = np.expand_dims(last_sequence, axis=0)

predicted_scaled_value = model.predict(last_sequence)
predicted_value = target_scaler.inverse_transform(predicted_scaled_value)[0][0]

last_date = df['Date'].iloc[-1]
target_date = last_date + timedelta(days=1)
stock_code = df['stk_cd'].iloc[-1]

print(f"\n===== 예측 결과 =====")
print(f"예측 대상 날짜: {target_date.strftime('%Y-%m-%d')}")
print(f"종목 코드: {int(stock_code)}")
print(f"예측된 Log Return: {predicted_value}")

# --- 4. 예측 결과를 DB에 저장 ---
conn = None # 연결 변수 초기화
try:
    # .env 파일의 정보로 DB에 연결
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )
    cursor = conn.cursor()

    # 테이블이 없으면 생성 (SQLite와 문법 동일)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_predictions (
        id SERIAL PRIMARY KEY,
        prediction_saved_at TIMESTAMP,
        target_date DATE,
        stock_code INTEGER,
        predicted_log_return REAL
    )
    ''')

    insert_data = (
    datetime.now(),
    target_date.strftime('%Y-%m-%d'),
    int(stock_code),
    float(predicted_value) # <-- [수정] float()으로 감싸서 파이썬 기본 숫자로 변환
)
    cursor.execute(
        "INSERT INTO stock_predictions (prediction_saved_at, target_date, stock_code, predicted_log_return) VALUES (%s, %s, %s, %s)",
        insert_data
    )

    conn.commit()
    cursor.close()
    print("\n===== DB 저장 완료 =====")
    print(f"예측 결과를 '{DB_NAME}' 데이터베이스에 성공적으로 저장했습니다.")

except Exception as e:
    print(f"DB 작업 중 오류가 발생했습니다: {e}")

finally:
    if conn is not None:
        conn.close()

# --- 5. DB 저장 결과 확인 ---
print("\n===== DB 저장 내용 확인 =====")
conn = None
try:
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
    )
    db_df = pd.read_sql_query("SELECT * FROM stock_predictions ORDER BY id DESC LIMIT 5", conn)
    print(db_df)

except Exception as e:
    print(f"DB에서 데이터를 불러오는 중 오류가 발생했습니다: {e}")

finally:
    if conn is not None:
        conn.close()