import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

# --- 1. 데이터 불러오기 및 전처리 ---

try:
    # 이전에 생성한 통합 CSV 파일 불러오기
    df = pd.read_csv('final_combined_data.csv')
except FileNotFoundError:
    print("Error: 'final_combined_data.csv' 파일을 찾을 수 없습니다.")
    print("이전 단계의 스크립트를 먼저 실행하여 파일을 생성해주세요.")
    exit()

# 모델에 사용할 특성(입력)과 타겟(정답) 선택
features = df[['lstm_pred_log', 'sentiment_score']].values
target = df['true_target_log_return'].values.reshape(-1, 1)

# 데이터 정규화 (0과 1 사이의 값으로 변환)
feature_scaler = MinMaxScaler()
scaled_features = feature_scaler.fit_transform(features)

target_scaler = MinMaxScaler()
scaled_target = target_scaler.fit_transform(target)


# --- 2. 시퀀스 데이터 생성 (Windowing) ---

# 과거 며칠의 데이터를 보고 미래를 예측할지 결정 (시퀀스 길이)
SEQUENCE_LENGTH = 30 
X, y = [], []

for i in range(len(scaled_features) - SEQUENCE_LENGTH):
    # 입력 시퀀스: i부터 i+SEQUENCE_LENGTH 이전까지
    X.append(scaled_features[i:i+SEQUENCE_LENGTH])
    # 정답: i+SEQUENCE_LENGTH 시점의 값
    y.append(scaled_target[i+SEQUENCE_LENGTH])

X = np.array(X)
y = np.array(y)

# 데이터셋 분리 (훈련용, 테스트용) - 시간 순서를 유지하기 위해 shuffle=False
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

print(f"훈련 데이터 형태: {X_train.shape}") # (샘플 수, 시퀀스 길이, 특성 수)
print(f"테스트 데이터 형태: {X_test.shape}")


# --- 3. LSTM 모델 구축 ---

model = Sequential([
    # 입력층: input_shape=(시퀀스 길이, 특성 수)
    LSTM(units=50, return_sequences=True, input_shape=(X_train.shape[1], X_train.shape[2])),
    Dropout(0.2), # 과적합 방지를 위한 드롭아웃
    LSTM(units=50, return_sequences=False),
    Dropout(0.2),
    Dense(units=25),
    # 출력층: 1개의 값을 예측
    Dense(units=1) 
])

# 모델 컴파일
model.compile(optimizer='adam', loss='mean_squared_error')
model.summary()


# --- 4. 모델 학습 ---

history = model.fit(
    X_train, 
    y_train,
    epochs=50, # 전체 데이터를 몇 번 반복 학습할지
    batch_size=32, # 한 번에 몇 개의 데이터를 묶어서 학습할지
    validation_data=(X_test, y_test),
    verbose=1
)


# --- 5. 예측 및 결과 시각화 ---

# 테스트 데이터로 예측 수행
predictions = model.predict(X_test)

# 정규화된 예측값을 다시 원래 값의 범위로 되돌림
predictions_inversed = target_scaler.inverse_transform(predictions)
y_test_inversed = target_scaler.inverse_transform(y_test)

# 그래프로 결과 확인
plt.figure(figsize=(14, 6))
plt.plot(y_test_inversed, label='Actual Price Return (True Value)')
plt.plot(predictions_inversed, label='Predicted Price Return (Prediction)')
plt.title('Stock Price Return Prediction using Combined Data')
plt.xlabel('Time')
plt.ylabel('Log Return')
plt.legend()
plt.grid(True)
plt.show()