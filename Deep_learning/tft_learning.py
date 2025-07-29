
import os
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from sqlalchemy import create_engine

import torch
from torch.utils.data import DataLoader

import lightning.pytorch as pl
from lightning.pytorch import Trainer, seed_everything
from lightning.pytorch.callbacks import EarlyStopping, LearningRateMonitor

from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer
from pytorch_forecasting.metrics import CrossEntropy

import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler

# 1. 환경변수 로드 및 DB 연결 설정
load_dotenv()  # .env 파일에서 DB 연결 정보 읽기
DB_USER    = os.getenv("DB_USER")
DB_PASSWORD= os.getenv("DB_PASSWORD")
DB_HOST    = os.getenv("DB_HOST")
DB_PORT    = os.getenv("DB_PORT")
DB_NAME2   = os.getenv("DB_NAME2")
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME2]):
    raise EnvironmentError("DB 환경변수 설정이 누락되었습니다.")
# SQLAlchemy 엔진 생성 (PostgreSQL)
engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME2}"
)

# 유닛(단위) 변환 함수: '백만원', '천원', '억원' 등을 실제 수치로 변환
def convert_unit(value, unit):
    try:
        value = float(value)
    except:
        return np.nan
    mapping = {'백만원':1_000_000, '천원':1_000, '억원':100_000_000}
    return value * mapping.get(unit, 1)

# 2. LightningDataModule 정의: 데이터 로딩→전처리→DataLoader 반환
class FinancialDataModule(pl.LightningDataModule):
    def __init__(self, batch_size=64, max_encoder_length=4, max_prediction_length=1, num_workers=8):
        super().__init__()
        self.batch_size = batch_size
        self.max_encoder_length    = max_encoder_length    # 과거 입력 길이
        self.max_prediction_length = max_prediction_length # 예측 구간 길이
        self.num_workers = num_workers

    def prepare_data(self):
        # 패턴 유지를 위해 빈 함수로 둡니다 (DB 읽기는 setup에서)
        pass

    def setup(self, stage=None):
        # --- 데이터 로딩 ---
        assets   = pd.read_sql("SELECT * FROM assets", engine)   # 자산 정보
        revenues = pd.read_sql("SELECT * FROM revenues", engine) # 매출 정보
        labels   = pd.read_sql("SELECT * FROM labels", engine)   # 라벨(매핑 정보)

        # --- 최신 context(기간) 정보만 남기기 ---
        assets['context_dt']   = pd.to_datetime(assets['context'], format='%Y.%m', errors='coerce')
        revenues['context_dt'] = pd.to_datetime(revenues['context'], format='%Y.%m', errors='coerce')
        assets_recent   = assets.sort_values('context_dt').drop_duplicates('rcept_no', keep='last')
        revenues_recent = revenues.sort_values('context_dt').drop_duplicates('rcept_no', keep='last')

        # --- 테이블 머지: labels + assets_recent + revenues_recent ---
        df = (
            labels[['rcept_no','label_text']]
            .merge(assets_recent[['rcept_no','value','unit','context']], on='rcept_no', how='inner')
            .merge(revenues_recent[['rcept_no','value','unit']], on='rcept_no', how='left', suffixes=('','_rev'))
        )
        df.rename(columns={
            'value':'asset_raw', 'unit':'asset_unit',
            'value_rev':'rev_raw','unit_rev':'rev_unit',
            'context':'period'}, inplace=True)

        # --- 수치 컬럼 생성 (단위 변환 후 결측 0 처리) ---
        df['asset_value']   = df.apply(lambda r: convert_unit(r['asset_raw'], r['asset_unit']), axis=1)
        df['revenue_value'] = df.apply(lambda r: convert_unit(r['rev_raw'], r['rev_unit']), axis=1)
        df[['asset_value','revenue_value']] = df[['asset_value','revenue_value']].fillna(0)
        df['date'] = pd.to_datetime(df['period'], format='%Y.%m', errors='coerce')

        # --- 그룹 식별자(ex: 종목 코드) 추출 ---
        df['stock_code'] = df['label_text'].str.split().str[0].str.replace('"','')

        # --- 시계열 정렬 및 타깃 생성 ---
        df = df.sort_values(['stock_code','date']).reset_index(drop=True)
        df['future_revenue'] = df.groupby('stock_code')['revenue_value'].shift(-1)      # 미래 매출
        df = df.dropna(subset=['future_revenue']).copy()                              # 마지막 행 제거
        df['target']   = (df['future_revenue'] > df['revenue_value']).astype(int)      # 상승(1)/하락(0)
        df['time_idx'] = df.groupby('stock_code').cumcount()                          # 시계열 인덱스
        df = df[df['stock_code'].str.match(r'^[A-Za-z0-9]+$')]

        # --- Train/Val 스플릿 (종목별 80:20 비율 유지) ---
        train_list, val_list = [], []
        for code, group in df.groupby('stock_code'):
            split = int(len(group) * 0.8)
            train_list.append(group.iloc[:split])
            val_list.append(group.iloc[split:])
        self.train_df = pd.concat(train_list).reset_index(drop=True)
        self.val_df   = pd.concat(val_list).reset_index(drop=True)

        # --- 피처 정규화 (종목별) ---
        scaler = StandardScaler()
        for col in ['asset_value','revenue_value']:
            self.train_df[col] = self.train_df.groupby('stock_code')[col] \
                .transform(lambda x: scaler.fit_transform(x.values.reshape(-1,1)).flatten())
            self.val_df[col]   = self.val_df.groupby('stock_code')[col] \
                .transform(lambda x: scaler.transform(x.values.reshape(-1,1)).flatten())

        # --- 클래스 불균형 대응 가중치 계산 ---
        counts  = self.train_df['target'].value_counts().sort_index()
        weights = (1.0 / counts) / (1.0 / counts).sum()
        self.class_weights = torch.tensor(weights.values, dtype=torch.float)

        # --- PyTorch Forecasting용 Dataset 생성 ---
        self.train_dataset = TimeSeriesDataSet(
            self.train_df,
            time_idx='time_idx', target='target', group_ids=['stock_code'],
            max_encoder_length=self.max_encoder_length,
            max_prediction_length=self.max_prediction_length,
            time_varying_known_reals=['time_idx'],
            time_varying_unknown_reals=['asset_value','revenue_value'],
            add_relative_time_idx=True, add_target_scales=False, add_encoder_length=True
        )
        self.val_dataset = TimeSeriesDataSet.from_dataset(
            self.train_dataset, self.val_df, predict=True, stop_randomization=True
        )

    def train_dataloader(self):
        # 학습용 DataLoader 반환
        return self.train_dataset.to_dataloader(
            train=True, batch_size=self.batch_size, num_workers=self.num_workers)

    def val_dataloader(self):
        # 검증용 DataLoader 반환
        return self.val_dataset.to_dataloader(
            train=False, batch_size=self.batch_size, num_workers=self.num_workers)

# 3. 메인 실행부: 시드 고정 → 데이터 준비 → 모델 생성 → 학습 → 예측/평가
if __name__ == '__main__':

    # (1) 재현성을 위해 시드 고정
    seed_everything(42)

    # (2) 데이터모듈 초기화 및 DataLoader 생성
    dm = FinancialDataModule()
    dm.setup()
    train_loader = dm.train_dataloader()
    val_loader   = dm.val_dataloader()

    # (3) TFT 모델 생성: 하이퍼파라미터 포함
    tft = TemporalFusionTransformer.from_dataset(
        dm.train_dataset,
        learning_rate=1e-3, hidden_size=16,
        attention_head_size=4, dropout=0.1,
        loss=CrossEntropy(weight=dm.class_weights)
    )

    # (4) Trainer 설정 및 학습 실행
    trainer = Trainer(
        max_epochs=2, gradient_clip_val=0.1,
        callbacks=[EarlyStopping(monitor='val_loss', patience=5), LearningRateMonitor()],
        enable_model_summary=True
    )
    trainer.fit(tft, train_dataloaders=train_loader, val_dataloaders=val_loader)

    # (5) 예측 및 평가: Predictions 객체에서 로직 및 타깃 추출
    predictions = tft.predict(val_loader, mode='raw', return_x=True)
    raw         = predictions.output            # 모델 로짓 딕셔너리
    x           = predictions.x                 # 입력 배치 딕셔너리

    # (6) 로짓 → 예측 클래스
    logits = raw['prediction']                   # [batch, pred_len, n_classes]
    logits = torch.as_tensor(logits).squeeze(1).cpu()
    preds  = logits.argmax(dim=-1).numpy()

    # (7) 실제 타깃 배열
    targets = x['decoder_target']                # [batch, pred_len]
    targets = (targets.squeeze(1).cpu().numpy().astype(int))

    # (8) 결과 리포트 출력 및 혼동 행렬 시각화
    print("Classification Report:")
    print(classification_report(targets, preds, labels=[0,1], zero_division=0))
    cm = confusion_matrix(targets, preds, labels=[0,1])
    plt.figure(figsize=(6,5))
    sns.heatmap(cm, annot=True, fmt='d', xticklabels=[0,1], yticklabels=[0,1])
    plt.title("Confusion Matrix")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.show()

