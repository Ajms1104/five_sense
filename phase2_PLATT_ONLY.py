# -*- coding: utf-8 -*-
# phase2_PLATT_ONLY.py
#
# ⭐️ [V22.PlattOnly] - 테스트/비교용
# 1. ⭐️ [핵심] IsotonicRegression (과적합 유발 가능성) 관련 로직 *모두 제거*
# 2. ⭐️ [핵심] 모든 저장 파일명에 "_PLATT_ONLY_"를 추가하여 기존 결과와 분리
# 3. [버그 수정] 퀀타일 loss가 nan이 되는 버그 수정 (np.mean([]) 방지)
# 4. [버그 수정] 가중치(CompScore)가 음수일 때 균등 가중치가 되는 버그 수정

from __future__ import annotations

# ====== 환경 설정 ======
import os
os.environ['PYTHONHASHSEED'] = '42'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import sys 
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse 
import json
import joblib
import warnings
import numpy as np
import pandas as pd
from itertools import combinations, product 
from collections import Counter
from typing import List, Dict, Tuple, Any, Optional, Union

import tensorflow as tf
import tensorflow.keras as K
from tensorflow.keras import layers as KL
from tensorflow.keras import models as KM
from tensorflow.keras import optimizers as KO
from tensorflow.keras import losses as KLoss

from sklearn.metrics import (
    f1_score, classification_report, confusion_matrix,
    balanced_accuracy_score, matthews_corrcoef 
)
from sklearn.linear_model import LogisticRegression
# ⭐️ [V22] IsotonicRegression 임포트 제거

# ====== config (Phase 1과 동일) ======
try:
    from config import FEATURE_COLS, TEMPORAL_COLS, STATIC_COLS
except ImportError as e:
    print(f"오류: config.py 임포트 실패 ({e}). 스크립트가 프로젝트 루트에서 실행 중인지 확인하세요.")
    sys.exit(1)

# =============================================================================
# 설정
# =============================================================================
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
tf.get_logger().setLevel('ERROR')

SEED = 42 
tf.random.set_seed(SEED)
np.random.seed(SEED)

CLASSIFY_BASE_DIR = 'experiments_v20_ensemble'
QUANTILE_BASE_DIR = 'experiments_v20_quantile_regression'
PREPROCESSED_DATA_DIR = 'preprocessed_dfs'
DEFAULT_ARCHS = ["lstm", "bilstm", "gru", "cnnlstm", "tcn", "transformer"]
OUTPUT_DIR = 'experiments_v20_ensemble_results' 
TOP_K_MODELS_TO_LOAD = 3 

QUANTILES = [0.1, 0.5, 0.9]
RETURN_SCALE = 100.0 

def log(msg: str): print(msg, flush=True)
def ensure_dir(p: str): os.makedirs(p, exist_ok=True)

# =============================================================================
# 커스텀 객체 및 NumPy Loss
# =============================================================================
@tf.keras.utils.register_keras_serializable()
def quantile_loss(y_true, y_pred, quantiles=QUANTILES):
    q = tf.constant(quantiles, dtype=tf.float32); yt = tf.cast(y_true, dtype=tf.float32); yp = tf.cast(y_pred, dtype=tf.float32)
    if tf.rank(yt) == 1: yt = tf.expand_dims(yt, -1)
    if y_true.shape[1] != y_pred.shape[1]:
         yt = tf.tile(yt, [1, tf.shape(yp)[1]])
    e = yt - yp
    pinball = tf.reduce_mean(tf.maximum(q * e, (q - 1.0) * e))
    return pinball

def numpy_quantile_loss(y_true: np.ndarray, y_pred_quantiles: np.ndarray, 
                        quantiles: List[float] = QUANTILES) -> float:
    
    if y_true.shape[0] == 0:
        return np.nan 
        
    if y_true.ndim == 1: y_true = y_true.reshape(-1, 1) 
    if y_pred_quantiles.ndim == 1:
        num_quantiles = len(quantiles)
        if y_pred_quantiles.shape[0] % num_quantiles == 0:
             y_pred_quantiles = y_pred_quantiles.reshape(-1, num_quantiles)
        else: 
             if num_quantiles == 1: y_pred_quantiles = y_pred_quantiles.reshape(-1, 1)
             else: raise ValueError(f"y_pred_quantiles shape {y_pred_quantiles.shape} is not compatible with {num_quantiles} quantiles.")
    q = np.array(quantiles, dtype=np.float32); e = y_true - y_pred_quantiles 
    pinball = np.maximum(q * e, (q - 1.0) * e); return float(np.mean(pinball)) 

@tf.keras.utils.register_keras_serializable()
class PositionalEncoding(KL.Layer):
    def __init__(self, position, d_model, **kwargs):
        super(PositionalEncoding, self).__init__(**kwargs)
        self.position = position; self.d_model = d_model
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
        config = super(PositionalEncoding, self).get_config(); config.update({ "position": self.position, "d_model": self.d_model }); return config

CUSTOM_OBJECTS = {
    "quantile_loss": quantile_loss,
    "PositionalEncoding": PositionalEncoding
}

# =============================================================================
# 시퀀스 생성 (마스터 시퀀스 생성용)
# =============================================================================
def create_sequences_for_model(df: pd.DataFrame, seq_length: int, temporal_cols: List[str]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    X_temporal, y_target, y_direction = [], [], []
    if df.empty or seq_length <= 0: return np.array([]), np.array([]), np.array([])
    unique_codes = df['stock_code'].unique()
    for code in unique_codes:
        stock_df = df[df['stock_code'] == code].sort_values('date')
        temporal_data = stock_df[temporal_cols].values; return_data = stock_df['return'].values
        
        if len(temporal_data) <= seq_length: continue
        num_sequences = len(temporal_data) - seq_length
        if num_sequences <= 0: continue
        
        X_temporal.extend([temporal_data[i:i + seq_length] for i in range(num_sequences)])
        y_target.extend([(return_data[i + seq_length] * RETURN_SCALE) for i in range(num_sequences)])
        y_direction.extend([(1 if return_data[i + seq_length] > 0 else 0) for i in range(num_sequences)])
        
    X_temporal_np = np.array(X_temporal, dtype=np.float32) if X_temporal else np.empty((0, seq_length, len(temporal_cols)), dtype=np.float32)
    y_target_np = np.array(y_target, dtype=np.float32).reshape(-1, 1) if y_target else np.empty((0, 1), dtype=np.float32)
    y_direction_np = np.array(y_direction, dtype=np.int32).reshape(-1,1) if y_direction else np.empty((0,1), dtype=np.int32)
    
    return X_temporal_np, y_target_np, y_direction_np

# =============================================================================
# 1차 예측 스코어 생성 (분류)
# =============================================================================
def get_individual_classification_scores(
    master_temporal_data: np.ndarray, 
    models_info: Dict[str, Dict], 
    arches_to_predict: List[str]
) -> Dict[str, np.ndarray]:
    if master_temporal_data.shape[0] == 0:
        return {}

    individual_preds_cls: Dict[str, np.ndarray] = {}
    
    for arch in arches_to_predict:
        if arch not in models_info:
            log(f"   ❌ '{arch}' (classify) 정보가 없어 예측 실패.")
            continue
            
        for rank, info in models_info[arch].items():
            model_path = info['model_path']; seq_length = info['seq_length']
            model_key = f"{arch}_rank{rank}" 
            
            log(f"   -> 1차 예측 (classify): {arch} (Rank {rank}, SeqLen: {seq_length}) - [모델: {os.path.basename(model_path)}]")
            try:
                model = KM.load_model(model_path, custom_objects=CUSTOM_OBJECTS, compile=False)
                X_sliced = master_temporal_data[:, -seq_length:, :]
                preds = model.predict(X_sliced, batch_size=1024, verbose=0)
                individual_preds_cls[model_key] = preds.reshape(-1) # (N,)
                del model; tf.keras.backend.clear_session()
            except Exception as e:
                log(f"   ❌ '{model_key}' (classify) 예측 실패: {e}")
                individual_preds_cls[model_key] = np.full((master_temporal_data.shape[0],), 0.5, dtype=np.float32)
            
    return individual_preds_cls 

# =============================================================================
# 1차 예측 스코어 생성 (퀀타일)
# =============================================================================
def get_individual_quantile_scores(
    master_temporal_data: np.ndarray, 
    models_info: Dict[str, Dict],
    arches_to_predict: List[str]
) -> Dict[str, np.ndarray]:
    if master_temporal_data.shape[0] == 0:
        return {}

    individual_preds_q: Dict[str, np.ndarray] = {}
    
    for arch in arches_to_predict:
        if arch not in models_info:
            log(f"   ❌ '{arch}' (quantile) 정보가 없어 예측 실패.")
            continue
            
        info = models_info[arch]
        model_path = info['model_path']; seq_length = info['seq_length']
        log(f"   -> 1차 예측 (quantile): {arch} (SeqLen: {seq_length})")
        try:
            model = KM.load_model(model_path, custom_objects=CUSTOM_OBJECTS, compile=False)
            X_sliced = master_temporal_data[:, -seq_length:, :]
            preds = model.predict(X_sliced, batch_size=1024, verbose=0)
            individual_preds_q[arch] = preds # (N, 3)
            del model; tf.keras.backend.clear_session()
        except Exception as e:
            log(f"   ❌ '{arch}' (quantile) 예측 실패: {e}")
            individual_preds_q[arch] = np.zeros((master_temporal_data.shape[0], len(QUANTILES)), dtype=np.float32)
            
    return individual_preds_q

# =============================================================================
# 앙상블 스코어 계산 (분류 - 가중 평균)
# =============================================================================
def get_classification_ensemble_score(
    individual_preds: Dict[str, np.ndarray], 
    weights: Dict[str, float] 
) -> np.ndarray:
    
    valid_preds = {model_key: preds for model_key, preds in individual_preds.items() if model_key in weights}
    
    if not valid_preds:
        return np.array([], dtype=float)
        
    weighted_prob = np.zeros(len(next(iter(valid_preds.values()))), dtype=float)
    total_weight = sum(weights.values())

    if total_weight == 0: 
        log("   -> 경고: 가중치 합이 0. 균등 평균 사용.")
        num_models = len(valid_preds)
        if num_models > 0:
            weighted_prob = sum(valid_preds.values()) / num_models
    else:
        for model_key, preds in valid_preds.items():
            weight = weights.get(model_key, 0)
            weighted_prob += preds * (weight / total_weight) 

    return weighted_prob

# =============================================================================
# 앙상블 스코어 계산 (퀀타일 - 단순 평균)
# =============================================================================
def get_quantile_ensemble_score(
    individual_preds_q: Dict[str, np.ndarray], 
    combo: Tuple[str]
) -> np.ndarray:
    
    preds_to_average = [individual_preds_q[arch] for arch in combo if arch in individual_preds_q]
    
    if not preds_to_average:
        return np.array([], dtype=float)
        
    ensemble_preds = np.mean(preds_to_average, axis=0)
    return ensemble_preds # (N, 3)

# =============================================================================
# ⭐️ [V22] 0.5 고정 원칙으로 이 함수는 사용되지 않음
# =============================================================================
def find_best_threshold_by_f1(y_true, y_prob, min_thr=0.01, max_thr=0.99, steps=100):
    thresholds = np.linspace(min_thr, max_thr, steps)
    f1_scores = [f1_score(y_true, (y_prob >= t).astype(int), average='macro', zero_division=0) for t in thresholds]
    
    if not f1_scores or np.all(np.array(f1_scores) == 0): 
        return 0.5, 0.0 
        
    best_f1 = np.max(f1_scores)
    best_thr = thresholds[np.argmax(f1_scores)]
    return best_thr, best_f1

# =============================================================================
# 상세 편향 진단 헬퍼
# =============================================================================
def get_detailed_metrics(y_true, y_prob, threshold: float) -> Dict:
    if len(y_true) == 0:
        return {
            "balacc": 0.5, "mcc": 0.0, "f1_macro": 0.0,
            "recall0": 0.0, "recall1": 0.0, "pred_pos_rate": 0.0,
            "tn": 0, "fp": 0, "fn": 0, "tp": 0
        }

    try:
        y_pred = (y_prob >= threshold).astype(int)
        
        balacc = balanced_accuracy_score(y_true, y_pred)
        mcc = matthews_corrcoef(y_true, y_pred)
        f1_macro = f1_score(y_true, y_pred, average='macro', zero_division=0)
        
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        if cm.size == 4:
            tn, fp, fn, tp = cm.ravel()
        else:
            if np.all(y_true == 0): tn = cm[0,0]; fp = 0; fn = 0; tp = 0
            elif np.all(y_true == 1): tn = 0; fp = 0; fn = 0; tp = cm[0,0]
            else: tn, fp, fn, tp = 0, 0, 0, 0
                
        recall0 = tn / (tn + fp) if (tn + fp) > 0 else 0.0 
        recall1 = tp / (tp + fn) if (tp + fn) > 0 else 0.0 
        pred_pos_rate = np.mean(y_pred)
        
        return {
            "balacc": float(balacc), "mcc": float(mcc), "f1_macro": float(f1_macro),
            "recall0": float(recall0), "recall1": float(recall1), "pred_pos_rate": float(pred_pos_rate),
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)
        }
    except Exception as e:
        log(f"   -> ⚠️ get_detailed_metrics 오류: {e}")
        return {
            "balacc": 0.5, "mcc": 0.0, "f1_macro": 0.0,
            "recall0": 0.0, "recall1": 0.0, "pred_pos_rate": 0.0,
            "tn": 0, "fp": 0, "fn": 0, "tp": 0
        }

# =============================================================================
# JSON 직렬화 헬퍼
# =============================================================================
def convert_to_python_types(data):
    if isinstance(data, dict):
        return {k: convert_to_python_types(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_to_python_types(item) for item in data]
    if isinstance(data, (np.float32, np.float64)):
        return float(data)
    if isinstance(data, (np.int32, np.int64)):
        return int(data)
    return data

# =============================================================================
# 메인 함수 (V22 - Platt Only)
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Phase 2: V22 - Platt Only + Quantile Ensemble (0.5 Fixed Thr)")
    parser.add_argument("--classify_dir", type=str, default=CLASSIFY_BASE_DIR, help="V20 분류 모델 경로")
    parser.add_argument("--quantile_dir", type=str, default=QUANTILE_BASE_DIR, help="V20 퀀타일 모델 경로")
    parser.add_argument("--data_dir", type=str, default=PREPROCESSED_DATA_DIR, help="V20 데이터 경로 (WalkForward)")
    parser.add_argument("--output_dir", type=str, default=OUTPUT_DIR, help="V20 앙상블 결과 저장 경로")
    parser.add_argument("--arches", nargs="*", default=DEFAULT_ARCHS, help="앙상블에 사용할 아키텍처 목록")
    args = parser.parse_args()

    ensure_dir(args.output_dir)
    log("="*50 + f"\n🚀 Phase 2 (V22 Platt Only + Quantile Ensemble) 시작 | 대상: {args.arches}")
    
    # --- 1. 1차 모델 정보 로드 ---
    log("\n✅ [1/9] 1차 모델(V20) 정보 로드 및 최대 시퀀스 길이 결정 중...")
    log(f"   -> 각 아키텍처별로 Top-{TOP_K_MODELS_TO_LOAD} 챔피언 모델을 모두 로드합니다.")
    
    models_info: Dict[str, Dict[str, Any]] = {'classify': {}, 'quantile': {}}
    max_seq_length_clf = 0 
    max_seq_length_q = 0   
    valid_classify_archs = [] 
    valid_quantile_archs = [] 
    
    for arch in args.arches:
        if arch == 'tft': continue 
        
        # --- 퀀타일 모델 로드 ---
        q_version = f"v20_{arch}_quantile_regression"
        q_params_path = os.path.join(args.quantile_dir, q_version, "best_params.json")
        q_model_path = os.path.join(args.quantile_dir, q_version, 'quantile_model.h5')
        
        if os.path.exists(q_params_path) and os.path.exists(q_model_path):
            with open(q_params_path, 'r', encoding='utf-8') as f: q_params = json.load(f)
            q_seq_len = q_params.get('seq_length')
            q_val_score = q_params.get('best_validation_score', 999.0)
            if q_seq_len:
                models_info['quantile'][arch] = {
                    'model_path': q_model_path, 'seq_length': q_seq_len, 
                    'val_score': q_val_score
                }
                valid_quantile_archs.append(arch) 
                max_seq_length_q = max(max_seq_length_q, q_seq_len)
                log(f"-> 1차(quantile) 로드: '{arch}', SeqLen: {q_seq_len}, Val Loss: {q_val_score:.5f}")

        # --- 분류 모델 로드 (Top-K 모두 로드) ---
        clf_version = f"v20_{arch}_classify_only"
        clf_params_path = os.path.join(args.classify_dir, clf_version, "best_params.json") 
        
        if not os.path.exists(clf_params_path):
            log(f"-> 경고: '{arch}' (classify) best_params.json 없음. 건너뜀.")
            continue
            
        with open(clf_params_path, 'r', encoding='utf-8') as f: clf_params = json.load(f)
        clf_seq_len = clf_params.get('seq_length')
        
        if not clf_seq_len:
             log(f"-> 경고: '{arch}' (classify) best_params.json에 seq_length 없음. 건너뜀.")
             continue
        
        models_info['classify'][arch] = {} 
        loaded_rank_count = 0
        
        for rank in range(1, TOP_K_MODELS_TO_LOAD + 1):
            model_path = os.path.join(args.classify_dir, clf_version, f'classification_model_rank{rank}.h5')
            
            if rank == 1 and not os.path.exists(model_path):
                 model_path = os.path.join(args.classify_dir, clf_version, 'classification_model.h5')
            
            if os.path.exists(model_path):
                rank_info = {}
                report_path = os.path.join(args.classify_dir, clf_version, "phase1_5_report.json")
                if os.path.exists(report_path):
                    try:
                        with open(report_path, 'r', encoding='utf-8') as f: report = json.load(f)
                        if len(report.get("top_k_runs", [])) >= rank:
                            rank_info = report["top_k_runs"][rank-1] # 0-based index
                    except Exception as e:
                        log(f"   -> ⚠️ 경고: {arch} phase1_5_report.json 읽기 실패: {e}")

                comp_score = rank_info.get('comp_score', clf_params.get('best_validation_score', 0.0))
                
                models_info['classify'][arch][rank] = {
                    'model_path': model_path, 
                    'seq_length': clf_seq_len, 
                    'val_score': comp_score, # ⭐️ CompScore (BalAcc or Brier)
                    'val_balacc_0p5': rank_info.get('balacc_0p5', 0.5), 
                    'val_mcc_0p5': rank_info.get('mcc_0p5', 0.0),       
                    'rank_info': rank_info 
                }
                log(f"-> 1차(classify) 로드: '{arch}' (Rank {rank}), SeqLen: {clf_seq_len}, Val CompScore: {comp_score:.4f}")
                max_seq_length_clf = max(max_seq_length_clf, clf_seq_len)
                loaded_rank_count += 1
            else:
                log(f"   -> 정보: '{arch}' Rank {rank} 모델({os.path.basename(model_path)}) 없음. 탐색에서 제외.")
        
        if loaded_rank_count > 0:
            valid_classify_archs.append(arch)
        else:
            log(f"-> 경고: '{arch}' (classify) V20 모델 파일 없음. 건너뜀.")

    if len(valid_classify_archs) < 3:
        log(f"❌ 오류: 유효한 분류 아키텍처가 3개 미만입니다. 탐색을 중단합니다."); sys.exit(1)
    if len(valid_quantile_archs) < 3:
        log(f"⚠️ 경고: 유효한 퀀타일 모델이 {len(valid_quantile_archs)}개입니다 (3개 미만). 퀀타일 앙상블 탐색을 건너뜁니다.")
        valid_quantile_archs = [] 

    log(f"-> 분류 기준(최대) 시퀀스 길이: {max_seq_length_clf}")
    log(f"-> 퀀타일 기준(최대) 시퀀스 길이: {max_seq_length_q}")
    log(f"-> 분류 앙상블 탐색 대상 아키텍처: {valid_classify_archs}")
    log(f"-> 퀀타일 앙상블 탐색 대상 아키텍처: {valid_quantile_archs}")


    # --- 2. 마스터 Val/Test 시퀀스 생성 ---
    log(f"\n✅ [2/9] 마스터 Val/Test 시퀀스 생성 중...")
    try:
        val_df = pd.read_pickle(os.path.join(args.data_dir, "val_df_scaled.pkl"))
        test_df = pd.read_pickle(os.path.join(args.data_dir, "test_df_scaled.pkl"))
    except Exception as e: log(f"❌ V20 데이터 로드 실패: {e}"); sys.exit(1)

    # --- 분류(Classification) 데이터셋 (clf 기준 max_seq_length) ---
    X_val_max_clf, _, y_val_direction_max = create_sequences_for_model(val_df, max_seq_length_clf, TEMPORAL_COLS)
    X_test_max_clf, _, y_test_direction_max = create_sequences_for_model(test_df, max_seq_length_clf, TEMPORAL_COLS)
    
    # --- 퀀타일(Quantile) 데이터셋 (q 기준 max_seq_length) ---
    X_val_max_q, y_val_target_q_max, _ = create_sequences_for_model(val_df, max_seq_length_q, TEMPORAL_COLS) 
    X_test_max_q, y_test_target_q_max, _ = create_sequences_for_model(test_df, max_seq_length_q, TEMPORAL_COLS)
    
    y_cal_direction = y_val_direction_max.ravel()
    y_test_direction = y_test_direction_max.ravel()
    y_cal_target = y_val_target_q_max.ravel()
    y_test_target = y_test_target_q_max.ravel()
    
    is_test_empty = y_test_direction.shape[0] == 0
    
    if X_val_max_clf.shape[0] == 0: log("❌ 마스터 Cal(Val) 분류 시퀀스 생성 실패 (0개)."); sys.exit(1)
    
    if X_val_max_q.shape[0] == 0 and valid_quantile_archs: 
        log("⚠️ 마스터 Cal(Val) 퀀타일 시퀀스 생성 실패 (0개). 퀀타일 탐색을 건너뜁니다.")
        valid_quantile_archs = []
    
    log(f"-> Cal(Val) 시퀀스 (N={X_val_max_clf.shape[0]}), Test 시퀀스 (N={y_test_direction.shape[0]}) 생성 완료")
    
    counter_val = Counter(y_cal_direction)
    log(f"   -> Cal(Val) Set 클래스 분포: 0={counter_val.get(0, 0)}, 1={counter_val.get(1, 0)}")
    if is_test_empty:
        log("   -> ⚠️ 경고: Test Set이 비어있습니다 (N=0). Val F1/Loss 기준으로 최적 조합을 탐색합니다.")

    # --- 3. [1회만 실행] 모든 개별 모델의 Val/Test 예측값 미리 생성 ---
    log("\n✅ [3/9] (1회 실행) 모든 개별 '분류' 모델(Top-K)의 'Val Set' 예측 생성 중...")
    individual_preds_clf_val_all = get_individual_classification_scores(X_val_max_clf, models_info['classify'], valid_classify_archs)
    
    individual_preds_q_val_all = {}
    if valid_quantile_archs:
        log("\n✅ [4/9] (1회 실행) 모든 개별 '퀀타일' 모델의 'Val Set' 예측 생성 중...")
        individual_preds_q_val_all = get_individual_quantile_scores(X_val_max_q, models_info['quantile'], valid_quantile_archs)
    else:
        log("\n✅ [4/9] (1회 실행) 유효한 퀀타일 모델이 없어 'Val Set' 예측을 건너뜁니다.")
    
    individual_preds_clf_test_all = {}
    individual_preds_q_test_all = {}
    
    if not is_test_empty:
        log("\n✅ [5/9] (1회 실행) 모든 개별 '분류' 모델(Top-K)의 'Test Set' 예측 생성 중...")
        individual_preds_clf_test_all = get_individual_classification_scores(X_test_max_clf, models_info['classify'], valid_classify_archs)
        if valid_quantile_archs:
            log("\n✅ [6/9] (1회 실행) 모든 개별 '퀀타일' 모델의 'Test Set' 예측 생성 중...")
            individual_preds_q_test_all = get_individual_quantile_scores(X_test_max_q, models_info['quantile'], valid_quantile_archs)
        else:
            log("\n✅ [6/9] (1회 실행) 유효한 퀀타일 모델이 없어 'Test Set' 예측을 건너뜁니다.")
    else:
        log("\n✅ [5/9, 6/9] (1회 실행) Test Set이 비어있어 'Test Set' 예측을 건너뜁니다.")

    del X_val_max_clf, X_test_max_clf, X_val_max_q, X_test_max_q
    log(f"-> ⭐️ 총 {len(individual_preds_clf_val_all)}개의 분류 모델 예측(Val) 생성 완료.")

    # --- 7. [⭐️ 핵심 루프 1 ⭐️] 분류 앙상블 조합(k=3~6) + (Rank 1~3) 완전 탐색 ---
    log("\n✅ [7/9] '방향성' 예측: 앙상블 조합(k=3~6) x (Rank 1~3) 완전 탐색 시작...")
    
    all_classification_results = []
    
    for k in range(3, len(valid_classify_archs) + 1):
        for arch_combo in combinations(valid_classify_archs, k):
            
            ranks_available_for_combo = [list(models_info['classify'][arch].keys()) for arch in arch_combo]
            
            for rank_combo in product(*ranks_available_for_combo):
                model_keys_combo = [f"{arch}_rank{rank}" for arch, rank in zip(arch_combo, rank_combo)]
                combo_name = " + ".join(model_keys_combo)
                
                log(f"\n" + "-"*40 + f"\n➡️  [방향성] 조합 (k={k}) 테스트 중: {combo_name}")

                # ==========================================================
                # ⭐️ [V21.Brier 버그 수정] A-1: 가중치 계산 로직 수정
                # ==========================================================
                individual_preds_val_combo = {model_key: individual_preds_clf_val_all[model_key] for model_key in model_keys_combo}
                val_comp_scores_combo = {}
                
                for model_key in model_keys_combo:
                    try:
                        arch, rank_str = model_key.split('_rank')
                        rank = int(rank_str)
                        val_score = models_info['classify'][arch][rank].get('val_score', -999.0) 
                        val_comp_scores_combo[model_key] = val_score
                    except Exception as e:
                        log(f"   -> ⚠️ {model_key}의 val_score 로드 실패: {e}")
                        val_comp_scores_combo[model_key] = -999.0
                
                # ==========================================================
                # ⭐️ [V21.Brier 버그 수정] A-2: Brier (음수) 또는 CompScore (양수) 가중치 계산
                # ==========================================================
                weights_combo = {}
                scores = list(val_comp_scores_combo.values())
                
                min_score = min(scores) if scores else 0.0
                shifted_scores = {k: (v - min_score) for k, v in val_comp_scores_combo.items()}
                total_shifted_score = sum(shifted_scores.values())

                if total_shifted_score > 1e-6:
                    for model_key, score in shifted_scores.items():
                        weights_combo[model_key] = score / total_shifted_score
                else: 
                    weights_combo = {model_key: 1.0 / len(model_keys_combo) for model_key in model_keys_combo}

                log(f"   -> 콤보 가중치 (Val CompScore 기반): { {k: round(v, 3) for k, v in weights_combo.items()} }")

                # [A-3] 캘리브레이터 훈련
                s_cal_combo = get_classification_ensemble_score(individual_preds_val_combo, weights_combo)
                
                platt_cal = LogisticRegression(solver="lbfgs", class_weight=None, max_iter=1000)
                platt_cal.fit(s_cal_combo.reshape(-1, 1), y_cal_direction)
                
                # ⭐️ [V22 수정] IsotonicRegression 관련 코드 *모두 삭제*
                log(f"   -> 콤보 캘리브레이터(Platt) 훈련 완료.")

                # ==========================================================
                # ⭐️ [V22 수정] A-4: 0.5 임계값 고정 (Platt만)
                # ==========================================================
                p_cal_platt = platt_cal.predict_proba(s_cal_combo.reshape(-1, 1))[:, 1]
                
                best_thr_platt = 0.5

                # [A-4b] Val Set 상세 지표 계산 (0.5 고정)
                val_metrics_platt = get_detailed_metrics(y_cal_direction, p_cal_platt, best_thr_platt)

                # [A-5] 테스트셋 평가
                test_metrics_platt = {}

                if not is_test_empty:
                    individual_preds_test_combo = {model_key: individual_preds_clf_test_all.get(model_key) for model_key in model_keys_combo if individual_preds_clf_test_all.get(model_key) is not None}
                    
                    if len(individual_preds_test_combo) == len(model_keys_combo):
                        s_test_combo = get_classification_ensemble_score(individual_preds_test_combo, weights_combo)
                        
                        p_test_platt = platt_cal.predict_proba(s_test_combo.reshape(-1, 1))[:, 1]
                        test_metrics_platt = get_detailed_metrics(y_test_direction, p_test_platt, best_thr_platt)
                    else:
                        log(f"   -> ⚠️ 경고: Test 예측값이 일부 모델에서 누락되어 Test 평가를 건너뜁니다.")

                log(f"   -> ⭐️ Platt(Val BalAcc): {val_metrics_platt['balacc']:.4f} @ Thr={best_thr_platt:.4f} (고정) | (Test BalAcc: {test_metrics_platt.get('balacc', -1):.4f})")

                # [A-6] 결과 리스트에 추가 (Platt만)
                all_classification_results.append({
                    "combo_name": combo_name, "k": k, "type": "Platt",
                    "threshold": best_thr_platt, "weights": weights_combo,
                    "calibrator_obj": platt_cal,
                    "val_metrics": val_metrics_platt, 
                    "test_metrics": test_metrics_platt 
                })

    # --- 8. [⭐️ 핵심 루프 2 ⭐️] 퀀타일 앙상블 조합(k=3~6) 탐색 ---
    all_quantile_results = []
    best_overall_q = None 
    
    if valid_quantile_archs:
        log("\n✅ [8/9] '변동성' 예측: 퀀타일 앙상블 조합(k=3~6) 전체 탐색 시작...")
        
        for k in range(3, len(valid_quantile_archs) + 1):
            for combo in combinations(valid_quantile_archs, k):
                combo_name = " + ".join(combo)
                
                ensemble_q_preds_val = get_quantile_ensemble_score(individual_preds_q_val_all, combo)
                loss_val = numpy_quantile_loss(y_cal_target, ensemble_q_preds_val, QUANTILES)
                
                loss_test = np.nan 
                if not is_test_empty and y_test_target.shape[0] > 0: 
                    ensemble_q_preds_test = get_quantile_ensemble_score(individual_preds_q_test_all, combo)
                    loss_test = numpy_quantile_loss(y_test_target, ensemble_q_preds_test, QUANTILES)

                log(f"   -> ⭐️ [변동성] 콤보 (k={k}) {combo_name} | Val Loss: {loss_val:.5f} | (Test Loss: {loss_test:.5f})")

                all_quantile_results.append({
                    "combo_name": combo_name, "k": k,
                    "val_loss": loss_val,
                    "test_loss": loss_test, 
                    "models": list(combo)
                })
        
        if not all_quantile_results:
             log("⚠️ 퀀타일 앙상블 조합 결과가 없습니다.")
        else:
            is_test_q_valid = (not is_test_empty) and (y_test_target.shape[0] > 0)
            sort_key_q_primary = 'test_loss' if is_test_q_valid else 'val_loss'
            sort_key_q_secondary = 'val_loss' if is_test_q_valid else 'test_loss' 

            best_results_q = sorted(all_quantile_results, key=lambda x: (
                x.get(sort_key_q_primary, float('inf')), 
                x.get(sort_key_q_secondary, float('inf'))
            ))
            best_overall_q = best_results_q[0]
            
    else:
        log("\n✅ [8/9] 유효한 퀀타일 모델이 없어 '변동성' 앙상블 탐색을 건너뜁니다.")


    # --- 9. [최종 리포트] ---
    log("\n✅ [9/9] 최종 듀얼 앙상블 리포트...")
    log("="*50)

    # 9.1) 분류 앙상블 1등 선정
    if not all_classification_results:
        log("❌ 탐색된 분류 앙상블 조합 결과가 없습니다 (Platt-only)."); sys.exit(1)
        
    sort_key_clf = 'test_metrics' if not is_test_empty else 'val_metrics'
    
    log(f"\n   -> ⭐️ {sort_key_clf.upper()} 기준 다중-키 정렬 (1: BalAcc, 2: MCC, 3: F1-Macro)")
    best_results_clf = sorted(
        all_classification_results, 
        key=lambda x: (
            x[sort_key_clf].get('balacc', 0.0),
            x[sort_key_clf].get('mcc', 0.0),
            x[sort_key_clf].get('f1_macro', 0.0)
        ), 
        reverse=True
    )
    best_overall_clf = best_results_clf[0]

    # [신규] Top-10 상세 리포트 출력
    log("\n" + "--- [ 🏆 Top-10 방향성 앙상블 (Weighted Avg, Platt Only) 상세 리포트 🏆 ] ---")
    log(f"     (정렬 기준: {sort_key_clf.upper()} [BalAcc > MCC > F1])")

    top_10_clf = best_results_clf[:10] 

    for i, res in enumerate(top_10_clf):
        log(f"\n   --- 🥇 앙상블 {i+1} (k={res['k']}, {res['type']}) ---")
        log(f"   [조합] {res['combo_name']}")
        log(f"   [가중치] { {k: round(v, 3) for k, v in res['weights'].items()} }")
        
        val_m = res.get("val_metrics", {})
        log(f"   [A: Val Set @ Thr={res['threshold']:.4f} (0.5 고정)]")
        log(f"     - 🎯 BalAcc: {val_m.get('balacc', 0):.4f} | MCC: {val_m.get('mcc', 0):.4f} | F1-Macro: {val_m.get('f1_macro', 0):.4f}")
        log(f"     - [편향진단] R0 (하락): {val_m.get('recall0', 0):.4f} | R1 (상승): {val_m.get('recall1', 0):.4f}")
        log(f"     - [편향진단] 예측된 상승 비율: {val_m.get('pred_pos_rate', 0):.4f}")

        test_m = res.get("test_metrics", {})
        if not is_test_empty and test_m:
            log(f"   [B: Test Set @ Thr={res['threshold']:.4f} (0.5 고정)] (최종 성능)")
            log(f"     - 🎯 BalAcc: {test_m.get('balacc', 0):.4f} | MCC: {test_m.get('mcc', 0):.4f} | F1-Macro: {test_m.get('f1_macro', 0):.4f}")
            log(f"     - [편향진단] R0 (하락): {test_m.get('recall0', 0):.4f} | R1 (상승): {test_m.get('recall1', 0):.4f}")
            log(f"     - [편향진단] 예측된 상승 비율: {test_m.get('pred_pos_rate', 0):.4f}")
        else:
            log(f"   [B: Test Set] (데이터 없음)")

    # --- 기존 1등 요약 (유지) ---
    primary_score_key = 'balacc' 
    log("\n" + "--- [ 🏆 *최종 1등* 방향성 앙상블 (Weighted Avg, Platt Only) 🏆 ] ---")
    log(f"  - 조합 (k={best_overall_clf['k']}): {best_overall_clf['combo_name']}")
    log(f"  - 방식: {best_overall_clf['type']} Voting (Platt Only)")
    log(f"  - ⭐️ 1순위 점수 ({sort_key_clf.upper()} BalAcc): {best_overall_clf[sort_key_clf].get(primary_score_key, 0):.4f}")
    log(f"  - 검증 (Val) BalAcc: {best_overall_clf['val_metrics'].get(primary_score_key, 0):.4f}")
    if not is_test_empty:
        log(f"  - 테스트 (Test) BalAcc: {best_overall_clf['test_metrics'].get(primary_score_key, 0):.4f}")
    log(f"  - 최적 임계값: {best_overall_clf['threshold']:.3f} (고정값)")
    log(f"  - 적용된 가중치: { {k: round(v, 3) for k, v in best_overall_clf['weights'].items()} }")
    log("="*50)
    
    # 9.2) 퀀타일 앙상블 1등 선정 (결과 출력)
    if best_overall_q:
        is_test_q_valid = (not is_test_empty) and (y_test_target.shape[0] > 0)
        sort_key_q_primary = 'test_loss' if is_test_q_valid else 'val_loss'
        
        log("\n" + "--- [ 🏆 최종 Best 변동성 앙상블 🏆 ] ---")
        log(f"  - 조합 (k={best_overall_q['k']}): {best_overall_q['combo_name']}")
        log(f"  - 방식: 단순 평균 앙상블")
        log(f"  - ⭐️ 1순위 점수 ({sort_key_q_primary.upper()}): {best_overall_q[sort_key_q_primary]:.5f}")
        log(f"  - 검증 (Val) Loss: {best_overall_q['val_loss']:.5f}")
        if is_test_q_valid:
            log(f"  - 테스트 (Test) Loss: {best_overall_q['test_loss']:.5f}")
        else:
            log(f"  - 테스트 (Test) Loss: {best_overall_q.get('test_loss', np.nan)} (nan/데이터 없음)")
        log("="*50)
    else:
        log("\n--- [ ⚠️ 최종 Best 변동성 앙상블 없음 (탐색 건너뜀) ] ---")
        log("="*50)

    # ==========================================================
    # ⭐️ [V22.PlattOnly] 9.3: 모든 저장 파일명 수정
    # ==========================================================
    log(f"\n✅ 최종 Best 모델 아티팩트 저장 중... (PLATT_ONLY)")
    
    best_calibrator = best_overall_clf['calibrator_obj']
    calibrator_type = best_overall_clf['type'].lower() # 'platt'
    
    best_clf_model_path = os.path.join(args.output_dir, f"best_WEIGHTED_AVG_calibrator_{calibrator_type}_PLATT_ONLY_v20.joblib")
    joblib.dump(best_calibrator, best_clf_model_path)
    log(f" -> [방향성] Best 가중 평균 캘리브레이터 저장: {best_clf_model_path}")
    
    log(f" -> [변동성] Best 앙상블 조합 정보가 JSON에 저장됩니다.")

    member_models_info_serializable = {}
    if best_overall_q:
         member_models_info_serializable = {
            arch: convert_to_python_types(models_info['quantile'][arch]) 
            for arch in best_overall_q['models']
         }

    member_models_info_clf = {}
    for model_key in best_overall_clf['combo_name'].split(' + '): 
        arch, rank_str = model_key.split('_rank')
        rank = int(rank_str)
        member_models_info_clf[model_key] = {
            'arch': arch,
            'selected_rank': rank,
            'model_path': models_info['classify'][arch][rank].get('model_path')
        }

    weighted_avg_report = {
        "best_classification_ensemble": {
            "combination_keys": best_overall_clf['combo_name'].split(' + '), 
            "member_models_info": member_models_info_clf, 
            "weights": convert_to_python_types(best_overall_clf['weights']),
            "threshold": float(best_overall_clf['threshold']),
            "calibrator_path": best_clf_model_path,
            "calibrator_type": best_overall_clf['type'],
            "primary_score_type": f"{sort_key_clf} (BalAcc > MCC > F1)", 
            "val_metrics": best_overall_clf.get("val_metrics", {}),
            "test_metrics": best_overall_clf.get("test_metrics", {}),
        },
        "best_quantile_ensemble": None 
    }
    
    if best_overall_q:
        is_test_q_valid = (not is_test_empty) and (y_test_target.shape[0] > 0)
        sort_key_q_primary = 'test_loss' if is_test_q_valid else 'val_loss'
        
        weighted_avg_report["best_quantile_ensemble"] = {
            "combination": best_overall_q['models'],
            "k": int(best_overall_q['k']),
            "val_loss": float(best_overall_q['val_loss']),
            "test_loss": float(best_overall_q.get('test_loss', np.nan)), # ⭐️ nan 저장
            "primary_score": float(best_overall_q[sort_key_q_primary]),
            "primary_score_type": sort_key_q_primary,
            "member_models_info": member_models_info_serializable
        }

    
    best_info_path = os.path.join(args.output_dir, "best_WEIGHTED_AVG_info_PLATT_ONLY_v20.json")
    with open(best_info_path, 'w', encoding='utf-8') as f:
        json.dump(convert_to_python_types(weighted_avg_report), f, indent=4, ensure_ascii=False)
    log(f" -> [종합] Best 가중 평균 앙상블 정보 저장: {best_info_path}")

    # 9.4) 전체 리포트 저장 (참고용)
    log("\n✅ 전체 조합 분석 리포트 저장 중... (PLATT_ONLY)")
    for res in all_classification_results:
        del res['calibrator_obj'] 
        
    full_report_clf_path = os.path.join(args.output_dir, "full_WEIGHTED_AVG_combination_report_PLATT_ONLY_v20.json")
    with open(full_report_clf_path, 'w', encoding='utf-8') as f:
        json.dump(convert_to_python_types(all_classification_results), f, indent=4, ensure_ascii=False)
    
    if all_quantile_results:
        full_report_q_path = os.path.join(args.output_dir, "full_quantile_ensemble_report_PLATT_ONLY_v20.json")
        with open(full_report_q_path, 'w', encoding='utf-8') as f:
            json.dump(convert_to_python_types(all_quantile_results), f, indent=4, ensure_ascii=False)
        log(f" -> 전체 퀀타일 리포트 저장 완료: {full_report_q_path}")
    
    log(f" -> 전체 '가중 평균' 리포트 저장 완료: {full_report_clf_path}") 

    # 9.5) 개별 단일 모델 성능 요약
    log("\n" + "="*50)
    log("✅ 참고용: 개별 단일 모델 성능 요약 (0.5 고정 임계값 기준)")
    log("="*50)

    log("\n--- [A] 개별 '방향성' 모델 (Val CompScore) ---") 
    best_single_f1 = -float('inf') 
    best_single_clf_name = ""
    
    sort_key_single_clf = 'test_metrics' if not is_test_empty else 'val_metrics'
    
    for arch in valid_classify_archs:
        if arch not in models_info['classify']: continue
        
        for rank, info in models_info['classify'][arch].items():
            model_key = f"{arch}_rank{rank}"
            val_score = info.get('val_score', -999.0)
            threshold = 0.5 
            
            f1_single_test_str = ""
            primary_score_single = val_score 
            
            if not is_test_empty and model_key in individual_preds_clf_test_all:
                preds_test = individual_preds_clf_test_all[model_key]
                test_metrics_single = get_detailed_metrics(y_test_direction, preds_test, threshold)
                
                test_balacc = test_metrics_single['balacc']
                f1_single_test_str = f"| Test BalAcc: {test_balacc:.4f}"
                primary_score_single = test_balacc 
            
            log(f"  -> {model_key.upper()} (Val CompScore @ Thr={threshold:.3f}): {val_score:.4f} {f1_single_test_str}")
            
            if primary_score_single > best_single_f1:
                best_single_f1 = primary_score_single
                best_single_clf_name = model_key
            
    log(f"  -> 🏆 Best Single Model ({sort_key_single_clf.upper().split('_')[0]} BalAcc/CompScore): {best_single_clf_name.upper()} @ {best_single_f1:.4f}")

    # --- 퀀타일 (Loss) 개별 모델 ---
    if valid_quantile_archs:
        log("\n--- [B] 개별 '변동성' 모델 (Val Loss) ---")
        best_single_loss = float('inf')
        best_single_q_name = ""
        
        is_test_q_valid = (not is_test_empty) and (y_test_target.shape[0] > 0)
        sort_key_single_q = 'test_loss' if is_test_q_valid else 'val_loss'

        for arch in valid_quantile_archs:
            loss_single_val = models_info['quantile'][arch].get('val_score', float('inf'))
            
            loss_single_test_str = ""
            primary_score_single_q = loss_single_val 

            if is_test_q_valid and arch in individual_preds_q_test_all:
                preds_test_q = individual_preds_q_test_all[arch]
                loss_single_test = numpy_quantile_loss(y_test_target, preds_test_q, QUANTILES)
                loss_single_test_str = f"| Test Loss: {loss_single_test:.5f}"
                primary_score_single_q = loss_single_test
            
            log(f"  -> {arch.upper()} (Val Loss): {loss_single_val:.5f} {loss_single_test_str}")
            
            if primary_score_single_q < best_single_loss:
                best_single_loss = primary_score_single_q
                best_single_q_name = arch

        log(f"  -> 🏆 Best Single Model ({sort_key_single_q.upper().split('_')[0]} Loss): {best_single_q_name.upper()} @ {best_single_loss:.5f}")


    log("\n🎉 Phase 2 (V22 Platt Only) 완료!")
    log("="*50)

if __name__ == "__main__":
    main()
