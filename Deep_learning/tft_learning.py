import os
import pandas as pd
import numpy as np
import torch
import psycopg2
from sqlalchemy import create_engine
from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer
from pytorch_lightning import Trainer
from pytorch_lightning.callbacks import EarlyStopping, LearningRateMonitor
from torch.utils.data import DataLoader
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from sklearn.metrics import classification_report, confusion_matrix
import seaborn as sns

load_dotenv()  # .env 파일에서 환경변수 읽기

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# 환경변수 중 하나라도 없으면 에러 발생
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise EnvironmentError("DB 환경변수(DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME)가 모두 설정되어야 합니다.")

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


# 1. 데이터 불러오기
assets_df = pd.read_sql("SELECT * FROM assets", engine)
revenues_df = pd.read_sql("SELECT * FROM revenues", engine)
labels_df = pd.read_sql("SELECT * FROM labels", engine)

# 2. 전처리
if assets_df.empty or revenues_df.empty or labels_df.empty:
    raise ValueError("One or more tables are empty.")

df = labels_df.merge(assets_df, on="rcept_no", suffixes=('', '_asset'))
df = df.merge(revenues_df, on="rcept_no", suffixes=('', '_revenue'))
df['date'] = pd.to_datetime(df['context'], format='%Y.%m', errors='coerce')

# 단위 환산
def convert_unit(value, unit):
    try:
        value = float(value)
    except:
        return np.nan
    if unit == '백만원': return value * 1_000_000
    elif unit == '천원': return value * 1_000
    elif unit == '억원': return value * 100_000_000
    return value

df['asset_value'] = df.apply(lambda r: convert_unit(r['value'], r['unit']), axis=1)
df['revenue_value'] = df.apply(lambda r: convert_unit(r['value_revenue'], r['unit_revenue']), axis=1)
df['stock_code'] = df['label_text'].apply(lambda x: x.split()[0] if isinstance(x, str) else "Unknown")

df_final = df[['stock_code', 'date', 'asset_value', 'revenue_value']].dropna()
df_final = df_final.sort_values(['stock_code', 'date'])

# 타겟 정의 (binary classification)
df_final['future_revenue'] = df_final.groupby('stock_code')['revenue_value'].shift(-1)
df_final.dropna(inplace=True)
df_final['target'] = (df_final['future_revenue'] > df_final['revenue_value']).astype(int)
df_final['time_idx'] = df_final.groupby('stock_code').cumcount()

# 3. TimeSeriesDataSet
max_encoder_length = 4
max_prediction_length = 1

dataset = TimeSeriesDataSet(
    df_final,
    time_idx='time_idx',
    target='target',
    group_ids=['stock_code'],
    max_encoder_length=max_encoder_length,
    max_prediction_length=max_prediction_length,
    time_varying_known_reals=['time_idx'],
    time_varying_unknown_reals=['asset_value', 'revenue_value'],
    add_relative_time_idx=True,
    add_target_scales=False,
    add_encoder_length=True,
)

# 4. 훈련/검증 분할
train_cutoff = int(len(dataset) * 0.8)
train_dataset = dataset[:train_cutoff]
val_dataset = dataset[train_cutoff:]

train_dataloader = DataLoader(train_dataset, batch_size=64, shuffle=True)
val_dataloader = DataLoader(val_dataset, batch_size=64, shuffle=False)

# 5. 모델 정의 및 학습 (Binary classification)
tft = TemporalFusionTransformer.from_dataset(
    dataset,
    learning_rate=1e-3,
    hidden_size=16,
    attention_head_size=4,
    dropout=0.1,
    loss=torch.nn.BCEWithLogitsLoss(),
    log_interval=10,
    reduce_on_plateau_patience=4,
)

trainer = Trainer(
    max_epochs=20,
    gradient_clip_val=0.1,
    callbacks=[EarlyStopping(monitor="val_loss", patience=5), LearningRateMonitor()],
    enable_model_summary=True,
)

trainer.fit(tft, train_dataloaders=train_dataloader, val_dataloaders=val_dataloader)

# 6. 예측 및 평가
raw_predictions, x = tft.predict(val_dataloader, mode="raw", return_x=True)

logits = raw_predictions['prediction'].squeeze().detach().cpu().numpy()
probs = torch.sigmoid(torch.tensor(logits)).numpy()
preds = (probs >= 0.5).astype(int)
true = x['decoder_target'].squeeze().detach().cpu().numpy()

print("\nClassification Report:")
print(classification_report(true, preds))

# Confusion Matrix 시각화
plt.figure(figsize=(6, 5))
sns.heatmap(confusion_matrix(true, preds), annot=True, fmt='d', cmap='Blues')
plt.title("Confusion Matrix")
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.tight_layout()
plt.show()