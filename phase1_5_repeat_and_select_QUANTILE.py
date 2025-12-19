# -*- coding: utf-8 -*-
# phase1_5_repeat_and_select_QUANTILE.py
# ⭐️ [완전체] 변동성(퀀타일) 챔피언 선발 스크립트
# ⭐️ [수정 4] 챔피언의 "Seed"를 best_params.json에 저장

from __future__ import annotations

# ====== 환경 설정 ======
import os
os.environ['PYTHONHASHSEED'] = '42'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import sys, json, math, warnings, random, shutil
import argparse # ⭐️ argparse import
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
from tensorflow.keras import losses as KLoss

warnings.filterwarnings("ignore")

# ====== config (Phase 1과 동일) ======
try:
    from config import FEATURE_COLS, TEMPORAL_COLS, STATIC_COLS
except ImportError:
    print("오류: config.py 혹은 FEATURE_COLS/TEMPORAL_COLS/STATIC_COLS 미존재", file=sys.stderr)
    sys.exit(1)

SEED = 42
QUANTILES = [0.1, 0.5, 0.9]
RETURN_SCALE = 100.0 # ⭐️ (버그 수정됨)

BASE_RESULTS_DIR = 'experiments_v20_quantile_regression' # ⭐️ 퀀타일 모델 경로
PREPROCESSED_DATA_DIR = 'preprocessed_dfs'
DEFAULT_ARCHS = ["lstm", "bilstm", "gru", "cnnlstm", "tcn", "transformer"]

try:
    gpus = tf.config.list_physical_devices('GPU')
    for gpu in gpus: tf.config.experimental.set_memory_growth(gpu, True)
    if gpus: print(f"-> {len(gpus)}개 GPU 메모리 증가 설정 완료.")
except Exception as e:
    print(f"-> 경고: GPU 메모리 설정 중 오류: {e}")

def log(msg: str): print(msg, flush=True)
def ensure_dir(p: str): os.makedirs(p, exist_ok=True)
def set_seed(run_seed):
    os.environ['PYTHONHASHSEED'] = str(run_seed)
    np.random.seed(run_seed); random.seed(run_seed); tf.random.set_seed(run_seed)
    log(f"   -> Run Seed 고정: {run_seed}")

# 요약 로그를 파일에 추가하는 함수
def log_summary_to_file(msg: str, file_path: str):
    log(msg) 
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
    except Exception as e:
        log(f"-> 경고: 요약 로그 파일 쓰기 실패: {e}")

# NumPy Pinball Loss
def numpy_quantile_loss(y_true: np.ndarray, y_pred_quantiles: np.ndarray, 
                        quantiles: List[float] = QUANTILES) -> float:
    if y_true.ndim == 1:
        y_true = y_true.reshape(-1, 1) 
    if y_pred_quantiles.ndim == 1:
        num_quantiles = len(quantiles)
        if y_pred_quantiles.shape[0] % num_quantiles == 0:
             y_pred_quantiles = y_pred_quantiles.reshape(-1, num_quantiles)
        else: 
             if num_quantiles == 1:
                 y_pred_quantiles = y_pred_quantiles.reshape(-1, 1)
             else: 
                 raise ValueError(f"y_pred_quantiles shape {y_pred_quantiles.shape} is not compatible with {num_quantiles} quantiles.")

    q = np.array(quantiles, dtype=np.float32) 
    e = y_true - y_pred_quantiles 
    pinball = np.maximum(q * e, (q - 1.0) * e)
    return float(np.mean(pinball)) # ⭐️ JSON 저장을 위해 python float으로 변환

# ====== ⭐️ (시작) 헬퍼 함수 (phase1_quantile_v20.py에서 복사) ⭐️ ======
@dataclass
class DataSplits:
    train_df: pd.DataFrame; val_df: pd.DataFrame; test_df: pd.DataFrame
    feature_cols: List[str]; scaler: RobustScaler

def load_data_from_files(data_dir: str) -> DataSplits:
    log(f"✅ [1/5] Phase0 산출물 로딩: {data_dir}")
    try:
        train_df = pd.read_pickle(os.path.join(data_dir, "train_df_scaled.pkl"))
        val_df   = pd.read_pickle(os.path.join(data_dir, "val_df_scaled.pkl"))
        test_df  = pd.read_pickle(os.path.join(data_dir, "test_df_scaled.pkl"))
        scaler   = joblib.load(os.path.join(data_dir, 'final_scaler.pkl'))
    except FileNotFoundError as e:
        log(f"-> 로딩 실패: {e}"); sys.exit(1)
    return DataSplits(train_df, val_df, test_df, FEATURE_COLS, scaler)

# ⭐️⭐️⭐️ [버그 수정] 퀀타일용 시퀀스 생성 (y_target에 100 곱하기)
def create_sequences_quantile(df: pd.DataFrame, seq_length: int,
                             temporal_cols: List[str], static_cols: List[str]):
    X_temporal, y_target = [], []
    for code, stock_df in df.groupby('stock_code'):
        stock_df = stock_df.sort_values('date')
        temp = stock_df[temporal_cols].values
        ret  = stock_df['return'].values 
        if len(temp) <= seq_length: continue
        nseq = len(temp) - seq_length
        for i in range(nseq):
            X_temporal.append(temp[i:i+seq_length])
            y_target.append(ret[i+seq_length] * RETURN_SCALE) 
    X_temporal = np.asarray(X_temporal, dtype=np.float32)
    X_static   = np.empty((len(X_temporal), 0), dtype=np.float32)
    y_target   = np.asarray(y_target, dtype=np.float32).reshape(-1, 1)
    return X_temporal, X_static, y_target

# 퀀타일 모델용 헤드 (v20 구조)
def head_quantile(x, p):
    x = KL.Dropout(p.get("dropout_rate",0.3))(x)
    for _ in range(p.get("dense_layers",1)):
        x = KL.Dense(p.get("dense_units",128), activation=p.get("activation","relu"))(x)
        x = KL.Dropout(p.get("dropout_rate",0.3))(x)
    
    h = x # 공통 특징 추출기
    q50 = KL.Dense(1, name="q50_center")(h)
    delta_q10 = KL.Dense(1, name="q10_delta")(h)
    delta_q10_pos = KL.Activation("softplus", name="q10_delta_pos")(delta_q10)
    q10 = KL.Subtract(name="q10_output")([q50, delta_q10_pos])
    delta_q90 = KL.Dense(1, name="q90_delta")(h)
    delta_q90_pos = KL.Activation("softplus", name="q90_delta_pos")(delta_q90)
    q90 = KL.Add(name="q90_output")([q50, delta_q90_pos])
    return KL.Concatenate(name="quantile_output")([q10, q50, q90])

def build_lstm(input_shape, p):
    inp = KL.Input(shape=input_shape); x = inp
    for i in range(p.get("lstm_n_layers",2)):
        x = KL.LSTM(p.get("lstm_units",128), return_sequences=(i<p.get("lstm_n_layers",2)-1))(x)
    out = head_quantile(x,p); return KM.Model(inp, out, name="LSTM") 

def build_bilstm(input_shape, p):
    inp = KL.Input(shape=input_shape); x = inp
    for i in range(p.get("bilstm_n_layers",2)):
        x = KL.Bidirectional(KL.LSTM(p.get("bilstm_units",128), return_sequences=(i<p.get("bilstm_n_layers",2)-1)))(x)
    out = head_quantile(x,p); return KM.Model(inp,out,name="BiLSTM") 

def build_gru(input_shape, p):
    inp = KL.Input(shape=input_shape); x = inp
    for i in range(p.get("gru_n_layers",2)):
        x = KL.GRU(p.get("gru_units",128), return_sequences=(i<p.get("gru_n_layers",2)-1))(x)
    out = head_quantile(x,p); return KM.Model(inp,out,name="GRU") 

def build_cnnlstm(input_shape, p):
    inp = KL.Input(shape=input_shape)
    x = KL.Conv1D(p.get("cnn_filters",64), p.get("cnn_kernel_size",3), padding="same", activation="relu")(inp)
    x = KL.MaxPooling1D()(x)
    for i in range(p.get("n_layers",1)):
        x = KL.LSTM(p.get("lstm_units",128), return_sequences=(i<p.get("n_layers",1)-1 or p.get("use_attention",False)))(x)
    if p.get("use_attention",False):
        try:
            num_heads = p.get("num_heads_cnn",2); key_dim = max(1, p.get("lstm_units",128)//num_heads)
            x = KL.MultiHeadAttention(num_heads=num_heads, key_dim=key_dim)(x,x)
            if len(x.shape) == 3: x = KL.GlobalAveragePooling1D()(x)
        except Exception:
             if isinstance(x, tf.Tensor) and len(x.shape) == 3: x = KL.GlobalAveragePooling1D()(x)
    out = head_quantile(x,p); return KM.Model(inp,out,name="CNNLSTM") 

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

def build_tcn(input_shape, p):
    inp = KL.Input(shape=input_shape); x = inp
    n_filters = p.get("tcn_filters", 64); kernel_size = p.get("tcn_kernel_size", 3)
    n_blocks = p.get("tcn_n_blocks", 2); dilation_base = p.get("tcn_dilation_base", 2)
    x = KL.Conv1D(n_filters, 1, padding='same')(x) 
    for i in range(n_blocks):
        dilation_rate = dilation_base ** i
        x = TCNResidualBlock(n_filters, kernel_size, dilation_rate)(x)
    x = KL.GlobalAveragePooling1D()(x) 
    out = head_quantile(x, p); return KM.Model(inp, out, name="TCN") 

@tf.keras.utils.register_keras_serializable()
class PositionalEncoding(KL.Layer):
    def __init__(self, position, d_model, **kwargs):
        super(PositionalEncoding, self).__init__(**kwargs)
        self.position = position
        self.d_model = d_model
        pos_encoding = self.build_encoding(position, d_model)
        self.pos_encoding = tf.cast(pos_encoding, dtype=tf.float32)
    def build_encoding(self, position, d_model):
        angle_rads = self.get_angles(np.arange(position)[:, np.newaxis], np.arange(d_model)[np.newaxis, :], d_model)
        angle_rads[:, 0::2] = np.sin(angle_rads[:, 0::2]); angle_rads[:, 1::2] = np.cos(angle_rads[:, 1::2])
        pos_encoding = angle_rads[np.newaxis, ...]; return pos_encoding
    def get_angles(self, pos, i, d_model):
        angle_rates = 1 / np.power(10000, (2 * (i // 2)) / np.float32(d_model)); return pos * angle_rates
    def call(self, inputs):
        seq_len = tf.shape(inputs)[1]; return inputs + self.pos_encoding[:, :seq_len, :]
    def get_config(self):
        config = super(PositionalEncoding, self).get_config(); config.update({"position": self.position, "d_model": self.d_model}); return config
        
def transformer_encoder_block(inputs, d_model, num_heads, dff, dropout_rate):
    attn_output = KL.MultiHeadAttention(num_heads=num_heads, key_dim=d_model // num_heads, dropout=dropout_rate)(inputs, inputs)
    attn_output = KL.LayerNormalization(epsilon=1e-6)(inputs + attn_output) 
    ffn_output = KL.Dense(dff, activation="relu")(attn_output); ffn_output = KL.Dense(d_model)(ffn_output); ffn_output = KL.Dropout(dropout_rate)(ffn_output)
    output = KL.LayerNormalization(epsilon=1e-6)(attn_output + ffn_output); return output

def build_transformer(input_shape, p):
    seq_len, num_features = input_shape
    d_model = p.get("d_model", 128); num_heads = p.get("num_heads", 4); dff = p.get("dff", d_model * 2) 
    n_blocks = p.get("transformer_n_blocks", 2); dropout_rate = p.get("dropout_rate", 0.3)
    inp = KL.Input(shape=input_shape)
    x = KL.Conv1D(filters=d_model, kernel_size=1, activation="relu")(inp)
    max_seq_len_for_pe = 512 
    x = PositionalEncoding(position=max_seq_len_for_pe, d_model=d_model)(x); x = KL.Dropout(dropout_rate)(x)
    for _ in range(n_blocks):
        x = transformer_encoder_block(x, d_model, num_heads, dff, dropout_rate)
    x = KL.GlobalAveragePooling1D()(x)
    out = head_quantile(x, p); return KM.Model(inp, out, name="Transformer") 

def build_model(arch, temporal_input_shape, p):
    if arch=="lstm": return build_lstm(temporal_input_shape, p)
    if arch=="bilstm": return build_bilstm(temporal_input_shape, p)
    if arch=="gru": return build_gru(temporal_input_shape, p)
    if arch=="cnnlstm": return build_cnnlstm(temporal_input_shape, p)
    if arch=="tcn": return build_tcn(temporal_input_shape, p)
    if arch=="transformer": return build_transformer(temporal_input_shape, p)
    raise ValueError(f"Unknown arch: {arch}")

@tf.keras.utils.register_keras_serializable()
def quantile_loss(y_true, y_pred, quantiles=QUANTILES):
    q = tf.constant(quantiles, dtype=tf.float32)
    y_true = tf.cast(y_true, dtype=tf.float32)
    y_pred = tf.cast(y_pred, dtype=tf.float32)
    if tf.rank(y_true) == 1:
        y_true = tf.expand_dims(y_true, -1)
    if y_true.shape[1] != y_pred.shape[1]:
         y_true = tf.tile(y_true, [1, tf.shape(y_pred)[1]])
    e = y_true - y_pred
    pinball = tf.reduce_mean(tf.maximum(q * e, (q - 1.0) * e))
    return pinball

def compile_model_quantile(model, lr: float):
    model.compile(optimizer=KO.Adam(learning_rate=lr), loss=quantile_loss, metrics=[], weighted_metrics=[])
    return model

class QuantileLossCallback(K.callbacks.Callback):
    def __init__(self, X_val, y_val_target, batch_size=1024):
        super().__init__()
        self.X_val = X_val
        self.y_val_target = y_val_target.ravel().reshape(-1, 1) 
        self.batch_size = batch_size
        self.best_loss = float('inf')

    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        if self.X_val is None or len(self.X_val) == 0:
             logs["val_pinball_loss"] = float('inf'); return
        p_val = self.model.predict(self.X_val, verbose=0, batch_size=self.batch_size)
        val_loss = numpy_quantile_loss(self.y_val_target, p_val, QUANTILES)
        logs["val_pinball_loss"] = val_loss
        if val_loss <= self.best_loss:
            self.best_loss = val_loss

def make_train_val_arrays_quantile(arch, seq_len, splits):
    Xt_tr, _, y_tr_target = create_sequences_quantile(splits.train_df, seq_len, TEMPORAL_COLS, STATIC_COLS)
    Xt_va, _, y_va_target = create_sequences_quantile(splits.val_df,   seq_len, TEMPORAL_COLS, STATIC_COLS)
    return Xt_tr, y_tr_target, Xt_va, y_va_target
# ====== ⭐️ (끝) 헬퍼 함수 (phase1_quantile_v20.py에서 복사) ⭐️ ======


# ====== [수정] 메인 로직 ======
def main():
    ap = argparse.ArgumentParser(description="Phase 1.5 [QUANTILE]: Repeat Training and Select Champion")
    ap.add_argument("--arches", nargs="*", default=DEFAULT_ARCHS, help="챔피언을 선발할 아키텍처 목록")
    ap.add_argument("--n_runs", type=int, default=5, help="반복 훈련 횟수 (N)")
    ap.add_argument("--data_dir", type=str, default=PREPROCESSED_DATA_DIR)
    args = ap.parse_args()

    n_runs = args.n_runs
    splits = load_data_from_files(args.data_dir)

    summary_log_path = os.path.join(BASE_RESULTS_DIR, "phase1_5_champion_summary_QUANTILE.txt")
    
    is_full_run = all(arch in args.arches for arch in DEFAULT_ARCHS) and len(args.arches) == len(DEFAULT_ARCHS)
    if is_full_run and os.path.exists(summary_log_path):
        try:
            os.remove(summary_log_path)
            log(f"-> 기존 요약 로그 파일 삭제: {summary_log_path}")
        except Exception as e:
            log(f"-> 경고: 기존 요약 로그 삭제 실패: {e}")

    for arch in args.arches:
        version = f"v20_{arch}_quantile_regression" 
        results_dir = os.path.join(BASE_RESULTS_DIR, version)
        params_path = os.path.join(results_dir, "best_params.json")
        final_model_path = os.path.join(results_dir, "quantile_model.h5") 
        
        log("\n" + "="*70)
        log(f"🚀 Phase 1.5 [QUANTILE]: 챔피언 선발 시작 ({arch.upper()}) | 반복 횟수: {n_runs}")
        log("="*70)

        # --- 1. 1등 레시피 로드 ---
        try:
            with open(params_path, 'r', encoding='utf-8') as f:
                best_params = json.load(f)
            log(f"✅ [1/5] 1등 레시피 로드 완료: {params_path}")
        except FileNotFoundError:
            log(f"❌ 오류: {params_path} 에서 1등 레시피를 찾을 수 없습니다.")
            log(f"-> 퀀타일 Phase 1 (튜닝)을 먼저 실행해야 합니다. {arch.upper()} 건너뜀.")
            continue 

        seq_len = best_params["seq_length"]
        bs = best_params["batch_size"]
        lr = best_params.get("learning_rate", 1e-3)

        # --- 2. "공통" Train/Val 데이터 생성 ---
        Xtr, ytr_target, Xva, yva_target = make_train_val_arrays_quantile(arch, seq_len, splits)
        if len(Xtr)==0 or len(Xva)==0:
            log(f"❌ 오류: {arch.upper()}용 Train/Val 데이터 생성 실패. 건너뜀.");
            continue
        
        log(f"✅ [2/5] 공통 Train/Val 데이터 생성 완료 (SeqLen={seq_len})")
        log(f"   -> Train: {Xtr.shape}, Val: {Xva.shape}")
        
        # --- 3. 불균형 처리 준비 (퀀타일은 불필요) ---
        log(f"✅ [3/5] 불균형 처리: (퀀타일 모델은 해당 없음)")

        # --- 4. N번 반복 훈련 및 평가 ---
        all_runs_results = []
        temp_model_paths = []
        
        log(f"\n✅ [4/5] {n_runs}회 반복 훈련 시작 (Val Pinball Loss 기준)...")
        
        for i in range(n_runs):
            run_seed = SEED + abs(hash(arch)) % 1000 + i*10 
            log("\n" + "-"*40)
            log(f"➡️  Run {i+1}/{n_runs} (Seed: {run_seed})")
            log(f"   -> {arch.upper()} 퀀타일 모델 0부터 훈련 시작...")
            
            set_seed(run_seed)
            model = build_model(arch, (seq_len, len(TEMPORAL_COLS)), best_params)
            model = compile_model_quantile(model, lr) 
            loss_cb = QuantileLossCallback(X_val=Xva, y_val_target=yva_target, batch_size=bs)
            callbacks = [ loss_cb,
                K.callbacks.EarlyStopping(monitor="val_pinball_loss", mode="min", patience=10, restore_best_weights=True, verbose=1),
                K.callbacks.ReduceLROnPlateau(monitor="val_pinball_loss", mode="min", factor=0.5, patience=5, min_lr=1e-6, verbose=1),
            ]
            model.fit(Xtr, ytr_target, validation_data=(Xva, yva_target), epochs=100, batch_size=bs, verbose=0, callbacks=callbacks)
            run_best_loss = loss_cb.best_loss
            log(f"   -> ⭐️ Run {i+1} 결과: Best Val Loss = {run_best_loss:.5f}")
            temp_path = os.path.join(results_dir, f"temp_quantile_model_run_{i+1}.h5")
            model.save(temp_path)
            temp_model_paths.append(temp_path)
            
            # ⭐️ [수정] 챔피언 선발을 위해 "seed"도 함께 저장
            all_runs_results.append({ 
                "run": i+1, 
                "loss": run_best_loss, 
                "path": temp_path,
                "seed": run_seed # ⭐️ 시드 저장
            })
            del model
            tf.keras.backend.clear_session()
            
        # --- 5. 챔피언 선발 및 저장 ---
        log("\n" + "="*60)
        log(f"✅ [5/5] 챔피언 선발 및 최종 저장 ({arch.upper()})")
        
        if not all_runs_results:
            log(f"❌ 오류: {arch.upper()} 훈련 결과가 없습니다. 건너뜀.");
            continue
            
        best_run = min(all_runs_results, key=lambda x: x['loss'])
        
        header_msg = f"--- [ {arch.upper()} 훈련 결과 요약 (Val Loss 기준 정렬) ] ---"
        log_summary_to_file("\n" + "="*60, summary_log_path) 
        log_summary_to_file(header_msg, summary_log_path)
        
        sorted_results = sorted(all_runs_results, key=lambda x: x['loss'])
        for res in sorted_results:
            star = "🏆" if res['run'] == best_run['run'] else "  "
            # ⭐️ [수정] 요약 로그에 시드(Seed) 번호 추가
            msg = f" {star} Run {res['run']} (Seed {res['seed']}): Loss = {res['loss']:.5f}"
            log_summary_to_file(msg, summary_log_path) 
        
        log("\n" + "-"*40) 
        # ⭐️ [수정] 최종 챔피언 로그에 시드(Seed) 번호 추가
        champion_msg = f"🏆 챔피언 모델 ({arch.upper()}): Run {best_run['run']} (Val Loss = {best_run['loss']:.5f}, Seed = {best_run['seed']})"
        log_summary_to_file("\n" + champion_msg, summary_log_path) 
        log_summary_to_file("="*60 + "\n", summary_log_path) 

        log(f"   -> {best_run['path']} -> {final_model_path}")
        shutil.move(best_run['path'], final_model_path)
        
        # ⭐️ [수정] best_params.json에 챔피언의 "시드"도 함께 덮어쓰기
        best_params["best_validation_score"] = float(best_run['loss']) 
        best_params["champion_run_seed"] = best_run['seed'] # ⭐️ 챔피언 시드 저장
        with open(params_path, "w", encoding="utf-8") as f:
            json.dump(best_params, f, ensure_ascii=False, indent=2)
        log(f"   -> {params_path}에 챔피언의 Val Loss/시드 덮어쓰기 완료.")
        
        for res in all_runs_results:
            if res['path'] != final_model_path and os.path.exists(res['path']):
                os.remove(res['path'])
        log(f"   -> 임시 모델 파일 {len(temp_model_paths)-1}개 삭제 완료.")

        log(f"\n🎉 {arch.upper()} [QUANTILE] 챔피언 선발 완료!")

    log("\n" + "="*70)
    log("🎉 Phase 1.5 [QUANTILE]: 모든 아키텍처 챔피언 선발 완료!")
    log(f"-> 최종 요약본이 {summary_log_path} 에 저장되었습니다.")
    log("="*70)

if __name__ == "__main__":
    main()
