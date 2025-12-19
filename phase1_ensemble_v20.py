# -*- coding: utf-8 -*-
# phase1_ensemble_v20.py
#
# ⭐️⭐️⭐️ [V14.CustomMetric] (커스텀 지표) ⭐️⭐️⭐️
# 1. ⭐️ (수정) [튜닝 목표 변경] MCC/BalAcc가 편향 모델에 높은 점수를 주는 맹점 발견.
#    "CustomScore = BalAcc - |R1 - R0|" (균형 페널티)를 최종 튜닝 목표로 사용.
#    MONITOR_METRIC_NAME을 'val_custom_score'로 변경.
# 2. ⭐️ (수정) MetricsCallback에 'val_custom_score' 계산 로직 추가
# 3. (유지) [안정성 보조] 'ReduceLROnPlateau'는 'val_loss'를 계속 모니터링
# 4. (유지) "아주 부드러운 가중치" (V11) + "누수 방지" (V6) 로직 모두 유지

from __future__ import annotations

# ====== 환경 설정 ======
import os
os.environ['PYTHONHASHSEED'] = '42'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import sys, argparse, json, math, warnings, random, shutil
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional, Union, Any

import numpy as np
import pandas as pd
import joblib

from sklearn.preprocessing import RobustScaler 
from sklearn.metrics import (
    f1_score, balanced_accuracy_score, precision_score, recall_score,
    average_precision_score, confusion_matrix, 
    brier_score_loss, 
    matthews_corrcoef
)
from sklearn.utils.class_weight import compute_sample_weight, compute_class_weight

import tensorflow as tf
import tensorflow.keras as K
from tensorflow.keras import layers as KL
from tensorflow.keras import models as KM
from tensorflow.keras import optimizers as KO
from tensorflow.keras import losses as KLoss
from tensorflow.keras import mixed_precision

import optuna
from optuna.samplers import TPESampler
from optuna.pruners import PercentilePruner

warnings.filterwarnings("ignore")

# =============================================================================
# 설정
# =============================================================================
SEED = 42
np.random.seed(SEED); random.seed(SEED); tf.random.set_seed(SEED)

# GPU 설정
try:
    gpus = tf.config.list_physical_devices("GPU")
    for g in gpus: tf.config.experimental.set_memory_growth(g, True)
    if gpus: 
        print(f"-> {len(gpus)}개 GPU 메모리 증가 설정 완료.")
        try:
            policy = mixed_precision.Policy('mixed_float16')
            mixed_precision.set_global_policy(policy)
            print("-> ⭐️ AMP (mixed_float16) 활성화 완료.")
        except Exception as e:
            print(f"-> ⚠️ AMP (mixed_float16) 활성화 실패: {e}")
except Exception as e: 
    print(f"-> 경고: GPU 메모리 설정 중 오류: {e}")

BASE_RESULTS_DIR = "experiments_v20_ensemble"
PREPROCESSED_DATA_DIR = "preprocessed_dfs"
MAX_SEQ_LEN_FOR_TUNING = 240 

def ensure_dir(p: str): os.makedirs(p, exist_ok=True)
def log(msg: str): print(msg, flush=True)

def _brier(y_true, y_prob):
    try:
        return float(brier_score_loss(y_true.astype(int), y_prob.astype(float)))
    except Exception:
        return np.nan
        
def _mcc(y_true, y_pred):
    try:
        return float(matthews_corrcoef(y_true, y_pred))
    except Exception:
        return 0.0 # 편향이 심해 계산 불가 시 0점

# =============================================================================
# config.py
# =============================================================================
try:
    from config import FEATURE_COLS, TEMPORAL_COLS, STATIC_COLS
except ImportError:
    print("오류: config.py 또는 FEATURE_COLS/TEMPORAL/STATIC_COLS를 찾을 수 없습니다.", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# ⭐️ [V25] phase0에서 헬퍼 함수 이동 (누수 없는 가공용)
# =============================================================================
def calculate_indicators(df_group):
    """(phase0에서 이동) 그룹별(종목별)로 호출되어야 함"""
    df = df_group.copy() # SettingWithCopyWarning 방지
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
    """(phase0에서 이동) 분할된 df(train/val/test)별로 호출되어야 함"""
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
    """(phase0에서 이동) 분할된 df에 피처 컬럼 보장"""
    missing = [c for c in feature_cols if c not in df.columns]
    for c in missing: 
        df[c] = np.nan
    if missing:
        log(f"   -> ⭐️ [V25] 누락 피처 {len(missing)}개를 NaN으로 생성.")
    return df
# =============================================================================


# =============================================================================
# ⭐️ [V25] 데이터 로딩 (수정)
# =============================================================================
@dataclass
class DataSplits:
    train_df: pd.DataFrame; val_df: pd.DataFrame; test_df: pd.DataFrame
    feature_cols: List[str]

def load_data_from_files(data_dir: str) -> DataSplits:
    log(f"✅ [1/7] Phase0 *RAW* 산출물 로딩: {data_dir}")
    try:
        train_df = pd.read_pickle(os.path.join(data_dir, "train_df_raw.pkl"))
        val_df   = pd.read_pickle(os.path.join(data_dir, "val_df_raw.pkl"))
        test_df  = pd.read_pickle(os.path.join(data_dir, "test_df_raw.pkl"))
    except FileNotFoundError as e:
        log(f"-> 로딩 실패: {e}"); 
        log("-> ⭐️ [V25] phase0 (V25 수정본)을 먼저 실행하여 _raw.pkl 파일을 생성해야 합니다.")
        sys.exit(1)
    
    def _info(name, df):
        if df.empty: log(f"RAW/{name}: EMPTY"); return
        d0, d1 = df["date"].min(), df["date"].max()
        pr = df["direction"].mean() if "direction" in df.columns else np.nan
        log(f"RAW/{name}: {d0.date()} ~ {d1.date()} rows={len(df):,} pos_rate={pr:.3f}")

    _info("Train", train_df); _info("Val", val_df); _info("Test", test_df)
    
    return DataSplits(train_df, val_df, test_df, FEATURE_COLS)

# =============================================================================
# ⭐️ [V6] 시퀀스 생성 (target_offset=1 수정)
# =============================================================================
def _group_key(df: pd.DataFrame) -> str:
    if 'stock_code' in df.columns: return 'stock_code'
    if 'ticker' in df.columns: return 'ticker'
    raise ValueError("stock_code/ticker 컬럼이 필요합니다.")

def create_sequences_train_only(
    df: pd.DataFrame, 
    max_seq_len: int, 
    temporal_cols: List[str],
    target_col="direction", 
    target_offset=1 # ⭐️ [V6] 타겟 누수 방지 (0 -> 1)
) -> Tuple[np.ndarray, np.ndarray]:
    """Train set에 사용: 각 그룹(종목) 내부에서만 시퀀스 생성"""
    X, y = [], []
    if df.empty:
        return np.empty((0, max_seq_len, len(temporal_cols)), dtype=np.float32), \
               np.empty((0,), dtype=np.int32)
               
    gk = _group_key(df)
    for _, g in df.groupby(gk):
        g = g.sort_values("date")
        temp = g[temporal_cols].values
        tgt = g[target_col].astype(int).values
        
        if len(temp) <= max_seq_len + max(0, target_offset): 
            continue
            
        t_min = max_seq_len - 1
        t_max = len(temp) - 1 - max(0, target_offset)
        
        for t in range(t_min, t_max):
            X.append(temp[t-(max_seq_len-1): t+1]) 
            y.append(tgt[t + target_offset]) 
            
    X_np = np.asarray(X, np.float32) if len(X) else np.empty((0, max_seq_len, len(temporal_cols)), dtype=np.float32)
    y_np = np.asarray(y, np.int32) if len(y) else np.empty((0,), dtype=np.int32)
    return X_np, y_np

def create_sequences_val_with_history(
    train_df: pd.DataFrame, 
    val_df: pd.DataFrame, 
    max_seq_len: int,
    temporal_cols: List[str], 
    target_col="direction",
    target_offset=1 # ⭐️ [V6] 타겟 누수 방지 (0 -> 1)
) -> Tuple[np.ndarray, np.ndarray]:
    """Val set에 사용: Train set을 "과거 기록"으로 사용 (누수 방지됨)"""
    X, y = [], []
    if val_df.empty:
        return np.empty((0, max_seq_len, len(temporal_cols)), dtype=np.float32), \
               np.empty((0,), dtype=np.int32)
               
    gk = _group_key(val_df if len(val_df)>0 else train_df)
    
    hist = pd.concat([train_df.copy(), val_df.copy()], ignore_index=True).sort_values([gk, "date"])
    
    for code, g_hist in hist.groupby(gk):
        g_hist = g_hist.sort_values("date")
        g_val = val_df[val_df[gk]==code].sort_values("date")
        
        if g_val.empty: continue

        temp = g_hist[temporal_cols].values
        tgt_dates = pd.to_datetime(g_hist["date"]).values
        tgt_vals  = g_hist[target_col].astype(int).values
        
        val_dates_set = set(pd.to_datetime(g_val["date"]).values)

        for t in range(len(g_hist)):
            tt = t + target_offset 
            if tt >= len(g_hist): break
            if tgt_dates[tt] not in val_dates_set: 
                continue

            start_idx = t - (max_seq_len - 1)
            if start_idx < 0: 
                continue 
            
            X.append(temp[start_idx:t+1])
            y.append(int(tgt_vals[tt]))
    
    X_np = np.asarray(X, np.float32) if len(X) else np.empty((0, max_seq_len, len(temporal_cols)), dtype=np.float32)
    y_np = np.asarray(y, np.int32) if len(y) else np.empty((0,), dtype=np.int32)
    return X_np, y_np
# =============================================================================


# =============================================================================
# Body 빌더들 (수정 없음)
# =============================================================================
def build_lstm_body(input_shape: Tuple[int, int], params: Dict[str, Any]) -> Tuple[tf.Tensor, tf.Tensor]:
    inp = KL.Input(shape=input_shape, name="temporal_input"); x = inp
    n_layers = params.get("lstm_n_layers", 2); units = params.get("lstm_units", 128)
    for i in range(n_layers): rs = (i < n_layers - 1); x = KL.LSTM(units, return_sequences=rs)(x)
    return inp, x
def build_bilstm_body(input_shape: Tuple[int, int], params: Dict[str, Any]) -> Tuple[tf.Tensor, tf.Tensor]:
    inp = KL.Input(shape=input_shape, name="temporal_input"); x = inp
    n_layers = params.get("bilstm_n_layers", 2); units = params.get("bilstm_units", 128)
    for i in range(n_layers): rs = (i < n_layers - 1); x = KL.Bidirectional(KL.LSTM(units, return_sequences=rs))(x)
    return inp, x
def build_gru_body(input_shape: Tuple[int, int], params: Dict[str, Any]) -> Tuple[tf.Tensor, tf.Tensor]:
    inp = KL.Input(shape=input_shape, name="temporal_input"); x = inp
    n_layers = params.get("gru_n_layers", 2); units = params.get("gru_units", 128)
    for i in range(n_layers): rs = (i < n_layers - 1); x = KL.GRU(units, return_sequences=rs)(x)
    return inp, x
def build_cnnlstm_body(input_shape: Tuple[int, int], params: Dict[str, Any]) -> Tuple[tf.Tensor, tf.Tensor]:
    inp = KL.Input(shape=input_shape, name="temporal_input")
    x = KL.Conv1D(filters=params.get("cnn_filters", 64), kernel_size=params.get("cnn_kernel_size", 3), padding="same", activation="relu")(inp)
    x = KL.MaxPooling1D()(x) 
    n_layers = params.get("n_layers", 1); units = params.get("lstm_units", 128); use_attn = params.get("use_attention", False)
    for i in range(n_layers): rs = (i < n_layers - 1) or use_attn; x = KL.LSTM(units, return_sequences=rs)(x)
    if use_attn and len(x.shape) == 3:
        try:
            num_heads = params.get("num_heads_cnn", 2); key_dim = max(1, units // num_heads)
            attn = KL.MultiHeadAttention(num_heads=num_heads, key_dim=key_dim); x = attn(query=x, value=x, key=x)
            if len(x.shape) == 3: x = KL.GlobalAveragePooling1D()(x)
        except Exception:
             if isinstance(x, tf.Tensor) and len(x.shape) == 3: x = KL.GlobalAveragePooling1D()(x)
    return inp, x
def TCNResidualBlock(n_filters, kernel_size, dilation_rate):
    def build_block(inputs):
        x = inputs; x = KL.Conv1D(filters=n_filters, kernel_size=kernel_size, dilation_rate=dilation_rate, padding='causal', kernel_initializer='he_normal')(x)
        x = KL.BatchNormalization()(x); x = KL.Activation('relu')(x); x = KL.Dropout(0.3)(x)
        x = KL.Conv1D(filters=n_filters, kernel_size=kernel_size, dilation_rate=dilation_rate, padding='causal', kernel_initializer='he_normal')(x)
        x = KL.BatchNormalization()(x); x = KL.Activation('relu')(x); x = KL.Dropout(0.3)(x)
        if inputs.shape[-1] != n_filters: shortcut = KL.Conv1D(filters=n_filters, kernel_size=1, padding='same')(inputs)
        else: shortcut = inputs
        x = KL.Add()([shortcut, x]); x = KL.Activation('relu')(x); return x
    return build_block
def build_tcn_body(input_shape: Tuple[int, int], params: Dict[str, Any]) -> Tuple[tf.Tensor, tf.Tensor]:
    inp = KL.Input(shape=input_shape, name="temporal_input"); x = inp; n_filters = params.get("tcn_filters", 64)
    kernel_size = params.get("tcn_kernel_size", 3); n_blocks = params.get("tcn_n_blocks", 2); dilation_base = params.get("tcn_dilation_base", 2)
    x = KL.Conv1D(n_filters, 1, padding='same')(x) 
    for i in range(n_blocks): dilation_rate = dilation_base ** i; x = TCNResidualBlock(n_filters, kernel_size, dilation_rate)(x)
    x = KL.GlobalAveragePooling1D()(x); return inp, x
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
def transformer_encoder_block(inputs, d_model, num_heads, dff, dropout_rate):
    attn_output = KL.MultiHeadAttention(num_heads=num_heads, key_dim=max(1, d_model // num_heads), dropout=dropout_rate)(inputs, inputs)
    attn_output = KL.LayerNormalization(epsilon=1e-6)(inputs + attn_output)
    ffn_output = KL.Dense(dff, activation="gelu")(attn_output); ffn_output = KL.Dense(d_model)(ffn_output); ffn_output = KL.Dropout(dropout_rate)(ffn_output)
    output = KL.LayerNormalization(epsilon=1e-6)(attn_output + ffn_output); return output
def build_transformer_body(input_shape: Tuple[int, int], params: Dict[str, Any]) -> Tuple[tf.Tensor, tf.Tensor]:
    seq_len, num_features = input_shape; d_model = params.get("d_model", 128); num_heads = params.get("num_heads", 4); dff = params.get("dff", d_model * 2)
    n_blocks = params.get("transformer_n_blocks", 2); dropout_rate = params.get("dropout_rate", 0.3)
    inp = KL.Input(shape=input_shape, name="temporal_input"); x = KL.Conv1D(filters=d_model, kernel_size=1, activation="relu")(inp)
    max_seq_len_for_pe = 512; x = PositionalEncoding(position=max_seq_len_for_pe, d_model=d_model)(x); x = KL.Dropout(dropout_rate)(x)
    for _ in range(n_blocks): x = transformer_encoder_block(x, d_model, num_heads, dff, dropout_rate)
    x = KL.GlobalAveragePooling1D()(x); return inp, x
# =============================================================================


# =============================================================================
# Head / 컴파일 (수정 없음)
# =============================================================================
def head_classify(x: tf.Tensor, params: Dict[str, Any]) -> tf.Tensor:
    dr = params.get("dropout_rate", 0.3); L = params.get("dense_layers", 1); H = params.get("dense_units", 128); act = params.get("activation", "relu")
    h = KL.Dropout(dr)(x)
    for _ in range(L): h = KL.Dense(H, activation=act)(h); h = KL.Dropout(dr)(h)
    out = KL.Dense(1, activation="sigmoid", name="direction_output", dtype="float32")(h)
    return out

def build_model_by_arch_classify(arch: str, temporal_input_shape: Tuple[int, int], params: Dict[str, Any]) -> KM.Model:
    if arch == "lstm": inp, body = build_lstm_body(temporal_input_shape, params)
    elif arch == "bilstm": inp, body = build_bilstm_body(temporal_input_shape, params)
    elif arch == "gru": inp, body = build_gru_body(temporal_input_shape, params)
    elif arch == "cnnlstm": inp, body = build_cnnlstm_body(temporal_input_shape, params)
    elif arch == "tcn": inp, body = build_tcn_body(temporal_input_shape, params)
    elif arch == "transformer": inp, body = build_transformer_body(temporal_input_shape, params)
    else: raise ValueError(f"Unknown arch: {arch}")
    output = head_classify(body, params); return KM.Model(inputs=inp, outputs=output, name=f"{arch.upper()}_Classify")
def compile_model_classify(model: KM.Model, lr: float) -> KM.Model:
    model.compile(optimizer=KO.Adam(learning_rate=lr), loss=KLoss.BinaryCrossentropy(),
                  metrics=[K.metrics.BinaryAccuracy(name="acc"), K.metrics.AUC(name="auc"), K.metrics.Precision(name="precision"), K.metrics.Recall(name="recall")])
    return model
# =============================================================================


# =============================================================================
# Optuna (수정 없음)
# =============================================================================
def suggest_params(trial: optuna.trial.Trial, arch: str) -> Dict[str, Any]:
    p: Dict[str, Any] = {}; p["learning_rate"] = trial.suggest_float("learning_rate", 1e-4, 1e-2, log=True)
    p["activation"] = trial.suggest_categorical("activation", ["relu","gelu","tanh"]); p["dropout_rate"] = trial.suggest_float("dropout_rate", 0.4, 0.7)
    p["dense_layers"] = trial.suggest_int("dense_layers", 1, 2); p["dense_units"] = trial.suggest_categorical("dense_units", [128, 256])
    p["batch_size"] = trial.suggest_categorical("batch_size", [32, 64, 128])
    
    p["seq_length"] = trial.suggest_int("seq_length", 64, MAX_SEQ_LEN_FOR_TUNING)
    
    if arch == "lstm":
        p["lstm_n_layers"] = trial.suggest_int("lstm_n_layers", 2, 4); p["lstm_units"] = trial.suggest_categorical("lstm_units", [64, 128, 256])
    elif arch == "bilstm":
        p["bilstm_n_layers"] = trial.suggest_int("bilstm_n_layers", 2, 4); p["bilstm_units"] = trial.suggest_categorical("bilstm_units", [64, 128, 256])
    elif arch == "gru":
        p["gru_n_layers"] = trial.suggest_int("gru_n_layers", 2, 4); p["gru_units"] = trial.suggest_categorical("gru_units", [64, 128, 256])
    elif arch == "cnnlstm":
        p["n_layers"] = trial.suggest_int("n_layers", 1, 2); p["lstm_units"] = trial.suggest_categorical("lstm_units", [128, 256])
        p["cnn_filters"] = trial.suggest_categorical("cnn_filters", [64, 128, 256]); p["cnn_kernel_size"] = trial.suggest_categorical("cnn_kernel_size", [3, 5])
        p["use_attention"] = trial.suggest_categorical("use_attention", [False, True])
        if p["use_attention"]: p["num_heads_cnn"] = trial.suggest_categorical("num_heads_cnn", [2, 4])
    elif arch == "tcn":
        p["tcn_filters"] = trial.suggest_categorical("tcn_filters", [32, 64, 128]); p["tcn_kernel_size"] = trial.suggest_categorical("tcn_kernel_size", [2, 3, 5])
        p["tcn_n_blocks"] = trial.suggest_int("tcn_n_blocks", 2, 4); p["tcn_dilation_base"] = trial.suggest_categorical("tcn_dilation_base", [2, 3])
    elif arch == "transformer":
        p["d_model"] = trial.suggest_categorical("d_model", [64, 128]); p["num_heads"] = trial.suggest_categorical("num_heads", [2, 4, 8])
        p["transformer_n_blocks"] = trial.suggest_int("transformer_n_blocks", 1, 3); p["dff"] = p["d_model"] * trial.suggest_categorical("dff_multiplier", [2, 4])
    return p

class BrierMonitor(K.callbacks.Callback):
    def __init__(self, X_val, y_val, patience=5, batch_size=1024):
        super().__init__()
        self.X_val, self.y_val = X_val, y_val.astype(int)
        self.patience = patience
        self.bs = batch_size
        self.best = np.inf
        self.bad = 0
    def on_epoch_end(self, epoch, logs=None):
        if self.X_val is None or len(self.X_val) == 0: return
        p = self.model.predict(self.X_val, verbose=0, batch_size=self.bs).ravel()
        b = _brier(self.y_val, p)
        if b < self.best - 1e-4: 
            self.best = b; self.bad = 0
        else:
            self.bad += 1
        print(f"[Epoch {epoch+1}] val_brier={b:.6f} (best={self.best:.6f}, bad_streak={self.bad})")

# ⭐️ [V11] objective (수정: "아주 부드러운 가중치" 로직)
def objective(
    trial: optuna.trial.Trial, 
    arch: str, 
    splits_processed: DataSplits, 
    imbalance_mode: str,
    X_val_max: np.ndarray,
    y_val: np.ndarray
) -> float:
    
    train_df = splits_processed.train_df
    version = f"v20_{arch}_classify_only"; results_dir = os.path.join(BASE_RESULTS_DIR, version); best_log_file = os.path.join(results_dir, "best_trials_log.txt")
    
    try: params = suggest_params(trial, arch)
    except Exception as e: log(f"파라미터 제안 실패: {e}"); raise optuna.exceptions.TrialPruned()
    
    seq_len = params["seq_length"]; bs = params["batch_size"]

    log(f"-> [Trial {trial.number}] Train 시퀀스 생성 (SeqLen={seq_len})")
    try:
        Xtr_t, ytr = create_sequences_train_only(
            train_df, seq_len, TEMPORAL_COLS, target_col="direction"
        )
        Xva_t = X_val_max[:, -seq_len:, :]
        yva = y_val
        
    except Exception as e: log(f"시퀀스 생성/슬라이싱 오류: {e}. Pruned."); raise optuna.exceptions.TrialPruned()
    
    if Xtr_t.shape[0] == 0: log("Train 시퀀스 0개. Pruned."); raise optuna.exceptions.TrialPruned()
    
    log(f"-> [Trial {trial.number}] 생성/슬라이싱 완료. (Train shape: {Xtr_t.shape}, Val shape: {Xva_t.shape})")

    sample_weights = None; class_weights_dict = None
    if imbalance_mode == "sample_weight":
        try:
            y_int = ytr.astype(int)
            if len(np.unique(y_int)) > 1:
                sample_weights = compute_sample_weight(class_weight='balanced', y=y_int).astype(np.float32)
                log("-> 'balanced' (강한) 샘플 가중치 (훈련셋) 적용 완료.")
            else: log("-> 샘플 가중치 미적용 (훈련셋 클래스 1개)")
        except Exception as e: log(f"-> 'balanced' 샘플 가중치 계산 실패({e}), 가중치 미적용.")
    
    # ⭐️ [V11] "아주 부드러운 가중치" (75% 완화) 로직
    elif imbalance_mode == "class_weight": 
        try:
            y_int = ytr.astype(int)
            if len(np.unique(y_int)) > 1:
                classes = np.unique(y_int)
                cw_raw = compute_class_weight(class_weight='balanced', classes=classes, y=y_int)
                
                # ⭐️ 가중치 완화 (Dampening): 1.0 (75%)과 'balanced' (25%)의 평균
                # ⭐️ (w_raw*0.25 + 1.0*0.75)
                cw_damped = [(w * 0.25 + 0.75) for w in cw_raw]
                
                class_weights_dict = dict(zip(classes, cw_damped))
                log(f"-> ⭐️ '아주 부드러운 가중치' (75% Damped) 적용 완료: {class_weights_dict}")
                log(f"   (참고: 원본 'balanced' 가중치: {dict(zip(classes, cw_raw))})")
            else:
                log("-> 클래스 가중치 미적용 (훈련셋 클래스 1개)")
        except Exception as e:
            log(f"-> '아주 부드러운 가중치' 계산 실패({e}), 가중치 미적용.")
            
    if sample_weights is not None and class_weights_dict is not None:
        log("-> 경고: sample_weight와 class_weight가 모두 설정됨. sample_weight만 사용."); class_weights_dict = None


    temporal_input_shape = (seq_len, len(TEMPORAL_COLS))
    model = build_model_by_arch_classify(arch, temporal_input_shape, params)
    model = compile_model_classify(model, lr=params["learning_rate"])

    # ⭐️ [V14] 튜닝 목표: val_custom_score (진짜 균형)
    MONITOR_METRIC_NAME = "val_custom_score"; MONITOR_METRIC_MODE = "max"
    
    metrics_cb = MetricsCallback(X_val=Xva_t, y_val=yva, batch_size=bs, thresh=0.5, monitor_metric=MONITOR_METRIC_NAME)
    
    callbacks = [
        metrics_cb,
        # ⭐️ [V14] EarlyStopping은 'CustomScore'를 모니터링
        # ⭐️ [V14] Patience를 15로 늘림 (LR 감소 후 학습 시간 부여)
        K.callbacks.EarlyStopping(monitor=MONITOR_METRIC_NAME, mode=MONITOR_METRIC_MODE, patience=15, restore_best_weights=True, verbose=1),
        # ⭐️ [V14] ReduceLROnPlateau는 'val_loss' (안정성)을 모니터링
        K.callbacks.ReduceLROnPlateau(monitor="val_loss", mode="min", factor=0.5, patience=5, min_lr=1e-6, verbose=1), 
        BrierMonitor(X_val=Xva_t, y_val=yva, patience=5, batch_size=bs), 
        # ⭐️ [V14] Pruning(가지치기)도 'CustomScore'를 모니터링
        optuna.integration.TFKerasPruningCallback(trial, MONITOR_METRIC_NAME),
    ]

    log(f"✅ [Trial {trial.number}] 학습 시작... (Arch={arch}, BS={bs}, Patience=15, Monitor={MONITOR_METRIC_NAME})")
    Xtr_fit = Xtr_t; Xva_fit = Xva_t 
    try:
        model.fit(Xtr_fit, ytr, validation_data=(Xva_fit, yva), epochs=100, batch_size=bs, verbose=1,
                  callbacks=callbacks, sample_weight=sample_weights, class_weight=class_weights_dict)
    except optuna.exceptions.TrialPruned as e: log(f"-> [Trial {trial.number}] Pruned."); raise e
    except Exception as e: log(f"학습 중 에러: {e}. Pruned."); tf.keras.backend.clear_session(); raise optuna.exceptions.TrialPruned()

    log(f"✅ [Trial {trial.number}] 검증셋(Val) 최종 평가 (ES 복원 모델)...")
    try:
        # ⭐️ [V14] CustomScore는 높을수록 좋으므로 max() 사용
        best_score = max(model.history.history[MONITOR_METRIC_NAME])
        log(f"-> Trial {trial.number} Best {MONITOR_METRIC_NAME}: {best_score:.5f}")
    except Exception as e:
        log(f"-> ⚠️ 경고: {MONITOR_METRIC_NAME} 점수 읽기 실패 ({e}).")
        best_score = -1.0 # ⭐️ [V14] CustomScore는 -1.0이 최악

    trial.set_user_attr("best_validation_score", float(best_score))
    
    # ⭐️ [V14] CustomScore는 높을수록 좋으므로 비교 로직 변경
    current_best_score = -1.0
    try: current_best_score = trial.study.best_value if trial.study.best_value is not None else -1.0
    except ValueError: pass
    is_best = bool(best_score is not None and not math.isnan(best_score) and not math.isinf(best_score) and best_score >= current_best_score)
    
    if is_best:
        log_msg = f"✨ New Best {MONITOR_METRIC_NAME} Found! ✨ Trial {trial.number}: {best_score:.5f}\n"; param_str = f"   ㄴ Params: LR={params['learning_rate']:.5f}, SeqLen={params['seq_length']}, BS={params['batch_size']}"
        if arch == 'lstm': param_str += f", Layers={params['lstm_n_layers']}, Units={params['lstm_units']}"
        elif arch == 'bilstm': param_str += f", Layers={params['bilstm_n_layers']}, Units={params['bilstm_units']}"
        elif arch == 'gru': param_str += f", Layers={params['gru_n_layers']}, Units={params['gru_units']}"
        elif arch == 'cnnlstm': param_str += f", Layers={params['n_layers']}, Units={params['lstm_units']}, Filters={params['cnn_filters']}, Kernel={params['cnn_kernel_size']}";
        elif arch == 'tcn': param_str += f", Filters={params['tcn_filters']}, Kernel={params['tcn_kernel_size']}, Blocks={params['tcn_n_blocks']}, Base={params['tcn_dilation_base']}"
        elif arch == 'transformer': param_str += f", d_model={params['d_model']}, n_heads={params['num_heads']}, n_blocks={params['transformer_n_blocks']}, dff={params['dff']}"
        log_msg += param_str; log(log_msg)
        try:
            with open(best_log_file, "a", encoding="utf-8") as f:
                import datetime; timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] Trial {trial.number} - New Best {MONITOR_METRIC_NAME}: {best_score:.5f}\n"); f.write(f"  Params: {json.dumps(params, indent=2)}\n"); f.write("-" * 30 + "\n")
        except Exception as e: log(f"경고: 최고 기록 로그 파일 저장 실패 - {e}")
        
    del model, Xtr_t, ytr, Xva_t, yva, Xtr_fit, Xva_fit
    tf.keras.backend.clear_session()
    return float(best_score) if np.isfinite(best_score) else -1.0

# ⭐️ [V14] MetricsCallback (수정: CustomScore 추가)
class MetricsCallback(K.callbacks.Callback):
    def __init__(self, X_val, y_val, batch_size=1024, thresh=0.5, monitor_metric="val_prauc_pos"):
        super().__init__(); self.X_val = X_val; self.y_val = y_val.astype(int); self.bs = batch_size
        self.th_0p5 = float(thresh); self.monitor_metric = monitor_metric
        
    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        if self.X_val is None or len(self.X_val) == 0:
            logs["val_balanced_acc_0p5"] = 0.0; logs["val_mcc_0p5"] = -1.0; logs["val_prauc_pos"] = -1.0; 
            logs["val_recall0_0p5"] = 0.0; logs["val_recall1_0p5"] = 0.0; logs["val_pred_pos_rate"] = 0.0; 
            logs["val_custom_score"] = -1.0; return # ⭐️ [V14] 추가

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
        pred_pos_rate = (tp + fp) / total_samples if total_samples > 0 else 0.0
        
        # ⭐️ [V14] 커스텀 스코어 (균형 페널티) 계산
        balance_penalty = abs(rec1_0p5 - rec0_0p5)
        custom_score = balacc_0p5 - balance_penalty
        
        try: pr_auc = average_precision_score(self.y_val, p)
        except Exception: pr_auc = np.nan
        
        logs["val_balanced_acc_0p5"] = float(balacc_0p5)
        logs["val_mcc_0p5"] = float(mcc_0p5) 
        logs["val_recall0_0p5"] = float(rec0_0p5) 
        logs["val_recall1_0p5"] = float(rec1_0p5) 
        logs["val_pred_pos_rate"] = float(pred_pos_rate)
        logs["val_custom_score"] = float(custom_score) # ⭐️ 로그에 추가
        
        f1pos_0p5 = f1_score(self.y_val, yhat_0p5, pos_label=1, zero_division=0)
        logs["val_f1_pos_0p5"] = float(f1pos_0p5)
        logs["val_prauc_pos"] = float(pr_auc) if not np.isnan(pr_auc) else -1.0
        
        # ⭐️ [V10] val_loss 덮어쓰기 로직 *완전 삭제*

        # ⭐️ [V14] 로그에 CustomScore 추가
        print(f"[Epoch {epoch+1}] CustomScore={custom_score:.4f}, BalAcc@0.5={balacc_0p5:.4f} | R0={rec0_0p5:.4f}, R1={rec1_0p5:.4f} | Pred_Rise%={pred_pos_rate:.4f}")

# =================================================================
# ⭐️ [V6] main (수정: 롤링 윈도우 누수 수정)
# =================================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", type=str, default=BASE_RESULTS_DIR)
    parser.add_argument("--arches", nargs="*", default=["lstm","bilstm","gru","cnnlstm", "tcn", "transformer"])
    parser.add_argument("--trials", type=int, default=50) 
    parser.add_argument("--data_dir", type=str, default=PREPROCESSED_DATA_DIR)
    parser.add_argument("--imbalance_mode", type=str, choices=["none", "sample_weight", "class_weight"], default="none")
    
    args = parser.parse_args()

    log("="*60)
    log(f"🚀 V20 Phase 1 (방향성 튜닝) 시작")
    log(f"-> 대상 아키텍처: {args.arches}")
    log(f"-> Trial 횟수 (N): {args.trials}")
    log(f"-> ⭐️ 불균형 처리 모드: {args.imbalance_mode.upper()}")
    # ⭐️ [V14] 로그 수정
    log(f"-> ⭐️ 메인 목표 (선정/중단): val_custom_score (BalAcc - |R1-R0|)")
    log(f"-> ⭐️ 보조 목표 (안정성): val_loss (학습률 조절)")
    log(f"-> ⭐️ [V25.LeakFix] 'phase0' RAW 데이터 로드 및 'phase1'에서 가공 시작...")
    log("="*60)

    # 1. RAW 데이터 로드
    splits_raw = load_data_from_files(args.data_dir)
    train_df_raw = splits_raw.train_df
    val_df_raw = splits_raw.val_df

    # 2. ⭐️ [V25.LeakFix.V6] 누수 없는 가공 파이프라인 (롤링 누수 최종 수정)
    
    log("\n✅ [2/7] [V25.LeakFix.V6] 'Train' Set 독립 가공 시작...")
    train_df_processed = train_df_raw.groupby('stock_code', group_keys=False).apply(calculate_indicators)
    train_df_processed = calculate_yoy(train_df_processed)
    train_df_processed = ensure_features(train_df_processed, FEATURE_COLS)
    train_df_processed[FEATURE_COLS] = train_df_processed.groupby('stock_code')[FEATURE_COLS].ffill()
    train_df_processed[FEATURE_COLS] = train_df_processed[FEATURE_COLS].fillna(0)
    log("-> 'Train' Set 가공 완료.")

    log("\n✅ [3/7] [V25.LeakFix.V6] 'Val' Set 독립 가공 시작 (롤링 누수 방지)...")
    val_df_processed = val_df_raw.groupby('stock_code', group_keys=False).apply(calculate_indicators)
    val_df_processed = calculate_yoy(val_df_processed)
    val_df_processed = ensure_features(val_df_processed, FEATURE_COLS)
    val_df_processed[FEATURE_COLS] = val_df_processed.groupby('stock_code')[FEATURE_COLS].ffill()
    val_df_processed[FEATURE_COLS] = val_df_processed[FEATURE_COLS].fillna(0)
    log("-> 'Val' Set 가공 완료.")
    
    # 3. ⭐️ [V25] 스케일러 훈련 및 적용
    log("\n✅ [4/7] [V25.LeakFix] 스케일러 훈련(Train) 및 적용(Train/Val)...")
    scaler = RobustScaler()
    scaler.fit(train_df_processed[FEATURE_COLS])
    train_df_processed[FEATURE_COLS] = scaler.transform(train_df_processed[FEATURE_COLS])
    val_df_processed[FEATURE_COLS] = scaler.transform(val_df_processed[FEATURE_COLS])
    log("-> 스케일링 완료.")
    
    # 4. ⭐️ [V25] 고정 검증 세트 (시퀀스) 생성
    log(f"\n✅ [5/7] 고정 Validation Set 생성 중 (MaxLen={MAX_SEQ_LEN_FOR_TUNING})...")
    X_val_max, y_val = create_sequences_val_with_history(
        train_df_processed, # ⭐️ 가공된 Train (History용)
        val_df_processed,   # ⭐️ 가공된 Val (타겟용)
        MAX_SEQ_LEN_FOR_TUNING, 
        TEMPORAL_COLS,
        target_col="direction",
        target_offset=1 # ⭐️ [V6] 타겟 누수 방지
    )
    if X_val_max.shape[0] == 0:
        log(f"❌ 치명적 오류: 고정 Validation Set 생성 실패 (0개)."); sys.exit(1)
    
    real_val_posrate = val_df_raw['direction'].mean()
    log(f"-> 고정 Val Set 생성 완료. Shape: {X_val_max.shape}, Labels: {y_val.shape}")
    log(f"-> ⭐️ (참고) 원본 RAW Val PosRate: {real_val_posrate:.3f}")
    log(f"-> ⭐️ (참고) 최종 시퀀스 Val PosRate: {y_val.mean():.3f}")
    
    splits_processed = DataSplits(
        train_df=train_df_processed,
        val_df=val_df_processed,
        test_df=splits_raw.test_df,
        feature_cols=FEATURE_COLS
    )

    # 5. ⭐️ [V25] 튜닝 시작
    log("\n✅ [6/7] Optuna 튜닝 시작...")
    for arch in args.arches:
        version = f"v20_{arch}_classify_only"; results_dir = os.path.join(args.results_dir, version); ensure_dir(results_dir)
        log("\n" + "="*60); log(f"🚀 Architecture: {arch.upper()} | Version: {version}"); log(f"-> 불균형 처리: {args.imbalance_mode.upper()}")
        
        storage = f"sqlite:///{os.path.join(results_dir, 'study.db')}"
        # ⭐️ [V14] study_name 변경 (v14_custom_score)
        study_name = f"{version}_custom_score_search_v14_final" 
        
        pruner   = PercentilePruner(percentile=25.0, n_startup_trials=5, n_warmup_steps=10); seed = SEED + hash(arch) % 1000
        sampler  = TPESampler(seed=seed, n_startup_trials=5); log("-> Pruner(25%, startup 5, warmup 10), Sampler(TPE, startup 5) 설정")
        
        study = optuna.create_study(study_name=study_name, storage=storage, load_if_exists=True, sampler=sampler, direction="maximize", pruner=pruner)
        
        tried = len(study.trials); done = len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]); remain= max(0, args.trials - tried)
        log(f"-> 저장소: {storage} | 완료 {done}/{args.trials} (총 시도 {tried}, 남음 {remain})")
        
        if remain > 0:
            try: 
                study.optimize(
                    lambda t: objective(t, arch, splits_processed, args.imbalance_mode, X_val_max, y_val), 
                    n_trials=remain, 
                    show_progress_bar=True
                )
            except Exception as e: log(f"[{arch}] 최적화 중단: {e}")
        else: log("-> 이미 목표 횟수 달성. 건너뜀.")

        # 6. ⭐️ [V25] 결과 저장
        log("\n✅ [7/7] 1등 레시피 및 스케일러 저장 중...");
        try: best_trial = study.best_trial; best_value = best_trial.value; best_params = best_trial.params
        except Exception: log(f"[{arch}] Best trial 없음. 건너뜀."); continue
        
        best_params["best_validation_score"] = float(best_value)
        
        joblib.dump(scaler, os.path.join(results_dir, "final_scaler.pkl"))
        
        with open(os.path.join(results_dir, "best_params.json"), "w", encoding="utf-8") as f: json.dump(best_params, f, ensure_ascii=False, indent=2)
        with open(os.path.join(results_dir, "feature_order.json"), "w", encoding="utf-8") as f:
            json.dump({"ALL_FEATURES": FEATURE_COLS, "TEMPORAL_COLS": TEMPORAL_COLS, "STATIC_COLS": STATIC_COLS}, f, indent=2)
        log(f"-> 1등 레시피 및 ⭐️스케일러⭐️ 저장 완료: {results_dir}")

        # ⭐️ [V14] 로그 수정
        log("\n--- 최적 Trial 정보 (Objective: Val Custom Score) ---"); log(f" Best CustomScore: {study.best_value:.5f}")
        for k, v in best_params.items(): log(f"   {k}: {v}")
        log(f"\n🎉 [{arch.upper()}] 튜닝 완료 (최종 학습은 1.5 스크립트에서 진행).")

if __name__ == "__main__":
    main()
