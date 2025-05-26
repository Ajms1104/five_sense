# =============================================
# 재무제표 기반 Temporal Fusion Transformer 예측 모델
# =============================================

import os
import pandas as pd
import numpy as np
import torch
import torch.nn.functional as F
from sqlalchemy import create_engine
from sklearn.metrics import classification_report, confusion_matrix
from torch.utils.data import DataLoader
from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer
from pytorch_forecasting.metrics import Metric
from lightning.pytorch import Trainer
from lightning.pytorch.callbacks import EarlyStopping, LearningRateMonitor
from lightning.pytorch.loggers import TensorBoardLogger
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import seaborn as sns

# ==============================
# 1. 환경 설정 및 DB 연결
# ==============================

load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAMET")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise EnvironmentError("DB 환경변수가 모두 설정되어야 합니다.")

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# ==============================
# 2. Custom Loss 정의 (Binary Classification용)
# ==============================

class CustomBCEWithLogitsLoss(Metric):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def forward(self, y_pred, target):
        return F.binary_cross_entropy_with_logits(y_pred, target.float())

# ==============================
# 3. 데이터 로딩 및 전처리
# ==============================

# 단일 보고서 번호 기준 (예시: 삼성전자 2020년 재무제표)
RCEPT_NO = '20210309000744'

labels_df = pd.read_sql(f"SELECT rcept_no, label_text FROM labels WHERE rcept_no = '{RCEPT_NO}'", engine)
assets_df = pd.read_sql(f"SELECT rcept_no, value, context, unit FROM assets WHERE rcept_no = '{RCEPT_NO}'", engine)
revenues_df = pd.read_sql(f"SELECT rcept_no, value, context, unit FROM revenues WHERE rcept_no = '{RCEPT_NO}'", engine)

# 숫자형 변환
assets_df['asset_value'] = assets_df['value'].astype(float)
revenues_df['revenue_value'] = revenues_df['value'].astype(float)

# 날짜 파싱
def parse_assets_date(s):
    return s.replace("Instant:", "").strip() if isinstance(s, str) and s.startswith("Instant:") else None

def parse_revenues_date(s):
    parts = s.split("to")
    return parts[1].strip() if isinstance(s, str) and s.startswith("Duration:") and len(parts) == 2 else None

assets_df['date'] = pd.to_datetime(assets_df['context'].apply(parse_assets_date), errors='coerce')
revenues_df['date'] = pd.to_datetime(revenues_df['context'].apply(parse_revenues_date), errors='coerce')

# 결측 제거
assets_df = assets_df.dropna(subset=['date']).reset_index(drop=True)
revenues_df = revenues_df.dropna(subset=['date']).reset_index(drop=True)

# 데이터 병합: labels + assets → revenues
df_la = labels_df.merge(assets_df[['rcept_no', 'date', 'asset_value']], on='rcept_no', how='inner')
df_final = df_la.merge(revenues_df[['rcept_no', 'date', 'revenue_value']], on=['rcept_no', 'date'], how='inner')

# 컬럼 정리
df_final = df_final[['rcept_no', 'label_text', 'date', 'asset_value', 'revenue_value']]
df_final = df_final.sort_values(['rcept_no', 'date']).reset_index(drop=True)

# 종목코드 추출 및 시계열 인덱스 생성
df_final['stock_code'] = df_final['label_text'].apply(lambda x: x.split()[0] if isinstance(x, str) else "Unknown")
df_final['time_idx'] = df_final.groupby('rcept_no')['date'].rank(method='dense').astype(int) - 1

# 타겟 변수 생성: 다음 시점의 revenue가 현재보다 크면 1, 아니면 0
df_final['target'] = (df_final.groupby('rcept_no')['revenue_value'].shift(-1) > df_final['revenue_value']).astype(float)
df_final = df_final.dropna(subset=['target']).reset_index(drop=True)

# ==============================
# 4. 데이터셋 필터링 및 분할
# ==============================

# 최소 시계열 길이 필터링
max_encoder_length = 1
max_prediction_length = 1
min_required_length = max_encoder_length + max_prediction_length

valid_rcept_nos = df_final.groupby('rcept_no')['time_idx'].nunique()
valid_rcept_nos = valid_rcept_nos[valid_rcept_nos >= min_required_length].index
df_final = df_final[df_final['rcept_no'].isin(valid_rcept_nos)].reset_index(drop=True)

# train/val 분리
max_time_idx = df_final['time_idx'].max()
train_cutoff = max_time_idx - max_prediction_length
train_df = df_final[df_final['time_idx'] <= train_cutoff].reset_index(drop=True)
val_df = df_final[df_final['time_idx'] > train_cutoff].reset_index(drop=True)

# ==============================
# 5. TimeSeriesDataSet 생성
# ==============================

train_dataset = TimeSeriesDataSet(
    train_df,
    time_idx="time_idx",
    target="target",
    group_ids=["rcept_no"],
    max_encoder_length=max_encoder_length,
    max_prediction_length=max_prediction_length,
    time_varying_known_reals=["time_idx"],
    time_varying_unknown_reals=["asset_value", "revenue_value"],
    add_relative_time_idx=True,
    add_target_scales=True,
    add_encoder_length=True,
    allow_missing_timesteps=True,
)

val_dataset = TimeSeriesDataSet.from_dataset(
    train_dataset,
    val_df,
    predict=True,
    stop_randomization=True,
    allow_missing_timesteps=True,
)

train_dataloader = DataLoader(train_dataset, batch_size=64, shuffle=True)
val_dataloader = DataLoader(val_dataset, batch_size=64, shuffle=False)

# ==============================
# 6. TFT 모델 정의 및 학습
# ==============================

logger = TensorBoardLogger("tb_logs", name="tft_experiment")
lr_logger = LearningRateMonitor(logging_interval='step')
early_stop_callback = EarlyStopping(monitor='val_loss', patience=3, verbose=True, mode='min')

tft = TemporalFusionTransformer.from_dataset(
    train_dataset,
    learning_rate=1e-3,
    hidden_size=16,
    attention_head_size=4,
    dropout=0.1,
    loss=CustomBCEWithLogitsLoss(),
    log_interval=10,
    reduce_on_plateau_patience=4,
)

trainer = Trainer(
    max_epochs=30,
    gradient_clip_val=0.1,
    callbacks=[lr_logger, early_stop_callback],
    logger=logger,
    enable_model_summary=True,
    accelerator="auto",
)

trainer.fit(tft, train_dataloaders=train_dataloader, val_dataloaders=val_dataloader)

# ==============================
# 7. 예측 및 평가
# ==============================

raw_predictions, x = tft.predict(val_dataloader, mode="raw", return_x=True)

logits = raw_predictions['prediction'].squeeze().detach().cpu()
probs = torch.sigmoid(logits).numpy()
preds = (probs >= 0.5).astype(int)
true = x['decoder_target'].squeeze().detach().cpu().numpy()

print("\n📊 Classification Report:")
print(classification_report(true, preds))

# Confusion Matrix 시각화
plt.figure(figsize=(6, 5))
sns.heatmap(confusion_matrix(true, preds), annot=True, fmt="d", cmap="Blues")
plt.xlabel("Predicted")
plt.ylabel("True")
plt.title("Confusion Matrix")
plt.tight_layout()
plt.show()
