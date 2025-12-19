# -*- coding: utf-8 -*-
# phase1_5_repeat_and_select.py
#
# ⭐️ [V17.FinalMetricFix] (최종 선발 기준 수정)
# 1. ⭐️ (수정) [최종 선발 기준] 'CompScore' (BalAcc/Brier/MCC)가 편향 모델에 높은 점수를 주는 맹점 발견.
#    최종 챔피언 선발 기준을 phase1과 동일한 'CustomScore' (BalAcc - |R1 - R0|)로 변경.
# 2. ⭐️ (수정) [튜닝 목표 변경] EarlyStopping의 MONITOR_METRIC_NAME을 'val_custom_score'로 변경.
# 3. ⭐️ (수정) MetricsCallback에 'val_custom_score', 'MCC', 'R0/R1' 등 상세 지표 계산 로직 추가.
# 4. ⭐️ (수정) EarlyStopping의 Patience를 7 -> 15로 늘려 안정화 시간 부여.
# 5. (유지) [누수 차단] phase0 (V25) 호환 (RAW 로드 및 V15 가공 로직)
# 6. (유지) target_offset=1 (타겟 누수 방지)
# 7. (유지) phase1의 'class_weight' (부드러운 가중치)를 동일하게 적용

from __future__ import annotations

# ====== 환경 설정 ======
import os
os.environ['PYTHONHASHSEED'] = '42'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import sys, argparse, json, math, warnings, random, shutil
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
# import argparse # ⭐️ [V15] argparse 임포트 (이미 상단에 있음)

import numpy as np
import pandas as pd
import joblib

from sklearn.preprocessing import RobustScaler
from sklearn.metrics import (
    f1_score, balanced_accuracy_score, average_precision_score, confusion_matrix,
    matthews_corrcoef, brier_score_loss 
)
from sklearn.utils.class_weight import compute_sample_weight, compute_class_weight # ⭐️ [V15] 추가

# ⭐️ [V15.1] 'import tensorflow as tf' 추가
import tensorflow as tf
import tensorflow.keras as K
from tensorflow.keras import layers as KL
from tensorflow.keras import models as KM
from tensorflow.keras import optimizers as KO
from tensorflow.keras import losses as KLoss

warnings.filterwarnings("ignore")

# ====== 사용자 config ======
try:
    from config import FEATURE_COLS, TEMPORAL_COLS, STATIC_COLS
except Exception as e:
    print("오류: config.py에서 FEATURE_COLS/TEMPORAL/STATIC_COLS를 찾을 수 없습니다.", file=sys.stderr)
    raise

SEED = 42
np.random.seed(SEED); random.seed(SEED); tf.random.set_seed(SEED)

BASE_RESULTS_DIR = "experiments_v20_ensemble"
PREPROCESSED_DATA_DIR = "preprocessed_dfs"

# GPU 메모리 증가
try:
    gpus = tf.config.list_physical_devices('GPU')
    for gpu in gpus: tf.config.experimental.set_memory_growth(gpu, True)
    if gpus: print(f"-> {len(gpus)}개 GPU 메모리 증가 설정 완료.")
except Exception as e:
    print(f"-> 경고: GPU 메모리 설정 실패: {e}")

_CURRENT_LOG_FILE = None 

def log(m):
    print(m, flush=True) 
    global _CURRENT_LOG_FILE
    if _CURRENT_LOG_FILE: 
        try:
            _CURRENT_LOG_FILE.write(str(m) + '\n') 
            _CURRENT_LOG_FILE.flush()
        except Exception as e:
            print(f"[Logger Error] Failed to write to log file: {e}", flush=True)

def ensure_dir(p): os.makedirs(p, exist_ok=True)

# ====== 헬퍼 함수들 ======
def _mcc(y_true, y_pred):
    try:
        return float(matthews_corrcoef(y_true, y_pred))
    except Exception:
        return 0.0

def _brier(y_true, y_prob):
    try:
        return float(brier_score_loss(y_true.astype(int), y_prob.astype(float)))
    except Exception:
        return np.nan

def thr_plateau_metrics(y_true, y_prob, best_thr, width=0.02, step=0.005):
    thrs = np.arange(max(0.01, best_thr - width), min(0.99, best_thr + width) + 1e-12, step)
    if len(thrs) == 0: 
        thrs = [best_thr]
    bals, mccs = [], []
    for t in thrs:
        y_hat = (y_prob >= t).astype(int)
        bals.append(balanced_accuracy_score(y_true, y_hat))
        mccs.append(_mcc(y_true, y_hat))
    return float(np.mean(bals)), float(np.std(bals)), float(np.mean(mccs))

def find_best_threshold_balacc_simple(y_true, y_prob, steps=200) -> Tuple[float, float]:
    if len(y_true) == 0 or len(np.unique(y_true)) < 2:
        return 0.5, 0.5 
    best_thr = 0.5
    best_balacc = 0.5 
    for thr in np.linspace(0.01, 0.99, steps):
        y_hat = (y_prob >= thr).astype(int)
        balacc = balanced_accuracy_score(y_true, y_hat)
        if balacc > best_balacc:
            best_balacc = balacc
            best_thr = thr
    return float(best_thr), float(best_balacc)

# =============================================================================
# ⭐️ [V15] phase1(V14)에서 헬퍼 함수 이동 (누수 없는 가공용)
# =============================================================================
def calculate_indicators(df_group):
    """(phase1에서 이동) 그룹별(종목별)로 호출되어야 함"""
    df = df_group.copy() 
    for col in ['open_pric', 'high_pric', 'low_pric', 'close_pric']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df[['open_pric', 'high_pric', 'low_pric', 'close_pric']] = df[['open_pric', 'high_pric', 'low_pric', 'close_pric']].ffill()
    close = df['close_pric']
    if close.isnull().all() or len(close) == 0: 
        return df

    df['sma_20'] = close.rolling(window=20, min_periods=1).mean()
    std_20 = close.rolling(window=20, min_periods=1).std()
    
    df['BBM_20_2_0'] = df['sma_20']; df['BBU_20_2_0'] = df['sma_20'] + (std_20 * 2); df['BBL_20_2_0'] = df['sma_20'] - (std_20 * 2)

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    df['MACD_12_26_9'] = ema_12 - ema_26
    df['MACDs_12_26_9'] = df['MACD_12_26_9'].ewm(span=9, adjust=False).mean()
    df['MACDh_12_26_9'] = df['MACD_12_26_9'] - df['MACDs_12_26_9']

    delta = close.diff(1)
    gain = delta.where(delta > 0, 0).fillna(0)
    loss = -delta.where(delta < 0, 0).fillna(0)
    avg_gain = gain.ewm(com=14 - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=14 - 1, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    df['rsi_14'] = 100 - (100 / (1 + rs))

    indicator_cols = ['sma_20', 'BBM_20_2_0', 'BBU_20_2_0', 'BBL_20_2_0', 'MACD_12_26_9', 'MACDs_12_26_9', 'MACDh_12_26_9', 'rsi_14']
    
    df[indicator_cols] = df[indicator_cols].replace([np.inf, -np.inf], np.nan)
    df[indicator_cols] = df[indicator_cols].ffill()
    return df

def calculate_yoy(df_split):
    """(phase1에서 이동) 분할된 df(train/val/test)별로 호출되어야 함"""
    df = df_split.copy()
    for col in ['sales', 'operating_income']:
        if col in df.columns:
            df[f'{col}_prev'] = df.groupby('stock_code')[col].shift(4)
            df[f'{col}_yoy'] = np.where(
                (df[f'{col}_prev'].isnull()) | (df[f'{col}_prev'] == 0),
                np.nan,
                ((df[col] - df[f'{col}_prev']) / df[f'{col}_prev']) * 100
            )
            df[f'{col}_yoy'] = df[f'{col}_yoy'].replace([np.inf, -np.inf], np.nan)
            df.drop(columns=[f'{col}_prev'], inplace=True, errors='ignore')
        else:
            df[f'{col}_yoy'] = np.nan
    return df

def ensure_features(df, feature_cols):
    """(phase1에서 이동) 분할된 df에 피처 컬럼 보장"""
    missing = [c for c in feature_cols if c not in df.columns]
    for c in missing: 
        df[c] = np.nan
    if missing:
        log(f"   -> ⭐️ [V15] 누락 피처 {len(missing)}개를 NaN으로 생성.")
    return df
# =============================================================================


# =============================================================================
# ⭐️ [V15] 데이터 로딩/가드 (수정: _raw.pkl 로드)
# =============================================================================
@dataclass
class Splits:
    train_df: pd.DataFrame
    val_df: pd.DataFrame
    test_df: pd.DataFrame
    # ⭐️ [V15] 스케일러는 main에서 생성/전달
    # scaler: RobustScaler 

FORBIDDEN_TARGET_LIKE = {
    'direction','label','labels','target','targets','y',
    'predict_target_date','target_date','future_return','ret_next'
}
def _group_key(df: pd.DataFrame) -> str:
    if 'stock_code' in df.columns: return 'stock_code'
    if 'ticker' in df.columns: return 'ticker'
    raise ValueError("stock_code/ticker 컬럼이 필요합니다.")
def guard_feature_list():
    lower_cols = [c.lower() for c in TEMPORAL_COLS]
    bad = [c for c in lower_cols if c in FORBIDDEN_TARGET_LIKE]
    if bad:
        raise ValueError(f"[가드레일] TEMPORAL_COLS에 라벨/미래지표 포함: {bad}")
        
def load_phase0(data_dir: str) -> Splits:
    log(f"✅ [1/8] Phase0 *RAW* 산출물 로딩: {data_dir}")
    try:
        # ⭐️ [V15] _raw.pkl 로드
        tr = pd.read_pickle(os.path.join(data_dir, "train_df_raw.pkl"))
        va = pd.read_pickle(os.path.join(data_dir, "val_df_raw.pkl"))
        te = pd.read_pickle(os.path.join(data_dir, "test_df_raw.pkl"))
        # ⭐️ [V15] 스케일러 로드 삭제 (main에서 생성)
        # scaler = joblib.load(os.path.join(data_dir, "final_scaler.pkl"))
    except FileNotFoundError as e:
        log(f"-> 로딩 실패: {e}"); 
        log("-> ⭐️ [V15] phase0 (V25 수정본)을 먼저 실행하여 _raw.pkl 파일을 생성해야 합니다.")
        sys.exit(1)
        
    for name, df in [("RAW/Train", tr), ("RAW/Val", va), ("RAW/Test", te)]:
        if len(df)==0: log(f"{name}: EMPTY")
        else: log(f"{name}: {df['date'].min().date()} ~ {df['date'].max().date()} rows={len(df):,} pos_rate={df['direction'].mean():.3f}")
    guard_feature_list()
    # ⭐️ [V15] scaler 반환 삭제
    return Splits(tr, va, te) 

# =============================================================================
# ⭐️ [V15] 시퀀스 생성 (수정: target_offset=1)
# =============================================================================
def create_sequences_train_only(df: pd.DataFrame, max_seq_len: int, temporal_cols: List[str],
                                target_col="direction", target_offset=1): # ⭐️ [V15] offset=1
    X, y, y_prev = [], [], []
    gk = _group_key(df)
    for _, g in df.groupby(gk):
        g = g.sort_values("date")
        temp = g[temporal_cols].values
        tgt = g[target_col].astype(int).values
        if len(temp) <= max_seq_len + max(0, target_offset): continue
        t_min = max_seq_len - 1
        t_max = len(temp) - 1 - max(0, target_offset)
        for t in range(t_min, t_max):
            X.append(temp[t-(max_seq_len-1): t+1])
            y.append(tgt[t + target_offset])
            pi = t + target_offset - 1 # ⭐️ (t+1)의 직전은 (t)
            y_prev.append(tgt[pi] if pi >= 0 else 0)
    return np.asarray(X, np.float32), np.asarray(y, np.int32), np.asarray(y_prev, np.int32)

def create_sequences_val_with_history(train_df: pd.DataFrame, val_df: pd.DataFrame, max_seq_len: int,
                                      temporal_cols: List[str], target_col="direction",
                                      target_offset=1, embargo_days=0): # ⭐️ [V15] offset=1
    X, y, y_prev = [], [], []
    gk = _group_key(val_df if len(val_df)>0 else train_df)
    hist = pd.concat([train_df.copy(), val_df.copy()], ignore_index=True).sort_values([gk, "date"])
    for code, g_hist in hist.groupby(gk):
        g_hist = g_hist.sort_values("date")
        g_val = val_df[val_df[gk]==code].sort_values("date")
        if g_val.empty: continue
        # ⭐️ [V15] phase0에서 embargo가 이미 처리되었으므로, 이중 embargo 로직 삭제
        
        temp = g_hist[temporal_cols].values
        tgt_dates = pd.to_datetime(g_hist["date"]).values
        tgt_vals  = g_hist[target_col].astype(int).values
        val_dates = set(pd.to_datetime(g_val["date"]).values)
        
        for t in range(len(g_hist)):
            tt = t + target_offset # ⭐️ [V15] (t+1)
            if tt >= len(g_hist): break
            if tgt_dates[tt] not in val_dates: continue
            
            start = t - (max_seq_len - 1)
            if start < 0: continue
            
            X.append(temp[start:t+1]) # ⭐️ X: [t-N+1, t]
            y.append(int(tgt_vals[tt])) # ⭐️ y: [t+1]
            
            pi = tt - 1 # ⭐️ (t+1)의 직전은 (t)
            y_prev.append(int(tgt_vals[pi]) if pi >= 0 else 0)
            
    return np.asarray(X, np.float32), np.asarray(y, np.int32), np.asarray(y_prev, np.int32)

_MAXSEQ_CACHE: Dict[tuple, tuple] = {}
def make_arrays_max(splits: Splits, max_seq_len: int, target_offset: int, embargo_days: int):
    # ⭐️ [V15] splits 객체에 scaler가 없으므로 key에서 제거
    key = (id(splits.train_df), id(splits.val_df), max_seq_len, target_offset, embargo_days)
    if key in _MAXSEQ_CACHE: return _MAXSEQ_CACHE[key]
    
    log(f"✅ [V15] MAX_SEQ_LEN={max_seq_len} 생성 (Val=history+Val-라벨, embargo={embargo_days}d, offset={target_offset})")
    
    # ⭐️ [V15] 가공된 df로 시퀀스 생성
    Xtr_max, ytr, ytr_prev = create_sequences_train_only(splits.train_df, max_seq_len, TEMPORAL_COLS, target_col="direction", target_offset=target_offset)
    Xva_max, yva, yva_prev = create_sequences_val_with_history(splits.train_df, splits.val_df, max_seq_len, TEMPORAL_COLS, target_col="direction", target_offset=target_offset, embargo_days=embargo_days)
    
    log(f"-> Train(MAX) shape={Xtr_max.shape}, Val(MAX) shape={Xva_max.shape}")
    def _r(y): return f"{np.mean(y):.4f} (pos={int(np.sum(y)):,}/{len(y):,})" if len(y)>0 else "N/A"
    log(f"   - Train y pos_rate={_r(ytr)} | Val y pos_rate={_r(yva)}")
    log(f"   - Val naive_prev pos_rate={_r(yva_prev)} (오프셋 기준 직전 라벨)")
    
    _MAXSEQ_CACHE[key] = (Xtr_max, ytr, ytr_prev, Xva_max, yva, yva_prev)
    return _MAXSEQ_CACHE[key]
# =============================================================================


# ====== 모델 빌드 (수정 없음) ======
def head_classify(x, p):
    x = KL.Dropout(p.get("dropout_rate",0.3))(x)
    for _ in range(p.get("dense_layers",1)):
        x = KL.Dense(p.get("dense_units",128), activation=p.get("activation","relu"))(x)
        x = KL.Dropout(p.get("dropout_rate",0.3))(x)
    return KL.Dense(1, activation="sigmoid", name="direction_output", dtype="float32")(x) 
def build_lstm(input_shape, p):
    inp = KL.Input(shape=input_shape); x = inp
    for i in range(p.get("lstm_n_layers",2)): x = KL.LSTM(p.get("lstm_units",128), return_sequences=(i<p.get("lstm_n_layers",2)-1))(x)
    out = head_classify(x,p); return KM.Model(inp, out, name="LSTM")
def build_bilstm(input_shape, p):
    inp = KL.Input(shape=input_shape); x = inp
    for i in range(p.get("bilstm_n_layers",2)): x = KL.Bidirectional(KL.LSTM(p.get("bilstm_units",128), return_sequences=(i<p.get("bilstm_n_layers",2)-1)))(x)
    out = head_classify(x,p); return KM.Model(inp,out,name="BiLSTM")
def build_gru(input_shape, p):
    inp = KL.Input(shape=input_shape); x = inp
    for i in range(p.get("gru_n_layers",2)): x = KL.GRU(p.get("gru_units",128), return_sequences=(i<p.get("gru_n_layers",2)-1))(x)
    out = head_classify(x,p); return KM.Model(inp,out,name="GRU")
def build_cnnlstm(input_shape, p):
    inp = KL.Input(shape=input_shape)
    x = KL.Conv1D(p.get("cnn_filters",64), p.get("cnn_kernel_size",3), padding="same", activation="relu")(inp)
    x = KL.MaxPooling1D()(x) 
    for i in range(p.get("n_layers",1)): x = KL.LSTM(p.get("lstm_units",128), return_sequences=(i<p.get("n_layers",1)-1))(x)
    out = head_classify(x,p); return KM.Model(inp,out,name="CNNLSTM")
def build_tcn(input_shape, p):
    def block(nf, ks, dr, inp):
        y = KL.Conv1D(nf, ks, padding='causal', dilation_rate=dr, kernel_initializer='he_normal')(inp)
        y = KL.BatchNormalization()(y); y = KL.Activation('relu')(y); y = KL.Dropout(0.3)(y)
        y = KL.Conv1D(nf, ks, padding='causal', dilation_rate=dr, kernel_initializer='he_normal')(y)
        y = KL.BatchNormalization()(y); y = KL.Activation('relu')(y); y = KL.Dropout(0.3)(y)
        sc = KL.Conv1D(nf, 1, padding='same')(inp) if inp.shape[-1]!=nf else inp
        y = KL.Add()([sc,y]); y = KL.Activation('relu')(y); return y
    inp = KL.Input(shape=input_shape); x = KL.Conv1D(p.get("tcn_filters",64), 1, padding='same')(inp)
    for i in range(p.get("tcn_n_blocks",2)): x = block(p.get("tcn_filters",64), p.get("tcn_kernel_size",3), p.get("tcn_dilation_base",2)**i, x)
    x = KL.GlobalAveragePooling1D()(x)
    out = head_classify(x,p); return KM.Model(inp,out,name="TCN")
@tf.keras.utils.register_keras_serializable()
class PositionalEncoding(KL.Layer):
    def __init__(self, position, d_model, **kwargs):
        super(PositionalEncoding, self).__init__(**kwargs); self.position = position; self.d_model = d_model
        pos_encoding = self.build_encoding(position, d_model); self.pos_encoding = tf.cast(pos_encoding, dtype=tf.float32)
    def build_encoding(self, position, d_model):
        angle_rads = self.get_angles(np.arange(position)[:, np.newaxis], np.arange(d_model)[np.newaxis, :], d_model)
        angle_rads[:, 0::2] = np.sin(angle_rads[:, 0::2]); angle_rads[:, 1::2] = np.cos(angle_rads[:, 1::2])
        pos_encoding = angle_rads[np.newaxis, ...]; return pos_encoding
    def get_angles(self, pos, i, d_model):
        angle_rates = 1 / np.power(10000, (2 * (i // 2)) / np.float32(d_model)); return pos * angle_rates
    def call(self, inputs):
        seq_len = tf.shape(inputs)[1]
        return inputs + tf.cast(self.pos_encoding[:, :seq_len, :], dtype=inputs.dtype) 
    def get_config(self):
        config = super(PositionalEncoding, self).get_config(); config.update({ "position": self.position, "d_model": self.d_model }); return config
def build_transformer(input_shape, p):
    seq_len, d_in = input_shape; d_model = int(p.get("d_model",128)); heads = int(p.get("num_heads",4)); dff = int(p.get("dff", d_model*2)); dr = float(p.get("dropout_rate",0.3))
    inp = KL.Input(shape=input_shape); x = KL.Dense(d_model, name="proj_to_dmodel")(inp); max_seq_len_for_pe = 512
    x = PositionalEncoding(position=max_seq_len_for_pe, d_model=d_model)(x); x = KL.Dropout(dr, name="drop_in")(x)
    n_layers = int(p.get("transformer_n_blocks", 2))
    for i in range(n_layers):
        attn = KL.MultiHeadAttention(num_heads=heads, key_dim=max(1, d_model // heads), dropout=dr, name=f"mha_{i}")(x, x)
        x = KL.Add(name=f"skip_attn_{i}")([x, attn]); x = KL.LayerNormalization(epsilon=1e-6, name=f"ln_attn_{i}")(x)
        f = KL.Dense(dff, activation="gelu", name=f"ff_{i}_1")(x); f = KL.Dropout(dr, name=f"drop_ff_{i}")(f); f = KL.Dense(d_model, name=f"ff_{i}_2")(f)
        x = KL.Add(name=f"skip_ff_{i}")([x, f]); x = KL.LayerNormalization(epsilon=1e-6, name=f"ln_ff_{i}")(x)
    x = KL.GlobalAveragePooling1D(name="gap")(x); out = head_classify(x, p); return KM.Model(inp, out, name="Transformer")
def build_model_by_arch(arch: str, input_shape, params: Dict):
    if arch=='lstm': return build_lstm(input_shape, params)
    if arch=='bilstm': return build_bilstm(input_shape, params)
    if arch=='gru': return build_gru(input_shape, params)
    if arch=='cnnlstm': return build_cnnlstm(input_shape, params)
    if arch=='tcn': return build_tcn(input_shape, params)
    if arch=='transformer': return build_transformer(input_shape, params)
    raise ValueError(f"Unknown arch: {arch}")
def compile_model(model, lr: float):
    model.compile(optimizer=KO.Adam(learning_rate=lr), loss=KLoss.BinaryCrossentropy(), metrics=[K.metrics.AUC(name="auc"), K.metrics.Precision(name="precision"), K.metrics.Recall(name="recall")])
    return model
# =============================================================================


# ====== ⭐️ [V16] 콜백 (수정: CustomScore) ======
class MetricsCallback(K.callbacks.Callback):
    def __init__(self, X_val, y_val, batch_size=1024, thresh=0.5, monitor_metric="val_custom_score"): # ⭐️ V16: 기본값 변경
        super().__init__(); self.X_val = X_val; self.y_val = y_val.astype(int); self.bs = batch_size
        self.th_0p5 = float(thresh); self.monitor_metric = monitor_metric
        
        # ⭐️ [V16] CustomScore는 -1이 최악
        self.best_score = -1.0 
        self.best_epoch = -1
        
    def on_train_begin(self, logs=None): 
        self.best_score = -1.0
        self.best_epoch = -1
        
    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        if self.X_val is None or len(self.X_val) == 0:
            logs["val_balanced_acc_0p5"] = 0.0; logs["val_mcc_0p5"] = -1.0; logs["val_custom_score"] = -1.0; 
            logs["val_recall0_0p5"] = 0.0; logs["val_recall1_0p5"] = 0.0; logs["val_pred_pos_rate"] = 0.0;
            logs["val_best_monitored_score"] = self.best_score; return

        p = self.model.predict(self.X_val, verbose=0, batch_size=self.bs).ravel()
        yhat_0p5 = (p >= self.th_0p5).astype(int)
        
        try: 
            tn, fp, fn, tp = confusion_matrix(self.y_val, yhat_0p5, labels=[0,1]).ravel()
        except ValueError:
            if np.all(yhat_0p5 == 0): tn, fp, fn, tp = len(self.y_val)-np.sum(self.y_val), 0, np.sum(self.y_val), 0
            elif np.all(yhat_0p5 == 1): tn, fp, fn, tp = 0, len(self.y_val)-np.sum(self.y_val), 0, np.sum(self.y_val)
            else: tn, fp, fn, tp = 0, 0, 0, 0
            
        rec0_0p5 = tn/(tn+fp) if (tn+fp)>0 else 0.0 # 하락(0) 재현율
        rec1_0p5 = tp/(tp+fn) if (tp+fn)>0 else 0.0 # 상승(1) 재현율
        balacc_0p5 = 0.5 * (rec0_0p5 + rec1_0p5)
        
        mcc_0p5 = _mcc(self.y_val, yhat_0p5)
        
        total_samples = tn + fp + fn + tp
        pred_pos_rate_0p5 = (tp + fp) / total_samples if total_samples > 0 else 0.0
        
        # ⭐️ [V16] 커스텀 스코어 (균형 페널티) 계산
        balance_penalty = abs(rec1_0p5 - rec0_0p5)
        custom_score = balacc_0p5 - balance_penalty
        
        try: pr_auc = average_precision_score(self.y_val, p)
        except Exception: pr_auc = np.nan
        
        logs["val_balanced_acc_0p5"] = float(balacc_0p5)
        logs["val_mcc_0p5"] = float(mcc_0p5) 
        logs["val_recall0_0p5"] = float(rec0_0p5) 
        logs["val_recall1_0p5"] = float(rec1_0p5) 
        logs["val_pred_pos_rate"] = float(pred_pos_rate_0p5)
        logs["val_custom_score"] = float(custom_score) # ⭐️ 로그에 추가
        
        f1pos_0p5 = f1_score(self.y_val, yhat_0p5, pos_label=1, zero_division=0)
        logs["val_f1_pos_0p5"] = float(f1pos_0p5)
        logs["val_prauc_pos"] = float(pr_auc) if not np.isnan(pr_auc) else -1.0
        
        # ⭐️ [V16] 튜닝 목표(monitor_metric)에 따라 current_score 할당
        if self.monitor_metric == 'val_custom_score':
            current_score = custom_score
        elif self.monitor_metric == 'val_prauc_pos':
            current_score = pr_auc if not np.isnan(pr_auc) else -1.0
        else: # 기본값: val_balanced_acc_0p5
            current_score = balacc_0p5
        
        if current_score >= self.best_score: 
            self.best_score = current_score; self.best_epoch = epoch + 1
            
        logs["val_best_monitored_score"] = self.best_score
        
        # ⭐️ [V16] 로그 수정
        print(f"[Epoch {epoch+1}] CustomScore={custom_score:.4f}, BalAcc@0.5={balacc_0p5:.4f}, MCC@0.5={mcc_0p5:.4f} | R0={rec0_0p5:.4f}, R1={rec1_0p5:.4f} | PredPos%={pred_pos_rate_0p5:.4f}")
        print(f"[Epoch {epoch+1}] (ES Best {self.monitor_metric}={self.best_score:.4f} at Ep {self.best_epoch})")


# ====== 유틸: 베이스라인 & 누수 검정 (수정 없음) ======
def evaluate_baselines(y_true: np.ndarray, y_prev: np.ndarray, y_prob: np.ndarray, best_thr: float, note: str):
    y_pred_thr = (y_prob >= best_thr).astype(int)
    y_pred_prev = y_prev.astype(int)
    def rep(title, yt, yp, prob=None):
        bal = balanced_accuracy_score(yt, yp)
        f1p = f1_score(yt, yp, average='binary', pos_label=1)
        pr  = average_precision_score(yt, prob) if prob is not None else np.nan
        log(f"[{note}] {title}: BalAcc={bal:.4f}, F1pos={f1p:.4f}, PR-AUC={pr:.4f}")
    y_pred_0p5 = (y_prob >= 0.5).astype(int)
    rep(f"Model@0.500", y_true, y_pred_0p5, y_prob) 
    rep(f"Model@{best_thr:.3f}", y_true, y_pred_thr, None) 
    rep("NaivePrev", y_true, y_pred_prev, None)
    
def leakage_sentry(model, X_val, y_val, batch_size=1024, name="LeakageSentry"):
    rng = np.random.default_rng(SEED+999); y_shuf = rng.permutation(y_val)
    prob = model.predict(X_val, batch_size=batch_size, verbose=0).ravel()
    pr = average_precision_score(y_shuf, prob); bal = balanced_accuracy_score(y_shuf, (prob>=0.5).astype(int))
    log(f"[{name}] ShuffledLabels: BalAcc={bal:.4f}, PR-AUC={pr:.4f} (≈0.5 기대)")

# ====== ⭐️ [V16] 반복학습 루틴 (수정: CustomScore 모니터링) ======
def run_once(seed: int, arch: str, params: Dict, Xtr_max, ytr, Xva_max, yva,
             yva_prev, max_seq_len: int, imbalance_mode: str): # ⭐️ [V15] imbalance_mode 추가
    # 시드 고정
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed); random.seed(seed); tf.random.set_seed(seed)
    log(f"   -> Run Seed 고정: {seed}")

    seq_len = int(params.get("seq_length", max_seq_len))
    if seq_len > Xtr_max.shape[1]:
        raise ValueError(f"seq_length({seq_len}) > MAX({Xtr_max.shape[1]})")

    Xtr = Xtr_max[:, -seq_len:, :]; Xva = Xva_max[:, -seq_len:, :]
    
    # ⭐️ [V15] 가중치 로직 (phase1과 동일)
    sample_weights = None; class_weights_dict = None
    if imbalance_mode == "sample_weight":
        try:
            y_int = ytr.astype(int)
            if len(np.unique(y_int)) > 1:
                sample_weights = compute_sample_weight(class_weight='balanced', y=y_int).astype(np.float32)
                log("   -> 'balanced' (강한) 샘플 가중치 (훈련셋) 적용 완료.")
        except Exception as e: log(f"   -> 'balanced' 샘플 가중치 계산 실패({e}), 가중치 미적용.")
    
    elif imbalance_mode == "class_weight": 
        try:
            y_int = ytr.astype(int)
            if len(np.unique(y_int)) > 1:
                classes = np.unique(y_int)
                cw_raw = compute_class_weight(class_weight='balanced', classes=classes, y=y_int)
                # ⭐️ "아주 부드러운 가중치" (75% 완화)
                cw_damped = [(w * 0.25 + 0.75) for w in cw_raw]
                class_weights_dict = dict(zip(classes, cw_damped))
                log(f"   -> ⭐️ '아주 부드러운 가중치' (75% Damped) 적용 완료: {class_weights_dict}")
            else:
                log("   -> 클래스 가중치 미적용 (훈련셋 클래스 1개)")
        except Exception as e:
            log(f"   -> '아주 부드러운 가중치' 계산 실패({e}), 가중치 미적용.")

    model = build_model_by_arch(arch, (seq_len, Xtr.shape[-1]), params)
    model = compile_model(model, params.get("learning_rate", 1e-3))

    # ⭐️ [V16] 1.5의 목표를 phase1과 동일한 "val_custom_score"로 변경
    MONITOR_METRIC_NAME = "val_custom_score"; MONITOR_METRIC_MODE = "max"
    
    cb = MetricsCallback(X_val=Xva, y_val=yva, batch_size=params.get("batch_size", 64), thresh=0.5, monitor_metric=MONITOR_METRIC_NAME)
    callbacks = [
        cb,
        # ⭐️ [V16] EarlyStopping도 "val_custom_score" 모니터링, Patience=15
        K.callbacks.EarlyStopping(monitor=MONITOR_METRIC_NAME, mode=MONITOR_METRIC_MODE, patience=15, restore_best_weights=True, verbose=1),
        K.callbacks.ReduceLROnPlateau(monitor="val_loss", mode="min", factor=0.5, patience=5, min_lr=1e-6, verbose=1),
    ]
    bs = int(params.get("batch_size", 64))
    history = model.fit(Xtr, ytr, validation_data=(Xva, yva), epochs=100, batch_size=bs, verbose=1, 
                        callbacks=callbacks, sample_weight=sample_weights, class_weight=class_weights_dict) # ⭐️ 가중치 전달

    log(f"   -> ⭐️ Best Epoch {cb.best_epoch} ({MONITOR_METRIC_NAME} 기준) 모델로 '고정 0.5 임계값' 및 '최적 임계값' 동시 평가...")
    prob = model.predict(Xva, verbose=0, batch_size=bs).ravel()
    
    log("   -> ⭐️ 고정 0.5 임계값 상세 평가...")
    yhat_0p5 = (prob >= 0.5).astype(int)
    tn_0p5, fp_0p5, fn_0p5, tp_0p5 = 0, 0, 0, 0
    
    # ⭐️ [V16] 모든 지표 계산 (CompScore 및 CustomScore용)
    try: 
        tn_0p5, fp_0p5, fn_0p5, tp_0p5 = confusion_matrix(yva, yhat_0p5, labels=[0,1]).ravel()
        rec0_0p5 = tn_0p5 / (tn_0p5 + fp_0p5) if (tn_0p5 + fp_0p5) > 0 else 0.0
        rec1_0p5 = tp_0p5 / (tp_0p5 + fn_0p5) if (tp_0p5 + fn_0p5) > 0 else 0.0
        balacc_0p5 = 0.5 * (rec0_0p5 + rec1_0p5)
        mcc_0p5 = _mcc(yva, yhat_0p5)
        pred_pos_rate_0p5 = float(yhat_0p5.mean())
        
        # ⭐️ [V16] CustomScore 계산
        balance_penalty = abs(rec1_0p5 - rec0_0p5)
        custom_score_0p5 = balacc_0p5 - balance_penalty
        
        log(f"   -> ⭐️ @0.5: CustomScore={custom_score_0p5:.4f}, BalAcc={balacc_0p5:.4f}, MCC={mcc_0p5:.4f}, R0={rec0_0p5:.4f}, R1={rec1_0p5:.4f}, PredPos%={pred_pos_rate_0p5:.4f}")
    except ValueError:
        log("   -> ⚠️ 고정 0.5 임계값 CM 계산 오류 (한 클래스만 예측)")
        rec0_0p5, rec1_0p5, balacc_0p5, mcc_0p5, pred_pos_rate_0p5, custom_score_0p5 = 0.0, 0.0, 0.5, 0.0, float(yhat_0p5.mean()), -1.0

    best_thr, best_balacc = find_best_threshold_balacc_simple(yva, prob, steps=200)
    log(f"   -> ⭐️ 최적 임계값 탐색 완료 (참고용): thr={best_thr:.4f} (BalAcc={best_balacc:.4f})")
    yhat_best = (prob >= best_thr).astype(int)
    tn_best, fp_best, fn_best, tp_best = 0, 0, 0, 0
    try: tn_best, fp_best, fn_best, tp_best = confusion_matrix(yva, yhat_best, labels=[0,1]).ravel()
    except ValueError: log("-> ⚠️ 최적 임계값 기준 CM 계산 오류 (한 클래스만 예측)")
    rec0_best = tn_best/(tn_best+fp_best) if (tn_best+fp_best)>0 else 0.0
    rec1_best = tp_best/(tp_best+fn_best) if (tp_best+fn_best)>0 else 0.0
    f1p_best = f1_score(yva, yhat_best, average='binary', pos_label=1)
    
    prauc = average_precision_score(yva, prob)
    brier = _brier(yva, prob)
    plateau_mean, plateau_std, plateau_mcc_mean = thr_plateau_metrics(yva, prob, best_thr)
    log(f"   -> ⭐️ 신뢰도/견고성: Brier={brier:.4f}, Plateau_BalAcc_Mean={plateau_mean:.4f} (Std={plateau_std:.4f}), Plateau_MCC_Mean={plateau_mcc_mean:.4f}")

    evaluate_baselines(y_true=yva, y_prev=yva_prev, y_prob=prob, best_thr=best_thr, note=f"{arch.upper()} Run(seed={seed}) VAL")
    leakage_sentry(model, Xva, yva, batch_size=bs, name=f"{arch.upper()} Run(seed={seed}) LeakageSentry")

    run_dir = os.path.join(BASE_RESULTS_DIR, f"v20_{arch}_classify_only", "phase1_5_runs")
    ensure_dir(run_dir)
    temp_path = os.path.join(run_dir, f"run_seed{seed}_seq{seq_len}.keras")
    try: model.save(temp_path)
    except Exception as e: log(f"-> 경고: 모델 저장 실패: {e}")
    del model, history, Xtr, Xva
    tf.keras.backend.clear_session()

    return {
        "seed": seed,
        "seq_length": seq_len,
        "saved_model": temp_path, 
        "best_epoch": cb.best_epoch,
        "prauc": float(prauc),
        "brier": float(brier),
        "balacc_0p5": float(balacc_0p5),
        "custom_score_0p5": float(custom_score_0p5), # ⭐️ [V17] 추가
        "recall0_0p5": float(rec0_0p5),
        "recall1_0p5": float(rec1_0p5),
        "mcc_0p5": float(mcc_0p5),
        "pred_pos_rate_0p5": float(pred_pos_rate_0p5),
        "balacc_best": float(best_balacc),
        "best_threshold": float(best_thr),
        "recall0_best": float(rec0_best),
        "recall1_best": float(rec1_best),
        "f1_pos_best": float(f1p_best),
        "pred_pos_rate_best": float(yhat_best.mean()),
        "thr_plateau_mean": float(plateau_mean),
        "thr_plateau_std": float(plateau_std),
        "thr_plateau_mcc_mean": float(plateau_mcc_mean),
    }

# =================================================================
# ⭐️ [V17] main (수정: CustomScore로 챔피언 선발)
# =================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results_dir", type=str, default=BASE_RESULTS_DIR)
    ap.add_argument("--data_dir", type=str, default=PREPROCESSED_DATA_DIR)
    ap.add_argument("--arches", nargs="*", default=["lstm","bilstm","gru","cnnlstm","tcn","transformer"])
    ap.add_argument("--n_runs", type=int, default=15)
    ap.add_argument("--seed", type=int, default=None, help="[신규] 특정 시드를 지정하여 단일 실행(복구) (n_runs 무시)")
    ap.add_argument("--max_seq_length", type=int, default=240)
    ap.add_argument("--target_offset", type=int, default=1) # ⭐️ [V15] 1로 고정 (phase1과 동일)
    ap.add_argument("--embargo_days", type=int, default=5)
    ap.add_argument("--top_k_save", type=int, default=3, help="[수정] Phase 2로 전달할 Top-K 챔피언 수 (모두 저장)")
    
    # ⭐️ [V15] phase1과 동일한 가중치 옵션 추가
    ap.add_argument("--imbalance_mode", type=str, choices=["none", "sample_weight", "class_weight"], default="none")
    
    args = ap.parse_args()

    # 1. ⭐️ [V15] RAW 데이터 로드
    splits_raw = load_phase0(args.data_dir)
    train_df_raw = splits_raw.train_df
    val_df_raw = splits_raw.val_df

    # 2. ⭐️ [V15] 누수 없는 가공 파이프라인 (phase1과 동일)
    log("\n✅ [V15.LeakFix] 'Train' Set 독립 가공 시작...")
    train_df_processed = train_df_raw.groupby('stock_code', group_keys=False).apply(calculate_indicators)
    train_df_processed = calculate_yoy(train_df_processed)
    train_df_processed = ensure_features(train_df_processed, FEATURE_COLS)
    train_df_processed[FEATURE_COLS] = train_df_processed.groupby('stock_code')[FEATURE_COLS].ffill()
    train_df_processed[FEATURE_COLS] = train_df_processed[FEATURE_COLS].fillna(0)
    log("-> 'Train' Set 가공 완료.")

    log("\n✅ [V15.LeakFix] 'Val' Set 독립 가공 시작 (롤링 누수 방지)...")
    val_df_processed = val_df_raw.groupby('stock_code', group_keys=False).apply(calculate_indicators)
    val_df_processed = calculate_yoy(val_df_processed)
    val_df_processed = ensure_features(val_df_processed, FEATURE_COLS)
    val_df_processed[FEATURE_COLS] = val_df_processed.groupby('stock_code')[FEATURE_COLS].ffill()
    val_df_processed[FEATURE_COLS] = val_df_processed[FEATURE_COLS].fillna(0)
    log("-> 'Val' Set 가공 완료.")
    
    # 3. ⭐️ [V15] 스케일러 훈련 및 적용
    log("\n✅ [V15.LeakFix] 스케일러 훈련(Train) 및 적용(Train/Val)...")
    scaler = RobustScaler()
    scaler.fit(train_df_processed[FEATURE_COLS])
    train_df_processed[FEATURE_COLS] = scaler.transform(train_df_processed[FEATURE_COLS])
    val_df_processed[FEATURE_COLS] = scaler.transform(val_df_processed[FEATURE_COLS])
    log("-> 스케일링 완료.")
    
    # ⭐️ [V15] 가공된 Splits 객체 생성
    splits_processed = Splits(
        train_df=train_df_processed,
        val_df=val_df_processed,
        test_df=splits_raw.test_df # Test는 사용하지 않음
    )
    
    # 4. ⭐️ [V15] 시퀀스 생성 (가공된 데이터 사용)
    Xtr_max, ytr, ytr_prev, Xva_max, yva, yva_prev = make_arrays_max(
        splits_processed, args.max_seq_length, args.target_offset, args.embargo_days
    )
    if len(Xtr_max) == 0 or len(Xva_max) == 0:
        log("❌ 오류: Train 또는 Validation 시퀀스가 생성되지 않았습니다.")
        return

    for arch in args.arches:
        version_dir = os.path.join(args.results_dir, f"v20_{arch}_classify_only")
        best_params_path = os.path.join(version_dir, "best_params.json")
        if not os.path.exists(best_params_path):
            log(f"-> {arch}: best_params.json 미존재. 건너뜀: {best_params_path}")
            continue

        with open(best_params_path, "r", encoding="utf-8") as f: params = json.load(f)
        defaults = dict(learning_rate=5e-4, dropout_rate=0.5, dense_layers=1, dense_units=256, batch_size=64, activation="tanh")
        if arch == "lstm": defaults.update({"lstm_n_layers": 2, "lstm_units": 128})
        if arch == "bilstm": defaults.update({"bilstm_n_layers": 2, "bilstm_units": 128})
        if arch == "gru": defaults.update({"gru_n_layers": 2, "gru_units": 128})
        if arch == "cnnlstm": defaults.update({"n_layers": 1, "lstm_units": 128, "cnn_filters": 64, "cnn_kernel_size": 3, "use_attention": False})
        if arch == "tcn": defaults.update({"tcn_filters": 64, "tcn_kernel_size": 3, "tcn_n_blocks": 2, "tcn_dilation_base": 2})
        if arch == "transformer": defaults.update({"d_model": 128, "num_heads": 4, "transformer_n_blocks": 2, "dff": 256})
        for k,v in defaults.items(): params.setdefault(k, v)
        seq_len = int(params.get("seq_length", args.max_seq_length))
        if seq_len > Xtr_max.shape[1]:
            log(f"-> {arch}: best seq_length({seq_len}) > MAX({Xtr_max.shape[1]}) → {Xtr_max.shape[1]}로 수정")
            params["seq_length"] = int(Xtr_max.shape[1])
        params["seq_length"] = int(params.get("seq_length", args.max_seq_length))

        log("="*100)
        
        if args.seed is not None:
            log(f"-> ⭐️ [단일 실행/복구 모드] --seed {args.seed} (n_runs 무시)")
            seeds_to_run = [args.seed]
            n_total_runs = 1
        else:
            log(f"-> ⭐️ [다중 실행 모드] n_runs={args.n_runs}")
            seeds_to_run = [SEED + 1000 + i for i in range(args.n_runs)]
            n_total_runs = args.n_runs

        log(f"🚀 Phase1.5 반복학습 시작: {arch.upper()} | Total Runs={n_total_runs} | "
            f"⭐️ 불균형 처리: {args.imbalance_mode.upper()} | " 
            f"⭐️ [V17] 모니터링: val_custom_score | " # ⭐️ [V17] 로그 수정
            f"Optimize: 0.5 Fixed CustomScore (BalAcc - |R1-R0|) | " # ⭐️ [V17] 로그 수정
            f"seq_len={params['seq_length']} | offset={args.target_offset} | embargo={args.embargo_days}d") 

        run_results = []
        for i, seed in enumerate(seeds_to_run):
            log(f"\n--- [{arch.upper()}] Run {i+1}/{n_total_runs} (seed={seed}) ---")
            try:
                res = run_once(
                    seed=seed, arch=arch, params=params,
                    Xtr_max=Xtr_max, ytr=ytr, Xva_max=Xva_max, yva=yva, yva_prev=yva_prev,
                    max_seq_len=args.max_seq_length,
                    imbalance_mode=args.imbalance_mode 
                )
                log(f"[{arch.upper()}] Run#{i+1} 결과: CustomScore@0.5={res['custom_score_0p5']:.4f} | BalAcc@0.5={res['balacc_0p5']:.4f} | MCC@0.5={res['mcc_0p5']:.4f} | Brier={res['brier']:.4f}")
                run_results.append(res)
            except Exception as e:
                log(f"❌ [{arch.upper()}] Run#{i+1} (seed={seed}) 실패: {e}")
                import traceback
                traceback.print_exc()
                tf.keras.backend.clear_session()

        log("\n" + "="*60)
        
        global _CURRENT_LOG_FILE
        log_txt_path = os.path.join(version_dir, "phase1_5_summary_report.txt")
        try:
            _CURRENT_LOG_FILE = open(log_txt_path, "w", encoding="utf-8") 
            log(f"-> ⭐️ 상세 요약 리포트를 {log_txt_path} 에 저장 시작...")
        except Exception as e:
            log(f"-> ⚠️ 경고: 로그 파일({log_txt_path}) 열기 실패: {e}")
            _CURRENT_LOG_FILE = None 

        log(f"✅ [5/5] 챔피언 선발 및 최종 저장 ({arch.upper()})")
        if not run_results:
            log(f"❌ 오류: {arch.upper()} 훈련 결과가 없습니다. 건너뜀.")
            if _CURRENT_LOG_FILE: 
                _CURRENT_LOG_FILE.close(); _CURRENT_LOG_FILE = None
            continue
            
        # ⭐️ [V17] 최종 선발 기준을 'custom_score_0p5'로 변경
        log(f"   -> ⭐️ 0.5 고정 기준 'CustomScore' (BalAcc - |R1-R0|)로 정렬")
        
        for r in run_results:
            # ⭐️ [V17] CompScore 대신 CustomScore 사용
            custom_score_0p5 = r.get("custom_score_0p5", -1.0)
            r["custom_score"] = custom_score_0p5 # ⭐️ 정렬용 키
            log(f"   -> Run (Seed {r['seed']}): CustomScore={custom_score_0p5:.4f} (BalAcc@0.5={r.get('balacc_0p5', 0):.4f}, R0={r.get('recall0_0p5', 0):.4f}, R1={r.get('recall1_0p5', 0):.4f})")

        sorted_runs = sorted(
            run_results,
            key=lambda r: r["custom_score"], # ⭐️ [V17] 정렬 기준 변경
            reverse=True
        )
        
        top_k_to_save_count = 1 if args.seed is not None else args.top_k_save
        top_k_runs = sorted_runs[:top_k_to_save_count]
        
        log("\n" + "-"*40) 
        log(f"🏆 Top-{len(top_k_runs)} 챔피언 ({arch.upper()}) (CustomScore 기준 정렬)") # ⭐️ [V17] 로그 수정
        
        final_saved_model_paths = [] 
        
        for i, run in enumerate(top_k_runs):
            rank = i + 1
            log(f"\n   --- 🥇 챔피언 {rank} (Seed {run['seed']}) ---")
            log(f"   [종합] CustomScore={run.get('custom_score', 0):.4f} | BestEpoch={run['best_epoch']} | PRAUC={run['prauc']:.4f} | Brier={run.get('brier', 0):.4f}") # ⭐️ [V17] CompScore -> CustomScore
            log(f"   [A: 고정 0.5 임계값] (⭐️핵심 성능⭐️)")
            log(f"     - 🎯 CustomScore (선발기준): {run.get('custom_score_0p5', 0):.4f}")
            log(f"     - 🎯 BalAcc (참고): {run.get('balacc_0p5', 0):.4f}")
            log(f"     - 🎯 MCC (참고): {run.get('mcc_0p5', 0):.4f}")
            log(f"     - [편향진단] R0 (하락 예측률): {run.get('recall0_0p5', 0):.4f} | R1 (상승 예측률): {run.get('recall1_0p5', 0):.4f}")
            log(f"     - [편향진단] 예측된 상승 비율: {run.get('pred_pos_rate_0p5', 0):.4f}")
            log(f"   [B: 최적 임계값 @ {run['best_threshold']:.4f}] (참고용)")
            log(f"     - 🎯 BalAcc (최대 성능): {run.get('balacc_best', 0):.4f}")
            log(f"     - [편향진단] R0 (하락 예측률): {run.get('recall0_best', 0):.4f} | R1 (상승 예측률): {run.get('recall1_best', 0):.4f}")
            log(f"     - [편향진단] 예측된 상승 비율: {run.get('pred_pos_rate_best', 0):.4f} | F1(상승): {run.get('f1_pos_best', 0):.4f}")
            log(f"   [C: 견고성 지표] (참고용, @최적Thr기준)")
            log(f"     - 🎯 Plateau BalAcc: {run.get('thr_plateau_mean', 0):.4f} (Std={run.get('thr_plateau_std', 0):.4f})")
            log(f"     - 🎯 Plateau MCC: {run.get('thr_plateau_mcc_mean', 0):.4f}")

            final_model_path = os.path.join(version_dir, f"classification_model_rank{rank}.h5") 
            try:
                log(f"   -> 🏆 Rank {rank} 모델 로딩: {run['saved_model']}")
                champion_model = KM.load_model(run['saved_model'], custom_objects={"PositionalEncoding": PositionalEncoding})
                champion_model.save(final_model_path)
                log(f"   -> 🏆 Rank {rank} 모델 .h5로 변환 저장 완료: {final_model_path}")
                del champion_model
                tf.keras.backend.clear_session()
                
                run['saved_model_final'] = final_model_path
                final_saved_model_paths.append(run['saved_model']) 
            except Exception as e:
                log(f"   -> ❌ Rank {rank} 모델 저장/변환 실패: {e}");
        
        if not top_k_runs:
             log("   -> ❌ 저장할 챔피언 모델이 없습니다."); continue

        champion_rank1 = top_k_runs[0]
        params["best_validation_score"] = float(champion_rank1['custom_score']) # ⭐️ [V17] 변경
        params["champion_run_seed"] = champion_rank1['seed']
        params["best_threshold"] = 0.5 
        params["champion_model_path"] = champion_rank1.get('saved_model_final', 'N/A') 
        params["champion_metrics"] = {
            "custom_score_0p5": champion_rank1.get("custom_score_0p5"), # ⭐️ [V17] 변경
            "balacc_0p5": champion_rank1.get("balacc_0p5"),
            "mcc_0p5": champion_rank1.get("mcc_0p5"),
            "brier": champion_rank1.get("brier"),
            "prauc": champion_rank1.get("prauc"),
            "recall0_0p5": champion_rank1.get("recall0_0p5"),
            "recall1_0p5": champion_rank1.get("recall1_0p5"),
            "pred_pos_rate_0p5": champion_rank1.get("pred_pos_rate_0p5"),
            "balacc_best_ref": champion_rank1.get("balacc_best"),
            "best_threshold_ref": champion_rank1.get("best_threshold"),
        }
        try:
            with open(best_params_path, "w", encoding="utf-8") as f:
                json.dump(params, f, ensure_ascii=False, indent=2)
            log(f"   -> {best_params_path}에 1등 챔피언(Rank 1)의 CustomScore/시드/0.5임계값/상세지표 덮어쓰기 완료.") # ⭐️ [V17] 로그 수정
        except Exception as e:
            log(f"   -> ⚠️ 경고: best_params.json 덮어쓰기 실패: {e}")

        deleted_count = 0
        for res in run_results:
            temp_keras_path = res['saved_model']
            if temp_keras_path in final_saved_model_paths:
                log(f"   -> ⭐️ {os.path.basename(temp_keras_path)} (Top-K) 보존됨. (최종 .h5로 변환 완료)")
                try: os.remove(temp_keras_path); 
                except Exception as e: log(f"   -> ⚠️ 경고: 변환 완료된 임시 모델 삭제 실패 ({temp_keras_path}): {e}")
            else:
                if os.path.exists(temp_keras_path):
                    try: os.remove(temp_keras_path); deleted_count += 1
                    except Exception as e: log(f"   -> ⚠️ 경고: 임시 모델 삭제 실패 ({temp_keras_path}): {e}")
        log(f"   -> 임시 모델 파일 {deleted_count}개 삭제 완료.")
        
        for run in top_k_runs:
            run['saved_model'] = run.get('saved_model_final', 'SAVE_FAILED') 
            if 'saved_model_final' in run: del run['saved_model_final'] 

        out = {
            "arch": arch, 
            "n_runs": n_total_runs, 
            "run_mode": "single_seed_recovery" if args.seed is not None else "multi_run_selection", 
            "top_k_runs": top_k_runs, 
            "champion_rank1": champion_rank1, 
            "metric_sort_key": "CustomScore (BalAcc@0.5 - abs(R1@0.5 - R0@0.5))", # ⭐️ [V17] 수정
            "target_offset": args.target_offset,
            "embargo_days": args.embargo_days, "max_seq_length_fixed": args.max_seq_length
        }
        
        report_path = os.path.join(version_dir, "phase1_5_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        log(f"-> 저장: {report_path}")
        
        if _CURRENT_LOG_FILE:
            log(f"-> ⭐️ 상세 요약 리포트 저장 완료: {log_txt_path}")
            _CURRENT_LOG_FILE.close()
            _CURRENT_LOG_FILE = None 
        
    log("\n✅ Phase 1.5 (방향성, 견고성 강화) 전체 완료")

if __name__ == "__main__":
    main()
