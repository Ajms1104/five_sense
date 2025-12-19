# -*- coding: utf-8 -*-
# phase1_quantile_v20.py
# ⭐️ v20: Q50 중앙 예측 + 비대칭 Head 구조로 수정
# ⭐️ TCN + Transformer 아키텍처 추가 (총 6개)
from __future__ import annotations

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

import tensorflow as tf
import tensorflow.keras as K
from tensorflow.keras import layers as KL
from tensorflow.keras import models as KM
from tensorflow.keras import optimizers as KO

import optuna
from optuna.samplers import TPESampler
from optuna.pruners import PercentilePruner

warnings.filterwarnings("ignore")

# =============================================================================
# 설정
# =============================================================================
SEED = 42
np.random.seed(SEED); random.seed(SEED); tf.random.set_seed(SEED)
try:
    gpus = tf.config.list_physical_devices("GPU")
    for g in gpus: tf.config.experimental.set_memory_growth(g, True)
    if gpus: print(f"-> {len(gpus)}개 GPU 메모리 증가 설정 완료.")
except Exception as e: print(f"-> 경고: GPU 메모리 설정 중 오류: {e}")

RETURN_SCALE = 100.0
QUANTILES = [0.1, 0.5, 0.9] # ⭐️ 3개 퀀타일 고정 (새로운 Head 구조)
CROSSING_LAMBDA = 0.0

# ⭐️⭐️⭐️ [핵심 수정] 버전 v20으로 변경 ⭐️⭐️⭐️
BASE_RESULTS_DIR = "experiments_v20_quantile_regression" # 버전업
PREPROCESSED_DATA_DIR = "preprocessed_dfs"

def ensure_dir(p: str): os.makedirs(p, exist_ok=True)
def log(msg: str): print(msg, flush=True)

# =============================================================================
# config.py (이전과 동일)
# =============================================================================
try:
    from config import FEATURE_COLS, TEMPORAL_COLS, STATIC_COLS
except ImportError:
    print("오류: config.py 또는 FEATURE_COLS/TEMPORAL_COLS/STATIC_COLS를 찾을 수 없습니다.", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# 데이터 로딩 (이전과 동일)
# =============================================================================
@dataclass
class DataSplits:
    train_df: pd.DataFrame; val_df: pd.DataFrame; test_df: pd.DataFrame
    feature_cols: List[str]; scaler: RobustScaler

def load_data_from_files(data_dir: str) -> DataSplits:
    log(f"✅ [1/6] Phase0 산출물 로딩: {data_dir}")
    try:
        train_df = pd.read_pickle(os.path.join(data_dir, "train_df_scaled.pkl"))
        val_df   = pd.read_pickle(os.path.join(data_dir, "val_df_scaled.pkl"))
        test_df  = pd.read_pickle(os.path.join(data_dir, "test_df_scaled.pkl"))
        scaler   = joblib.load(os.path.join(data_dir, 'final_scaler.pkl'))
    except FileNotFoundError as e:
        log(f"-> 로딩 실패: {e}"); sys.exit(1)
    def _info(name, df):
        if df.empty: log(f"RAW/{name}: EMPTY"); return
        d0, d1 = df["date"].min(), df["date"].max()
        pr = df["direction"].mean() if "direction" in df.columns else np.nan
        log(f"RAW/{name}: {d0.date()} ~ {d1.date()} rows={len(df):,} pos_rate={pr:.3f}")
    _info("Train", train_df); _info("Val", val_df); _info("Test", test_df)
    return DataSplits(train_df, val_df, test_df, FEATURE_COLS, scaler)

# =============================================================================
# 시퀀스 생성 (이전과 동일)
# =============================================================================
def create_sequences_regression(
    df: pd.DataFrame,
    seq_length: int,
    temporal_cols: List[str]
) -> Tuple[np.ndarray, np.ndarray]:
    X_temporal, y_return = [], []
    for code in df["stock_code"].unique():
        sdf = df[df["stock_code"] == code].sort_values("date")
        temp = sdf[temporal_cols].values; ret  = sdf["return"].values
        if len(temp) <= seq_length: continue
        nseq = len(temp) - seq_length
        for i in range(nseq):
            X_temporal.append(temp[i:i+seq_length])
            y_return.append(ret[i+seq_length] * RETURN_SCALE)
    X_temporal = np.asarray(X_temporal, dtype=np.float32) if len(X_temporal) else np.empty((0, seq_length, len(temporal_cols)), dtype=np.float32)
    y_return   = np.asarray(y_return, dtype=np.float32)   if len(y_return)   else np.empty((0,), dtype=np.float32)
    return X_temporal, y_return

# =============================================================================
# ⭐️⭐️⭐️ Body 빌더들 (TCN + Transformer 추가) ⭐️⭐️⭐️
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
    x = KL.Conv1D(params.get("cnn_filters", 64), params.get("cnn_kernel_size", 3), padding="same", activation="relu")(inp)
    x = KL.MaxPooling1D()(x)
    n_layers = params.get("n_layers", 1); units = params.get("lstm_units", 128); use_attn = params.get("use_attention", False)
    for i in range(n_layers): rs = (i < n_layers - 1) or use_attn; x = KL.LSTM(units, return_sequences=rs)(x)
    if use_attn and len(x.shape) == 3:
        heads = params.get("num_heads_cnn", 2); key_dim = max(1, units // heads)
        attn = KL.MultiHeadAttention(num_heads=heads, key_dim=key_dim); x = attn(query=x, value=x, key=x)
        if len(x.shape) == 3: x = KL.GlobalAveragePooling1D()(x)
    return inp, x

# ⭐️ [TCN] TCN 잔차 블록 (동일)
def TCNResidualBlock(n_filters, kernel_size, dilation_rate):
    def build_block(inputs):
        x = inputs
        x = KL.Conv1D(filters=n_filters, kernel_size=kernel_size, dilation_rate=dilation_rate, padding='causal', kernel_initializer='he_normal')(x)
        x = KL.BatchNormalization()(x); x = KL.Activation('relu')(x); x = KL.Dropout(0.3)(x)
        x = KL.Conv1D(filters=n_filters, kernel_size=kernel_size, dilation_rate=dilation_rate, padding='causal', kernel_initializer='he_normal')(x)
        x = KL.BatchNormalization()(x); x = KL.Activation('relu')(x); x = KL.Dropout(0.3)(x)
        if inputs.shape[-1] != n_filters: shortcut = KL.Conv1D(filters=n_filters, kernel_size=1, padding='same')(inputs)
        else: shortcut = inputs
        x = KL.Add()([shortcut, x]); x = KL.Activation('relu')(x)
        return x
    return build_block

# ⭐️ [TCN] TCN Body 빌더 (동일)
def build_tcn_body(input_shape: Tuple[int, int], params: Dict[str, Any]) -> Tuple[tf.Tensor, tf.Tensor]:
    inp = KL.Input(shape=input_shape, name="temporal_input"); x = inp
    n_filters = params.get("tcn_filters", 64); kernel_size = params.get("tcn_kernel_size", 3)
    n_blocks = params.get("tcn_n_blocks", 2); dilation_base = params.get("tcn_dilation_base", 2)
    x = KL.Conv1D(n_filters, 1, padding='same')(x) 
    for i in range(n_blocks):
        dilation_rate = dilation_base ** i
        x = TCNResidualBlock(n_filters, kernel_size, dilation_rate)(x)
    x = KL.GlobalAveragePooling1D()(x) 
    return inp, x

# ⭐️⭐️⭐️ [Transformer 추가] Positional Encoding ⭐️⭐️⭐️
class PositionalEncoding(KL.Layer):
    def __init__(self, position, d_model, **kwargs):
        super(PositionalEncoding, self).__init__(**kwargs)
        self.position = position
        self.d_model = d_model
        pos_encoding = self.build_encoding(position, d_model)
        self.pos_encoding = tf.cast(pos_encoding, dtype=tf.float32)

    def build_encoding(self, position, d_model):
        angle_rads = self.get_angles(np.arange(position)[:, np.newaxis],
                                     np.arange(d_model)[np.newaxis, :],
                                     d_model)
        angle_rads[:, 0::2] = np.sin(angle_rads[:, 0::2])
        angle_rads[:, 1::2] = np.cos(angle_rads[:, 1::2])
        pos_encoding = angle_rads[np.newaxis, ...]
        return pos_encoding

    def get_angles(self, pos, i, d_model):
        angle_rates = 1 / np.power(10000, (2 * (i // 2)) / np.float32(d_model))
        return pos * angle_rates

    def call(self, inputs):
        seq_len = tf.shape(inputs)[1]
        return inputs + self.pos_encoding[:, :seq_len, :]

# ⭐️⭐️⭐️ [Transformer 추가] Transformer Encoder Block ⭐️⭐️⭐️
def transformer_encoder_block(inputs, d_model, num_heads, dff, dropout_rate):
    attn_output = KL.MultiHeadAttention(
        num_heads=num_heads, key_dim=d_model // num_heads, dropout=dropout_rate
    )(inputs, inputs)
    attn_output = KL.LayerNormalization(epsilon=1e-6)(inputs + attn_output)
    ffn_output = KL.Dense(dff, activation="relu")(attn_output)
    ffn_output = KL.Dense(d_model)(ffn_output)
    ffn_output = KL.Dropout(dropout_rate)(ffn_output)
    output = KL.LayerNormalization(epsilon=1e-6)(attn_output + ffn_output)
    return output

# ⭐️⭐️⭐️ [Transformer 추가] Transformer Body 빌더 ⭐️⭐️⭐️
def build_transformer_body(input_shape: Tuple[int, int], params: Dict[str, Any]) -> Tuple[tf.Tensor, tf.Tensor]:
    seq_len, num_features = input_shape
    
    d_model = params.get("d_model", 128) 
    num_heads = params.get("num_heads", 4)
    dff = params.get("dff", d_model * 2)
    n_blocks = params.get("transformer_n_blocks", 2)
    dropout_rate = params.get("dropout_rate", 0.3)
    
    inp = KL.Input(shape=input_shape, name="temporal_input")
    
    # 1. 입력 차원(num_features)을 d_model로 매핑
    x = KL.Conv1D(filters=d_model, kernel_size=1, activation="relu")(inp)
    
    # 2. Positional Encoding
    max_seq_len_for_pe = 512 # 넉넉하게
    x = PositionalEncoding(position=max_seq_len_for_pe, d_model=d_model)(x)
    x = KL.Dropout(dropout_rate)(x)

    # 3. 인코더 블록 스택
    for _ in range(n_blocks):
        x = transformer_encoder_block(x, d_model, num_heads, dff, dropout_rate)
    
    # 4. Global Average Pooling
    x = KL.GlobalAveragePooling1D()(x)
    
    # 5. (inp, body_output) 반환
    return inp, x
# ⭐️⭐️⭐️ [Transformer 추가] 끝 ⭐️⭐️⭐️

# =============================================================================
# Quantile Head (이전과 동일)
# =============================================================================
def head_quantile(x: tf.Tensor, params: Dict[str, Any]) -> tf.Tensor:
    if len(QUANTILES) != 3:
        raise ValueError("이 Head 구조는 QUANTILES = [Q10, Q50, Q90] (3개)일 때만 작동합니다.")
    dr = params.get("dropout_rate", 0.3); L = params.get("dense_layers", 1)
    H = params.get("dense_units", 128); act = params.get("activation", "relu")
    h = KL.Dropout(dr)(x)
    for _ in range(L): h = KL.Dense(H, activation=act)(h); h = KL.Dropout(dr)(h)
    q50 = KL.Dense(1, name="q50_center")(h)
    delta_q10 = KL.Dense(1, name="q10_delta")(h)
    delta_q10_pos = KL.Activation("softplus", name="q10_delta_pos")(delta_q10)
    q10 = KL.Subtract(name="q10_output")([q50, delta_q10_pos])
    delta_q90 = KL.Dense(1, name="q90_delta")(h)
    delta_q90_pos = KL.Activation("softplus", name="q90_delta_pos")(delta_q90)
    q90 = KL.Add(name="q90_output")([q50, delta_q90_pos])
    return KL.Concatenate(name="quantile_output")([q10, q50, q90])

# ⭐️⭐️⭐️ [Transformer 추가] 모델 빌더 수정 ⭐️⭐️⭐️
def build_model_by_arch_quantile(arch: str, temporal_input_shape: Tuple[int, int], params: Dict[str, Any]) -> KM.Model:
    if arch == "lstm": inp, body = build_lstm_body(temporal_input_shape, params)
    elif arch == "bilstm": inp, body = build_bilstm_body(temporal_input_shape, params)
    elif arch == "gru": inp, body = build_gru_body(temporal_input_shape, params)
    elif arch == "cnnlstm": inp, body = build_cnnlstm_body(temporal_input_shape, params)
    elif arch == "tcn": inp, body = build_tcn_body(temporal_input_shape, params)
    elif arch == "transformer": inp, body = build_transformer_body(temporal_input_shape, params) # ⭐️ Transformer 추가
    else: raise ValueError(f"Unknown arch: {arch}")
    out = head_quantile(body, params)
    return KM.Model(inputs=inp, outputs=out, name=f"{arch.upper()}_Quantile")

# =============================================================================
# 손실/컴파일 (이전과 동일)
# =============================================================================
def quantile_loss(y_true: tf.Tensor, y_pred: tf.Tensor,
                  quantiles: List[float] = QUANTILES,
                  crossing_lambda: float = CROSSING_LAMBDA) -> tf.Tensor:
    q = tf.constant(quantiles, dtype=tf.float32); yt = tf.cast(y_true, tf.float32); yp = tf.cast(y_pred, tf.float32)
    if tf.rank(yt) == 1: yt = tf.expand_dims(yt, -1)
    yt = tf.tile(yt, [1, tf.shape(yp)[1]])
    e = yt - yp
    pinball = tf.reduce_mean(tf.maximum(q * e, (q - 1.0) * e))
    if crossing_lambda > 0.0 and len(quantiles) >= 2:
        diffs = yp[:, :-1] - yp[:, 1:];
        xpen = tf.reduce_mean(tf.nn.relu(diffs))
        return pinball + crossing_lambda * xpen
    return pinball

def compile_model_quantile(model: KM.Model, lr: float) -> KM.Model:
    loss_fn = lambda yt, yp: quantile_loss(yt, yp, QUANTILES, CROSSING_LAMBDA)
    model.compile(optimizer=KO.Adam(learning_rate=lr), loss=loss_fn, metrics=[K.metrics.MeanAbsoluteError(name="mae")])
    return model

# =============================================================================
# 평가/진단 (이전과 동일)
# =============================================================================
def evaluate_avg_quantile_loss(model: KM.Model, X_val: np.ndarray, y_val: np.ndarray) -> float:
    if X_val.shape[0] == 0 or y_val.shape[0] == 0: return float('inf')
    yq = model.predict(X_val, verbose=0, batch_size=1024)
    if y_val.ndim == 1: y_val = y_val[:, np.newaxis]
    loss = quantile_loss(tf.constant(y_val, tf.float32), tf.constant(yq, tf.float32)).numpy()
    return float(loss) if np.isfinite(loss) else float("inf")

def compute_quantile_diagnostics(y_true: np.ndarray, yq: np.ndarray) -> Dict[str, float]:
    if y_true.ndim == 2: y_true = y_true[:, 0]
    if yq.ndim != 2 or yq.shape[1] != len(QUANTILES): return dict(pinball=float("inf"), picp=0.0, mpiw=float("inf"), medae=float("inf"), noncross_rate=0.0)
    qs = np.array(QUANTILES, dtype=np.float32); e = (y_true[:, None] - yq)
    pinball = np.mean(np.maximum(qs * e, (qs - 1.0) * e))
    low_idx = 0; high_idx = len(QUANTILES) - 1
    ql = yq[:, low_idx]; qh = yq[:, high_idx]
    picp = np.mean((y_true >= ql) & (y_true <= qh)); mpiw = np.mean(qh - ql)
    med_idx = len(QUANTILES) // 2
    medae = np.median(np.abs(y_true - yq[:, med_idx]))
    noncross = np.mean(np.all(np.diff(yq, axis=1) >= -1e-8, axis=1))
    return dict(pinball=float(pinball), picp=float(picp), mpiw=float(mpiw), medae=float(medae), noncross_rate=float(noncross))

def evaluate_on_split(model: KM.Model, X_fit: np.ndarray, y_true: np.ndarray, name: str) -> None:
    yq = model.predict(X_fit, verbose=0, batch_size=1024)
    diag = compute_quantile_diagnostics(y_true.squeeze(), yq)
    log(f"[Diag/{name}] pinball={diag['pinball']:.5f} | PICP(10-90)={diag['picp']:.3f} | "
        f"MPIW={diag['mpiw']:.3f} | MedAE(Q50)={diag['medae']:.4f} | noncross={diag['noncross_rate']:.3f}")

# =============================================================================
# ⭐️⭐️⭐️ Optuna (Transformer 추가) ⭐️⭐️⭐️
# =============================================================================
def suggest_params(trial: optuna.trial.Trial, arch: str) -> Dict[str, Any]:
    p: Dict[str, Any] = {}; p["learning_rate"] = trial.suggest_float("learning_rate", 1e-4, 1e-2, log=True)
    p["activation"] = trial.suggest_categorical("activation", ["relu","gelu","tanh"]);
    p["dropout_rate"] = trial.suggest_float("dropout_rate", 0.4, 0.7)
    p["dense_layers"] = trial.suggest_int("dense_layers", 1, 2); p["dense_units"] = trial.suggest_categorical("dense_units", [128,256])
    p["batch_size"] = trial.suggest_categorical("batch_size", [32, 64, 128]);
    p["seq_length"] = trial.suggest_int("seq_length", 64, 240)

    if arch == "lstm": p["lstm_n_layers"]=trial.suggest_int("lstm_n_layers", 2, 4); p["lstm_units"]=trial.suggest_categorical("lstm_units", [64, 128, 256])
    elif arch == "bilstm": p["bilstm_n_layers"]=trial.suggest_int("bilstm_n_layers", 2, 4); p["bilstm_units"]=trial.suggest_categorical("bilstm_units", [64, 128, 256])
    elif arch == "gru": p["gru_n_layers"]=trial.suggest_int("gru_n_layers", 2, 4); p["gru_units"]=trial.suggest_categorical("gru_units", [64, 128, 256])
    elif arch == "cnnlstm":
        p["n_layers"]=trial.suggest_int("n_layers", 1, 2); p["lstm_units"]=trial.suggest_categorical("lstm_units", [128,256])
        p["cnn_filters"]=trial.suggest_categorical("cnn_filters", [64,128,256]); p["cnn_kernel_size"]=trial.suggest_categorical("cnn_kernel_size", [3,5])
        p["use_attention"]=trial.suggest_categorical("use_attention", [False,True])
        if p["use_attention"]: p["num_heads_cnn"]=trial.suggest_categorical("num_heads_cnn",[2,4])
    elif arch=="tcn":
        p["tcn_filters"] = trial.suggest_categorical("tcn_filters", [32, 64, 128])
        p["tcn_kernel_size"] = trial.suggest_categorical("tcn_kernel_size", [2, 3, 5])
        p["tcn_n_blocks"] = trial.suggest_int("tcn_n_blocks", 2, 4)
        p["tcn_dilation_base"] = trial.suggest_categorical("tcn_dilation_base", [2, 3])
    # ⭐️⭐️⭐️ [Transformer 추가] Transformer 하이퍼파라미터 ⭐️⭐️⭐️
    elif arch=="transformer":
        p["d_model"] = trial.suggest_categorical("d_model", [64, 128]) # OOM 방지
        p["num_heads"] = trial.suggest_categorical("num_heads", [2, 4, 8])
        p["transformer_n_blocks"] = trial.suggest_int("transformer_n_blocks", 1, 3)
        p["dff"] = p["d_model"] * trial.suggest_categorical("dff_multiplier", [2, 4])
    return p

def objective(trial: optuna.trial.Trial, arch: str, splits: DataSplits) -> float:
    train_df, val_df = splits.train_df, splits.val_df
    version = f"v20_{arch}_quantile_regression"; results_dir = os.path.join(BASE_RESULTS_DIR, version); best_log_file = os.path.join(results_dir, "best_trials_log.txt")
    try: params = suggest_params(trial, arch)
    except Exception as e: log(f"파라미터 제안 실패: {e}"); raise optuna.exceptions.TrialPruned()
    seq_len, bs = params["seq_length"], params["batch_size"]

    log(f"-> [Trial {trial.number}] 시퀀스 생성 (SeqLen={seq_len})")
    try:
        Xtr_t, ytr = create_sequences_regression(train_df, seq_len, TEMPORAL_COLS)
        Xva_t, yva = create_sequences_regression(val_df,   seq_len, TEMPORAL_COLS)
    except Exception as e: log(f"시퀀스 생성 오류: {e}. Pruned."); raise optuna.exceptions.TrialPruned()

    if Xtr_t.shape[0] == 0 or Xva_t.shape[0] == 0: log("시퀀스 0개. Pruned."); raise optuna.exceptions.TrialPruned()
    log(f"-> [Trial {trial.number}] 생성 완료. (Train shape: {Xtr_t.shape}, Val shape: {Xva_t.shape})")

    if ytr.ndim == 1: ytr = ytr[:, np.newaxis]
    if yva.ndim == 1: yva = yva[:, np.newaxis]

    temporal_input_shape = (seq_len, len(TEMPORAL_COLS))
    model = build_model_by_arch_quantile(arch, temporal_input_shape, params)
    model = compile_model_quantile(model, lr=params["learning_rate"])

    cbs = [ K.callbacks.EarlyStopping(monitor="val_loss", patience=5, mode="min", restore_best_weights=True, verbose=1),
            K.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=3, mode="min", min_lr=1e-6, verbose=1),
            optuna.integration.TFKerasPruningCallback(trial, "val_loss") ]

    log(f"✅ [Trial {trial.number}] 학습 시작... (Arch={arch}, BS={bs}, Patience=5)")
    Xtr_fit, Xva_fit = Xtr_t, Xva_t
    try: model.fit( Xtr_fit, ytr, validation_data=(Xva_fit, yva), epochs=100, batch_size=bs, verbose=1, callbacks=cbs )
    except optuna.exceptions.TrialPruned as e: log(f"-> [Trial {trial.number}] Pruned."); raise e
    except Exception as e: log(f"학습 중 에러: {e}. Pruned."); tf.keras.backend.clear_session(); raise optuna.exceptions.TrialPruned()

    log("✅ 검증 평균 퀀타일 손실 계산..."); avg_loss = evaluate_avg_quantile_loss(model, Xva_fit, yva)
    log(f"-> Trial {trial.number} Val Avg Quantile Loss: {avg_loss:.5f}")

    trial.set_user_attr("best_validation_score", float(avg_loss)) # 저장용

    current_best_loss = float('inf')
    try: current_best_loss = trial.study.best_value if trial.study.best_value is not None else float('inf')
    except ValueError: pass
    is_best = bool(avg_loss is not None and not math.isnan(avg_loss) and not math.isinf(avg_loss) and avg_loss <= current_best_loss)
    if is_best: # (로그 기록 로직)
        log_msg = f"✨ New Best Loss Found! ✨ Trial {trial.number}: {avg_loss:.5f}\n"; param_str = f"   ㄴ Params: LR={params['learning_rate']:.5f}, SeqLen={params['seq_length']}, BS={params['batch_size']}"
        if arch == 'lstm': param_str += f", Layers={params['lstm_n_layers']}, Units={params['lstm_units']}"
        elif arch == 'bilstm': param_str += f", Layers={params['bilstm_n_layers']}, Units={params['bilstm_units']}"
        elif arch == 'gru': param_str += f", Layers={params['gru_n_layers']}, Units={params['gru_units']}"
        elif arch == 'cnnlstm': param_str += f", Layers={params['n_layers']}, Units={params['lstm_units']}, Filters={params['cnn_filters']}, Kernel={params['cnn_kernel_size']}";
        elif arch == 'tcn': param_str += f", Filters={params['tcn_filters']}, Kernel={params['tcn_kernel_size']}, Blocks={params['tcn_n_blocks']}, Base={params['tcn_dilation_base']}"
        # ⭐️⭐️⭐️ [Transformer 추가] Transformer 로그 ⭐️⭐️⭐️
        elif arch == 'transformer':
            param_str += f", d_model={params['d_model']}, n_heads={params['num_heads']}, n_blocks={params['transformer_n_blocks']}, dff={params['dff']}"
        log_msg += param_str; log(log_msg)
        try:
            with open(best_log_file, "a", encoding="utf-8") as f:
                import datetime; timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] Trial {trial.number} - New Best Loss: {avg_loss:.5f}\n")
                f.write(f"  Params: {json.dumps(params, indent=2)}\n"); f.write("-" * 30 + "\n")
        except Exception as e: log(f"경고: 최고 기록 로그 파일 저장 실패 - {e}")
        
    del model, Xtr_t, ytr, Xva_t, yva, Xtr_fit, Xva_fit
    tf.keras.backend.clear_session()
    return float(avg_loss) if np.isfinite(avg_loss) else float("inf")

# ====== 메인 (⭐️ [수정] 최종 학습 삭제) ======
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", type=str, default=BASE_RESULTS_DIR)
    parser.add_argument("--arches", nargs="*", default=["lstm","bilstm","gru","cnnlstm", "tcn", "transformer"])
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--data_dir", type=str, default=PREPROCESSED_DATA_DIR)
    args = parser.parse_args()

    splits = load_data_from_files(args.data_dir)
    for arch in args.arches:
        version = f"v20_{arch}_quantile_regression"; results_dir = os.path.join(args.results_dir, version); ensure_dir(results_dir)
        log("="*60 + f"\n🚀 Architecture: {arch.upper()} | Version: {version}")
        storage = f"sqlite:///{os.path.join(results_dir, 'study.db')}"
        study_name = f"{version}_loss_search"
        pruner   = PercentilePruner(percentile=25.0, n_startup_trials=5, n_warmup_steps=10)
        seed     = SEED + hash(arch) % 1000 + 20
        sampler  = TPESampler(seed=seed, n_startup_trials=5)
        log("-> Pruner(25%, startup 5, warmup 10), Sampler(TPE, startup 5) 설정")
        study = optuna.create_study(study_name=study_name, storage=storage, load_if_exists=True, sampler=sampler, direction="minimize", pruner=pruner)
        tried = len(study.trials); done = len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]); remain= max(0, args.trials - tried)
        log(f"-> 저장소: {storage} | 완료 {done}/{args.trials} (총 시도 {tried}, 남음 {remain})")
        
        if remain > 0:
            try: study.optimize(lambda t: objective(t, arch, splits), n_trials=remain, show_progress_bar=True)
            except Exception as e: log(f"[{arch}] 최적화 중단: {e}")
        else: log("-> 이미 목표 횟수 달성. 건너뜀.")

        log("✅ [마감] 1등 레시피 저장 중...")
        try: best_trial = study.best_trial; best_value = best_trial.value; best_params = best_trial.params
        except Exception: log(f"[{arch}] Best trial 없음. 건너뜀."); continue

        best_params["best_validation_score"] = float(best_value)

        # ⭐️ 튜닝 직후 'best_params.json'과 스케일러, 피처 정보 저장
        joblib.dump(splits.scaler, os.path.join(results_dir, "final_scaler.pkl"))
        with open(os.path.join(results_dir, "best_params.json"), "w", encoding="utf-8") as f: 
            json.dump(best_params, f, ensure_ascii=False, indent=2)
        with open(os.path.join(results_dir, "feature_order.json"), "w", encoding="utf-8") as f:
            json.dump({"ALL_FEATURES": FEATURE_COLS, "TEMPORAL_COLS": TEMPORAL_COLS, "STATIC_COLS": STATIC_COLS}, f, indent=2)
        
        log(f"-> 1등 레시피 저장 완료: {os.path.join(results_dir, 'best_params.json')}")

        # ===== [최종 학습 블록 삭제] =====
        # (NPY 데이터 생성, final.fit(), final.save() 등 모두 삭제)
        # (이 스크립트의 임무는 best_params.json을 찾는 것까지입니다.)
        # (실제 모델 훈련/저장은 phase1_5_repeat_and_select_QUANTILE.py가 담당합니다.)

        log("\n--- 최적 Trial 정보 (Objective: Avg Quantile Loss) ---")
        log(f" Best Loss: {study.best_value:.5f}")
        for k, v in best_params.items(): log(f"   {k}: {v}")
        
        log(f"\n🎉 [{arch.upper()}] 튜닝 완료 (최종 학습은 1.5 스크립트에서 진행).")

if __name__ == "__main__":
    # ⭐️ (참고) 이 스크립트를 실행하기 전에, 
    # ⭐️ 원본 'phase1_quantile_v20.py'의 모든 함수(def, class)를 
    # ⭐️ 이 'main()' 함수 위에 복사-붙여넣기 해야 합니다.
    main()
