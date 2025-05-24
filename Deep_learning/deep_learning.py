import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, classification_report, precision_score, recall_score
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import tensorflow as tf
from tensorflow.keras import backend as K
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Bidirectional, Dropout, BatchNormalization
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau



# .env 파일 로드 (있으면)
load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# 필수 환경변수 모두 체크
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise EnvironmentError("DB 환경변수(DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME)를 모두 설정해주세요.")

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


query = """
SELECT p.stk_cd, p.date, p.open_pric, p.high_pric, p.low_pric, p.close_pric,
       o.oyr_hgst, o.oyr_lwst, o.base_pric, o.cur_prc AS access_cur_prc, o.trde_qty,
       b.rank, b.acc_trde_qty,
       i.listcount
FROM price_data p
LEFT JOIN original_access_data o ON p.stk_cd = o.stk_cd
LEFT JOIN buyTop50_data b ON p.stk_cd = b.stk_cd
LEFT JOIN infolist_data i ON p.stk_cd = i.code
WHERE p.date IS NOT NULL
ORDER BY p.stk_cd, p.date;
"""

df = pd.read_sql(query, engine)

# --- 전처리 ---
df = df.fillna(0)
df['date'] = pd.to_datetime(df['date'], errors='coerce')
df = df.sort_values(by=['stk_cd', 'date'])
df['next_close'] = df.groupby('stk_cd')['close_pric'].shift(-1)
df['target'] = (df['next_close'] > df['close_pric']).astype(int)
df = df.dropna(subset=['target'])

features = ['open_pric', 'high_pric', 'low_pric', 'close_pric',
            'oyr_hgst', 'oyr_lwst', 'base_pric', 'access_cur_prc',
            'trde_qty', 'rank', 'acc_trde_qty', 'listcount']

split_idx = int(len(df) * 0.8)
train_df = df[:split_idx]
test_df = df[split_idx:]

scaler = MinMaxScaler()
train_df[features] = scaler.fit_transform(train_df[features])
test_df[features] = scaler.transform(test_df[features])

# --- 시퀀스 생성 함수 ---
def create_sequences(data, target, time_steps=15):
    X, y = [], []
    for i in range(len(data) - time_steps):
        X.append(data[i:i + time_steps])
        y.append(target[i + time_steps])
    return np.array(X), np.array(y)

X_train, y_train = create_sequences(train_df[features].values, train_df['target'].values)
X_test, y_test = create_sequences(test_df[features].values, test_df['target'].values)

X_train_final, X_val, y_train_final, y_val = train_test_split(
    X_train, y_train, test_size=0.1, random_state=42, stratify=y_train
)

# --- 모델 구성 ---
model = Sequential([
    Bidirectional(LSTM(64, return_sequences=True), input_shape=(X_train.shape[1], X_train.shape[2])),
    Dropout(0.3),
    BatchNormalization(),
    Bidirectional(LSTM(32, return_sequences=False)),
    Dropout(0.3),
    BatchNormalization(),
    Dense(1, activation='sigmoid')
])

model.compile(
    optimizer=Adam(learning_rate=0.0001),
    loss='binary_crossentropy',
    metrics=['accuracy']
)

class_weights = {0: 2.67, 1: 1.0}

early_stopping = EarlyStopping(monitor='val_loss', patience=20, restore_best_weights=True)
reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6)

history = model.fit(
    X_train_final, y_train_final,
    epochs=100,
    batch_size=32,
    validation_data=(X_val, y_val),
    callbacks=[early_stopping, reduce_lr],
    class_weight=class_weights
)

y_pred_prob = model.predict(X_test).ravel()
y_pred = (y_pred_prob >= 0.5).astype(int)

plt.hist(y_pred_prob, bins=100, color='skyblue')
plt.title("Prediction Probability Distribution")
plt.xlabel("Probability of Class 1")
plt.ylabel("Count")
plt.grid(True)
plt.show()

cm = confusion_matrix(y_test, y_pred)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=['Down', 'Up'], yticklabels=['Down', 'Up'])
plt.title("Confusion Matrix")
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.show()

print("\nClassification Report:")
print(classification_report(y_test, y_pred))

print("\nPrecision (0):", precision_score(y_test, y_pred, pos_label=0))
print("Recall (0):", recall_score(y_test, y_pred, pos_label=0))

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
sns.countplot(x=y_test, ax=axes[0], palette='pastel')
axes[0].set_title("Actual Class Distribution")
sns.countplot(x=y_pred, ax=axes[1], palette='Set2')
axes[1].set_title("Predicted Class Distribution")
plt.tight_layout()
plt.show()

from sklearn.metrics import precision_recall_curve
precision, recall, thresholds = precision_recall_curve(y_test, y_pred_prob)
plt.figure(figsize=(8, 6))
plt.plot(recall, precision, marker='.', color='purple')
plt.title("Precision-Recall Curve")
plt.xlabel("Recall")
plt.ylabel("Precision")
plt.grid(True)
plt.show()

from sklearn.metrics import roc_curve, auc
fpr, tpr, thresholds = roc_curve(y_test, y_pred_prob)
roc_auc = auc(fpr, tpr)
plt.figure(figsize=(8, 6))
plt.plot(fpr, tpr, color='darkorange', lw=2, label='ROC curve (area = %0.2f)' % roc_auc)
plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
plt.title('Receiver Operating Characteristic')
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.legend(loc="lower right")
plt.grid(True)
plt.show()

plt.figure(figsize=(14, 4))
plt.plot(y_test[:200], label='Actual', marker='o', linestyle='--')
plt.plot(y_pred[:200], label='Predicted', marker='x')
plt.title("Actual vs Predicted (First 200 samples)")
plt.xlabel("Sample Index")
plt.ylabel("Class")
plt.legend()
plt.grid(True)
plt.show()