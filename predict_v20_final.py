# -*- coding: utf-8 -*-
"""
predict_v20_WINNER_ONLY.py
- V20 최종 예측 스크립트 (서버 실행용).
- ⭐️ [V22.WinnerOnly] 
- 1. (수정) "WEIGHTED_AVG" (0.5810) 1등 앙상블 *하나만* 예측하고 CSV로 저장
- 2. (수정) Stacking 및 개별 챔피언 6개 트랙 *모두 제거*
- 3. (추가) 나머지 모든 개별 모델(rank1~3)은 로그에 "상승 예측 비율"만 요약 출력
- 4. (수정) 1.5의 Top-K (rank1~3) 모델을 모두 로드하여 앙상블을 정확히 재현
- 5. (수정) 분류/퀀타일 시퀀스 길이 분리 로드 (nan 버그 수정)
- 6. ⭐️ (버그 수정 9) DB 로드 로직 *최종 수정*: 
-    local_data_prep이 이미 병합한 'price_data' 테이블 *하나만* 읽도록 수정.
-    불필요한 investor/financial 병합 로직 *모두 제거*.
-    ffill 직전 pd.to_numeric 강제 변환 (안정성)
"""

from __future__ import annotations

# ====== 환경 설정 ======
import os
os.environ['PYTHONHASHSEED'] = '42'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import sys 
project_root = os.path.abspath(os.path.dirname(__file__)) 
if project_root not in sys.path: sys.path.insert(0, project_root)

import argparse 
import json
import joblib
import warnings
import numpy as np
import pandas as pd
from itertools import combinations
from collections import Counter
from typing import List, Dict, Tuple, Any, Optional, Union
from datetime import date, timedelta
import math 
import sqlite3 

import tensorflow as tf
import tensorflow.keras as K
from tensorflow.keras import layers as KL
from tensorflow.keras import models as KM
from sklearn.metrics import f1_score, classification_report, confusion_matrix
from sklearn.linear_model import LogisticRegression 
from sklearn.isotonic import IsotonicRegression 

# ====== config (Phase 1과 동일) ======
try:
    from config import HOLIDAYS_2025, stock_to_industry, stock_code_to_name, FEATURE_COLS as CONFIG_FEATURE_COLS, TEMPORAL_COLS, STATIC_COLS
except ImportError as e:
    print(f"오류: config.py 임포트 실패 ({e}). 프로젝트 루트 경로 ({project_root}) 및 config.py 존재 여부 확인.")
    sys.exit(1)

# =================================================================
# 설정
# =================================================================
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
tf.get_logger().setLevel('ERROR')

SEED = 42 
tf.random.set_seed(SEED)
np.random.seed(SEED)

CLASSIFY_BASE_DIR = os.path.join(project_root, 'experiments_v20_ensemble')
QUANTILE_BASE_DIR = os.path.join(project_root, 'experiments_v20_quantile_regression')
ENSEMBLE_RESULTS_DIR = os.path.join(project_root, 'experiments_v20_ensemble_results')
LOGS_DIR = os.path.join(project_root, 'logs')

WEIGHTED_AVG_REPORT_PATH = os.path.join(ENSEMBLE_RESULTS_DIR, 'best_WEIGHTED_AVG_info_v20.json') 

# --- V20 SQLite DB 파일 경로 설정 ---
today_db_str = date.today().strftime("%Y%m%d")
SQLITE_DB_PATH = os.path.join(project_root, f'predict_data_v20_{today_db_str}.db')

TARGET_STOCKS = list(stock_to_industry.keys())
QUANTILES = [0.1, 0.5, 0.9]
RETURN_SCALE = 100.0 
ARCHITECTURES = ["lstm", "bilstm", "gru", "cnnlstm", "tcn", "transformer"]
TOP_K_MODELS_TO_LOAD = 3 

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

# =================================================================
# 로거 설정 (v20)
# =================================================================
today_str_log = date.today().strftime("%Y-%m-%d")
ensure_dir(LOGS_DIR)
log_filename = os.path.join(LOGS_DIR, f"prediction_log_v20_FINAL_WINNER_ONLY_{today_str_log}.txt") 

class Logger(object):
    def __init__(self, filename="Default.log"): self.terminal = sys.stdout; self.log = open(filename, "a", encoding='utf-8')
    def write(self, message): self.terminal.write(message); self.log.write(message)
    def flush(self): self.terminal.flush(); self.log.flush()

sys.stdout = Logger(log_filename)
print(f"\n--- V20 FINAL (수정됨: WINNER_ONLY, Q연동) 시작 ({date.today().strftime('%Y-%m-%d %H:%M:%S')}) ---") 

def log(message):
    print(message)

# =================================================================
# 커스텀 객체 및 NumPy Loss
# =================================================================
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

# =================================================================
# 헬퍼 함수
# =================================================================
def get_recent_volatility_limits_sqlite(stock_code, sqlite_path):
    query = f"SELECT date, \"sma_20\" FROM price_data WHERE stock_code = '{stock_code}' ORDER BY date DESC LIMIT 60;"
    try:
        conn = sqlite3.connect(sqlite_path)
        df = pd.read_sql_query(query, conn, parse_dates=['date'])
        conn.close()
        
        df['sma_20'] = pd.to_numeric(df['sma_20'], errors='coerce')
        if len(df) < 10: return 0.15, -0.15
        df['daily_change'] = df['sma_20'].pct_change().replace([np.inf, -np.inf], np.nan)
        
        volatility = df['daily_change'].std()
        if pd.isna(volatility) or volatility <= 0: return 0.15, -0.15
        max_gain = min(volatility * 2.5, 0.30); max_loss = max(volatility * -2.5, -0.30)
        return max_gain, max_loss
    except sqlite3.Error as e: log(f"-> 변동성 계산 중 SQLite 오류: {e}"); return 0.15, -0.15
    except Exception as e: log(f"-> 변동성 계산 중 오류: {e}"); return 0.15, -0.15

def get_next_trading_day(today):
    next_day = today
    while True:
        next_day += timedelta(days=1)
        if next_day.weekday() < 5 and next_day.strftime('%Y-%m-%d') not in HOLIDAYS_2025: return next_day

# =================================================================
# ⭐️ [V22.ffill-fix-9] (수정) 데이터 로드 및 전처리 함수 (병합 로직 *제거*)
# =================================================================
def load_data_from_sqlite(data_length: int, feature_cols_ordered: List[str], sqlite_path: str) -> Optional[pd.DataFrame]:
    log(f"✅ [3/6] 예측용 최신 데이터 로드 및 전처리를 시작합니다 (SQLite: {sqlite_path})")
    days_to_load = data_length + 60 # (ffill 등을 위한 버퍼)

    if not os.path.exists(sqlite_path):
        log(f"❌ 오류: 예측 데이터 V20 SQLite 파일 없음: {sqlite_path}")
        return None

    try: # 날짜 확인
        conn = sqlite3.connect(sqlite_path)
        last_date_query = f"SELECT MAX(date) FROM price_data WHERE stock_code='{TARGET_STOCKS[0]}'"
        last_date_str = pd.read_sql_query(last_date_query, conn).iloc[0, 0]
        if not last_date_str: raise ValueError("SQLite DB에 가격 데이터가 없습니다.")
        log(f"-> SQLite DB 마지막 데이터 날짜: {last_date_str}")

        start_date_query = f"SELECT MIN(date) FROM (SELECT date FROM price_data WHERE stock_code='{TARGET_STOCKS[0]}' AND date <= '{last_date_str}' ORDER BY date DESC LIMIT {days_to_load})"
        start_date_str = pd.read_sql_query(start_date_query, conn).iloc[0, 0]
        if not start_date_str:
            log(f"⚠️ 경고: DB에 {days_to_load}일치 데이터가 없습니다. 가능한 모든 데이터를 로드합니다.")
            start_date_query = f"SELECT MIN(date) FROM price_data WHERE stock_code='{TARGET_STOCKS[0]}'"
            start_date_str = pd.read_sql_query(start_date_query, conn).iloc[0, 0]
        
        log(f"-> 데이터 로드 시작 날짜: {start_date_str}")
        conn.close()

    except sqlite3.Error as e: log(f"❌ SQLite 날짜 조회 실패: {e}"); return None
    except Exception as e: log(f"❌ 날짜 계산 오류: {e}"); return None

    try: # ⭐️ [수정] 데이터 로드 (price_data 테이블 하나만 로드)
        conn = sqlite3.connect(sqlite_path)
        target_stocks_tuple = tuple(TARGET_STOCKS)

        # ⭐️ local_data_prep_v20.py가 이미 모든 피처(32개) + close_pric (1개)를 price_data에 저장했음
        all_cols_to_load = ['stock_code', 'date'] + feature_cols_ordered
        all_cols_to_load = list(dict.fromkeys(all_cols_to_load)) # 중복 제거 (순서 유지)
        
        quoted_feature_cols = [f'"{col}"' for col in all_cols_to_load if col not in ['stock_code', 'date']]

        price_sql = f"""
            SELECT stock_code, date, {', '.join(quoted_feature_cols)} 
            FROM price_data 
            WHERE stock_code IN {target_stocks_tuple} AND date >= '{start_date_str}'
        """
        
        final_df = pd.read_sql_query(price_sql, conn, parse_dates=['date'])
        conn.close()

    except sqlite3.Error as e: log(f"❌ SQLite 데이터 로드 오류: {e}"); return None
    except Exception as e: log(f"❌ 데이터 로드 중 오류: {e}"); return None

    if final_df.empty: log("❌ 오류: SQLite DB에 필요한 기간의 가격 데이터 없음."); return None
    
    # ⭐️ [V22.ffill-fix-9] (수정) 불필요한 병합(merge) 로직 *모두 삭제*
    
    # ⭐️ [수정] 누락 컬럼 확인 (local_data_prep_v20.py가 정상 작동했다면 이 경고는 뜨지 않아야 함)
    missing_cols = []
    for col in feature_cols_ordered:
        if col not in final_df.columns:
            final_df[col] = np.nan # ⭐️ 0.0이 아닌 np.nan으로 채움
            missing_cols.append(col)
    if missing_cols: log(f"-> 🔴 경고: DB 로드 후 피처 누락 (np.nan으로 채움): {missing_cols}")

    if 'close_pric' not in final_df.columns:
        final_df['close_pric'] = np.nan 
        log("   -> 'close_pric' 컬럼이 DB에 없어 np.nan으로 추가합니다. (후처리용)")

    # ⭐️ [수정] ffill 전에 dtype 강제 변환
    log("   -> ⭐️ ffill 전, 모든 피처의 dtype을 numeric으로 강제 변환...")
    try:
        for col in feature_cols_ordered:
            final_df[col] = pd.to_numeric(final_df[col], errors='coerce') 
        final_df['close_pric'] = pd.to_numeric(final_df['close_pric'], errors='coerce')
    except Exception as e:
        log(f"   ❌ dtype 강제 변환 실패: {e}. 예측 중단.")
        return None

    # ⭐️ [수정] ffill/fillna 로직 (가장 안정적인 2-step)
    log("   -> 그룹별 ffill 및 fillna(0) 적용 중 (2-step 방식)...")
    
    # 1. ffill (그룹별)
    final_df[feature_cols_ordered] = final_df.groupby('stock_code')[feature_cols_ordered].ffill()
    final_df['close_pric'] = final_df.groupby('stock_code')['close_pric'].ffill()
    
    # 2. fillna(0) (전체)
    final_df[feature_cols_ordered] = final_df[feature_cols_ordered].fillna(0)
    final_df['close_pric'] = final_df['close_pric'].fillna(0)
    
    log(f"-> 최신 데이터 로드/가공 완료 (Shape: {final_df.shape}).")
    return final_df

# 모델별 입력 데이터 생성 함수
def create_input_for_model(stock_df_scaled: pd.DataFrame, seq_len: int, temporal_cols: List[str]) -> np.ndarray:
    input_data = stock_df_scaled.tail(seq_len)
    if len(input_data) < seq_len:
        raise ValueError(f"모델 입력 생성 실패. 필요: {seq_len}, 가능: {len(input_data)}")
    temporal_input = input_data[temporal_cols].values.reshape(1, seq_len, -1)
    return temporal_input

# =================================================================
# ⭐️ V22.WinnerOnly 예측 실행 함수
# =================================================================
def run_prediction():
    log(f"🚀 V20 FINAL 예측 (수정됨: WINNER_ONLY, TopK로드, Q연동) 스크립트 실행")

    # --- 1. 스케일러, 피처 순서, 앙상블 정보 로드 ---
    log("\n✅ [1/6] 스케일러, 피처 순서, 앙상블 정보 로드 중...")
    try:
        base_model_files_dir = os.path.join(CLASSIFY_BASE_DIR, 'v20_gru_classify_only') 
        scaler_path = os.path.join(base_model_files_dir, 'final_scaler.pkl')
        feature_order_path = os.path.join(base_model_files_dir, 'feature_order.json')

        scaler = joblib.load(scaler_path)
        log(f"-> 스케일러 로드 완료: {scaler_path}")

        with open(feature_order_path, 'r', encoding='utf-8') as f: feature_info = json.load(f)
        feature_cols_ordered = feature_info['ALL_FEATURES']
        temporal_cols_ordered = feature_info['TEMPORAL_COLS']
        log(f"-> 피처 순서 정보 로드 완료 ({len(feature_cols_ordered)}개).")
        
        # ⭐️ 1-1. 가중 평균(Weighted Avg) 전략 로드
        with open(WEIGHTED_AVG_REPORT_PATH, 'r', encoding='utf-8') as f: weighted_report = json.load(f) 
        weighted_avg_info = weighted_report['best_classification_ensemble'] 
        
        weighted_combination_keys = weighted_avg_info['combination_keys'] 
        weighted_weights = weighted_avg_info['weights'] 
        weighted_threshold = weighted_avg_info['threshold'] 
        weighted_calibrator_type = weighted_avg_info['calibrator_type'].lower() 
        
        weighted_model_filename = f"best_WEIGHTED_AVG_calibrator_{weighted_calibrator_type}_v20.joblib"
        weighted_model_path = os.path.join(ENSEMBLE_RESULTS_DIR, weighted_model_filename) 
        
        meta_model_weighted_avg = joblib.load(weighted_model_path)
        log(f"-> [전략 1] 가중 평균 앙상블 로드 완료 (모델 {len(weighted_combination_keys)}개, 임계값 {weighted_threshold:.4f})")
        log(f"   -> 조합: {', '.join(weighted_combination_keys)}")

        # ⭐️ 1-2. 퀀타일(Quantile) 앙상블 전략 로드 (WEIGHTED_AVG 리포트에서 가져옴)
        best_qnt_info = weighted_report.get('best_quantile_ensemble') 
        if best_qnt_info is None:
             log("-> ⚠️ 경고: 퀀타일 앙상블 정보가 없습니다. (WEIGHTED_AVG_REPORT_PATH 확인 필요)")
             quantile_combination_archs = [] 
        else:
             quantile_combination_archs = best_qnt_info['combination'] 
             log(f"-> [전략 2] 퀀타일 앙상블 정보 로드 완료 (모델 {len(quantile_combination_archs)}개)")

    except FileNotFoundError as e: log(f"❌ 필수 파일 없음 (스케일러/피처/앙상블리포트/모델): {e}"); return
    except Exception as e: log(f"❌ 필수 파일 로드 실패: {e}"); return

    # ==========================================================
    # ⭐️ [V22.WinnerOnly] (수정) 2. 1차 챔피언 모델 *TopK* 로드
    # ==========================================================
    log("\n✅ [2/6] 1차 챔피언 모델(Top-K) 로드 및 동적 SeqLen 정보 취합 중...")
    
    models_classify_all: Dict[str, KM.Model] = {} # ⭐️ 'lstm_rank1', 'lstm_rank2', ...
    models_quantile: Dict[str, KM.Model] = {}       # ⭐️ 'lstm', 'gru', ...
    
    models_info_clf: Dict[str, Dict[int, Dict[str, Any]]] = {} # ⭐️ 'lstm': { 1: {...} }
    models_info_qnt: Dict[str, Dict[str, Any]] = {} # ⭐️ 'lstm': {...}
    
    max_seq_length_clf = 0 
    max_seq_length_q = 0   
    
    try:
        # --- 퀀타일 모델 로드 (단일 모델) ---
        for arch in ARCHITECTURES:
            q_version = f"v20_{arch}_quantile_regression"
            q_params_path = os.path.join(QUANTILE_BASE_DIR, q_version, "best_params.json")
            q_model_path = os.path.join(QUANTILE_BASE_DIR, q_version, 'quantile_model.h5')
            
            if os.path.exists(q_params_path) and os.path.exists(q_model_path):
                with open(q_params_path, 'r', encoding='utf-8') as f: q_params = json.load(f)
                seq_len = q_params.get('seq_length')
                if seq_len:
                    models_info_qnt[arch] = {'seq_length': seq_len}
                    max_seq_length_q = max(max_seq_length_q, seq_len) 
                    log(f"   -> 로드 중 (Q): '{arch}', SeqLen: {seq_len}")
                    models_quantile[arch] = KM.load_model(q_model_path, custom_objects=CUSTOM_OBJECTS, compile=False)

        # --- 분류 모델 로드 (Top-K 모두 로드) ---
        for arch in ARCHITECTURES:
            clf_version = f"v20_{arch}_classify_only"
            clf_params_path = os.path.join(CLASSIFY_BASE_DIR, clf_version, "best_params.json") 
            if not os.path.exists(clf_params_path):
                log(f"-> 경고: '{arch}' (classify) best_params.json 없음. 건너뜀.")
                continue
            
            with open(clf_params_path, 'r', encoding='utf-8') as f: clf_params = json.load(f)
            clf_seq_len = clf_params.get('seq_length')
            if not clf_seq_len:
                 log(f"-> 경고: '{arch}' (classify) best_params.json에 seq_length 없음. 건너뜀.")
                 continue
            
            models_info_clf[arch] = {} 
            
            for rank in range(1, TOP_K_MODELS_TO_LOAD + 1):
                model_path = os.path.join(CLASSIFY_BASE_DIR, clf_version, f'classification_model_rank{rank}.h5')
                
                if rank == 1 and not os.path.exists(model_path):
                     model_path = os.path.join(CLASSIFY_BASE_DIR, clf_version, 'classification_model.h5')
                
                if os.path.exists(model_path):
                    model_key = f"{arch}_rank{rank}" # 'lstm_rank1'
                    models_info_clf[arch][rank] = {'seq_length': clf_seq_len}
                    max_seq_length_clf = max(max_seq_length_clf, clf_seq_len) 
                    log(f"   -> 로드 중 (C): '{model_key}', SeqLen: {clf_seq_len}")
                    models_classify_all[model_key] = KM.load_model(model_path, custom_objects=CUSTOM_OBJECTS, compile=False)
        
        log(f"-> V20 챔피언 모델 {len(models_classify_all)}+{len(models_quantile)}개 로드 완료.")
        log(f"-> ⭐️ 동적 MAX_SEQ_LEN (분류): {max_seq_length_clf}")
        log(f"-> ⭐️ 동적 MAX_SEQ_LEN (퀀타일): {max_seq_length_q}")
        if not models_classify_all or not models_quantile:
            raise ValueError("분류 또는 퀀타일 모델 로드에 실패했습니다.")
        
    except Exception as e: log(f"❌ 모델 로드 실패: {e}"); return

    # --- 3. 최신 데이터 로드 및 전처리 (SQLite 기반) ---
    max_seq_len_global = max(max_seq_length_clf, max_seq_length_q)
    latest_data_df = load_data_from_sqlite(max_seq_len_global, feature_cols_ordered, SQLITE_DB_PATH)
    if latest_data_df is None: return

    # --- 4. 예측 대상일 계산 ---
    log("\n✅ [4/6] 예측 대상일 계산 중...")
    base_date = latest_data_df['date'].max().date()
    predict_target_date = get_next_trading_day(base_date)
    predict_date_str = predict_target_date.strftime('%Y-%m-%d') # ⭐️ 파일명용 날짜
    log(f"-> 예측 대상일: {predict_date_str}")

    # ==============================================================
    # ⭐️ [V22.WinnerOnly] 5. 주식별 예측 수행 (단일 트랙)
    # ==============================================================
    log("\n✅ [5/6] 주식별 1-Track 예측 및 후처리 수행 중...")

    # ⭐️ (V22.WinnerOnly) 후처리(리스크) 헬퍼 함수
    def execute_post_processing(
            decision: str, 
            q10_return: float, 
            q90_return: float, 
            current_close: float, 
            stock_code_for_risk: str
        ) -> Dict[str, Any]:
        try:
            ai_pred_return = q90_return if decision == "상승" else q10_return
            ai_pred_close = current_close * (1 + ai_pred_return)
            post1_pred_close = ai_pred_close
            risk_score = 0; policy_text = ""
            max_gain, max_loss = get_recent_volatility_limits_sqlite(stock_code_for_risk, SQLITE_DB_PATH)
            change_pct_candidate = (post1_pred_close - current_close) / current_close if current_close != 0 else 0.0
            final_t1_pred_close = post1_pred_close
            if not (-0.30 < change_pct_candidate < 0.30):
                risk_score, policy_text = 2, "[상하한 초과]"
                final_t1_pred_close = current_close * (1 + (0.30 if change_pct_candidate > 0 else -0.30))
            elif not (max_loss < change_pct_candidate < max_gain):
                risk_score, policy_text = 1, "[변동성 초과]"
                final_t1_pred_close = current_close * (1 + (max_gain if change_pct_candidate > 0 else max_loss))
            final_t1_pred_close = max(0, final_t1_pred_close)
            t1_change_percent = ((final_t1_pred_close - current_close) / current_close) * 100 if current_close != 0 else 0.0
            return {
                'post_pred_return': round(t1_change_percent, 2), 
                'post_pred_close': round(final_t1_pred_close, 0),
                'risk_score': risk_score, 
                'risk_policy_text': policy_text,
            }
        except Exception as e:
            log(f"   ⚠️ [{stock_code_for_risk}] 후처리 중 오류: {e}")
            return {
                'post_pred_return': 0.0, 'post_pred_close': round(current_close, 0),
                'risk_score': 99, 'risk_policy_text': "[오류]"
            }

    final_prediction_results = [] # ⭐️ 1등 앙상블 CSV 저장용
    individual_model_stats = []   # ⭐️ 개별 모델 로그 요약용

    # --- 주식별 루프 시작 ---
    for stock_code in TARGET_STOCKS:
        stock_name = stock_code_to_name.get(stock_code, stock_code)
        stock_df_orig = latest_data_df[latest_data_df['stock_code'] == stock_code]

        if len(stock_df_orig) < max_seq_len_global: 
            log(f"-> ⚠️ [{stock_name}] 데이터 부족 (필요: {max_seq_len_global}, 보유: {len(stock_df_orig)}), 건너뛰기.")
            continue
        try:
            latest_close_price = pd.to_numeric(stock_df_orig['close_pric'].iloc[-1], errors='coerce')
            if pd.isna(latest_close_price) or latest_close_price == 0:
                log(f"   -> [{stock_name}] 'close_pric' 누락. 'sma_20'으로 대체합니다.")
                latest_close_price = pd.to_numeric(stock_df_orig['sma_20'].iloc[-1], errors='coerce')
            if pd.isna(latest_close_price): raise ValueError("마지막 종가(close_pric, sma_20)가 모두 유효하지 않음")
        except (IndexError, ValueError, TypeError) as e:
            log(f"-> ⚠️ [{stock_name}] 마지막 종가 오류 ({e}), 건너뛰기.")
            continue
        if latest_close_price <= 10: log(f"-> ⚠️ [{stock_name}] 현재가 낮아 제외."); continue

        stock_preds_cls_prob_all: Dict[str, float] = {} # ⭐️ 'lstm_rank1' -> 0.45
        stock_preds_qnt: Dict[str, np.ndarray] = {}       # ⭐️ 'lstm' -> [q10, q50, q90]

        log(f"\n--- [{stock_name} ({stock_code})] 예측 시작 ---")
        log(f"   {'현재가:':<20} {latest_close_price:,.0f} 원 ({base_date.strftime('%Y-%m-%d')})")

        # 스케일링
        try:
            stock_df_tail = stock_df_orig.tail(max_seq_len_global + 10) 
            
            # ⭐️ [V22.ffill-fix-6] fillna(0)은 scaler.transform() *이전에* 수행되어야 함
            stock_df_tail_filled = stock_df_tail[feature_cols_ordered].fillna(0)
            
            stock_df_scaled_values = scaler.transform(stock_df_tail_filled.values)
            stock_df_scaled = pd.DataFrame(stock_df_scaled_values, index=stock_df_tail.index, columns=feature_cols_ordered)
            for col in ['stock_code', 'date']:
                if col in stock_df_tail: stock_df_scaled[col] = stock_df_tail[col]
        except Exception as e:
            log(f"   ⚠️ [{stock_name}] 스케일링 실패: {e}")
            continue

        # 5.1) ⭐️ [V22.TopK] 모든 개별 모델 예측 (분류 TopK + 퀀타일 단일)
        has_failed_prediction = False
        
        # --- (분류) Top-K 모델 예측 ---
        for model_key, model in models_classify_all.items(): # ⭐️ 'lstm_rank1', 'lstm_rank2', ...
            try:
                arch, rank_str = model_key.split('_rank')
                rank = int(rank_str)
                seq_len = models_info_clf[arch][rank]['seq_length']
                
                input_data = create_input_for_model(stock_df_scaled, seq_len, temporal_cols_ordered)
                preds = model.predict(input_data, verbose=0)
                stock_preds_cls_prob_all[model_key] = preds[0][0]
            except Exception as e:
                log(f"   ⚠️ [{stock_name}] {model_key} (classify) 예측 실패 (SeqLen={seq_len}): {e}")
                stock_preds_cls_prob_all[model_key] = np.nan
                has_failed_prediction = True
        
        # --- (퀀타일) 단일 모델 예측 ---
        for arch, model in models_quantile.items():
            try:
                seq_len = models_info_qnt[arch]['seq_length']
                input_data = create_input_for_model(stock_df_scaled, seq_len, temporal_cols_ordered)
                preds = model.predict(input_data, verbose=0)
                stock_preds_qnt[arch] = preds[0] / 100.0 # (100.0 스케일 복원)
            except Exception as e:
                log(f"   ⚠️ [{stock_name}] {arch} (quantile) 예측 실패 (SeqLen={seq_len}): {e}")
                stock_preds_qnt[arch] = np.array([np.nan] * len(QUANTILES))
                has_failed_prediction = True 

        if has_failed_prediction:
            log(f"   ❌ [{stock_name}] 일부 모델 예측 실패로 앙상블 예측을 건너뜁니다.")
            continue
            
        # 5.2) ⭐️ [V22.WinnerOnly] 개별 모델 상승/하락 예측 비율 계산
        for model_key, prob_up in stock_preds_cls_prob_all.items():
            decision_int = 1 if prob_up >= 0.5 else 0 
            individual_model_stats.append({
                'stock_code': stock_code,
                'model_key': model_key,
                'decision': decision_int, # 0 or 1
                'prob_up': prob_up
            })

        # 5.3) 앙상블 (방향성) 예측
        log("   --- [A] 앙상블 (방향성) 예측 ---")
        try:
            valid_weights_sum = sum(weighted_weights.get(key, 0) for key in weighted_combination_keys)
            weighted_score_pre_cal = sum(stock_preds_cls_prob_all[key] * weighted_weights.get(key, 0) for key in weighted_combination_keys)
            
            if valid_weights_sum == 0:
                log("   ⚠️ 1등 앙상블 가중치 합이 0. 균등 평균으로 대체.")
                weighted_score_pre_cal = np.mean([stock_preds_cls_prob_all[key] for key in weighted_combination_keys])
            else:
                weighted_score_pre_cal /= valid_weights_sum
            
            if weighted_calibrator_type == 'isotonic':
                weighted_avg_prob_up = meta_model_weighted_avg.transform(np.array([weighted_score_pre_cal]))[0]
            else: # 'platt'
                weighted_avg_prob_up = meta_model_weighted_avg.predict_proba(np.array([weighted_score_pre_cal]).reshape(-1, 1))[0, 1]
                
            weighted_avg_decision = "상승" if weighted_avg_prob_up >= weighted_threshold else "하락"
            log(f"   {'⭐️ 1등 앙상블(P):':<20} {weighted_avg_prob_up:.2%} -> {weighted_avg_decision}")
        except Exception as e:
            log(f"   ❌ [{stock_name}] 가중 평균 앙상블 예측 실패: {e}")
            weighted_avg_prob_up = 0.5; weighted_avg_decision = "하락" # 실패 시 기본값

        # 5.4) 앙상블 (변동성) 예측
        log("   --- [B] 앙상블 (변동성) 예측 ---")
        try:
            if not quantile_combination_archs:
                log("   ⚠️ 퀀타일 앙상블 정보가 없어 개별 LSTM 퀀타일로 대체합니다.")
                if 'lstm' in stock_preds_qnt:
                    ensemble_qnt = stock_preds_qnt['lstm']
                else:
                    raise ValueError("퀀타일 앙상블과 LSTM 퀀타일 모델 모두 사용 불가")
            else:
                valid_preds_qnt = [stock_preds_qnt[arch] for arch in quantile_combination_archs] 
                ensemble_qnt = np.mean(valid_preds_qnt, axis=0) # [q10, q50, q90]
            
            log(f"   {'퀀타일 앙상블(Q):':<20} [{ensemble_qnt[0]:.2%}, {ensemble_qnt[1]:.2%}, {ensemble_qnt[2]:.2%}]")
        except Exception as e:
            log(f"   ❌ [{stock_name}] 퀀타일 앙상블 예측 실패: {e}")
            ensemble_qnt = np.array([0.0, 0.0, 0.0]) 

        # 5.5) ⭐️ [V22.WinnerOnly] 1등 앙상블 *단일* 후처리 및 저장
        log("   --- [C] 1등 앙상블 후처리 및 저장 ---")
        
        common_data = {
            'predict_target_date': predict_date_str,
            'stock_code': stock_code, 'stock_name': stock_name, 
            'last_close_price': latest_close_price
        }

        post_results_w_avg = execute_post_processing(
            weighted_avg_decision, 
            ensemble_qnt[0],       
            ensemble_qnt[2],       
            latest_close_price, 
            stock_code
        )
        track_data_w_avg = {
            **common_data,
            'decision': weighted_avg_decision,
            'prob_up': round(weighted_avg_prob_up * 100, 2),
            'threshold': round(weighted_threshold, 3),
            'q10': round(ensemble_qnt[0] * 100, 2),
            'q50': round(ensemble_qnt[1] * 100, 2),
            'q90': round(ensemble_qnt[2] * 100, 2),
            **post_results_w_avg
        }
        final_prediction_results.append(track_data_w_avg)

    # --- 주식별 루프 종료 ---
    log("\n...모든 주식 예측 완료.")

    # ==============================================================
    # ⭐️ [V22.WinnerOnly] 6. 단일 CSV 파일 저장 + 개별 모델 통계 출력
    # ==============================================================
    log(f"\n✅ [6/6] ⭐️ 1등 앙상블 CSV 파일 저장 및 개별 모델 통계 출력 시작...")
    
    csv_columns = [
        'predict_target_date', 'stock_name', 'stock_code', 
        'decision', 'prob_up', 'threshold', 
        'q10', 'q50', 'q90',
        'post_pred_return', 'post_pred_close', 'last_close_price',
        'risk_score', 'risk_policy_text'
    ]

    # --- 6.1) 1등 앙상블 CSV 저장 ---
    if not final_prediction_results:
        log("-> ⚠️ 1등 앙상블 예측 결과 없음. CSV 저장 건너뛰기.")
    else:
        try:
            df_track = pd.DataFrame(final_prediction_results)
            final_cols = [col for col in csv_columns if col in df_track.columns]
            df_track = df_track[final_cols]
            
            csv_filename = os.path.join(LOGS_DIR, f"prediction_summary_v20_FINAL_WINNER_ONLY_{predict_date_str}.csv")
            
            df_track.round(4).to_csv(csv_filename, index=False, encoding='utf-8-sig')
            log(f"-> ✅ (1등 앙상블) CSV 파일 저장 성공 ({len(df_track)}건): {csv_filename}")
        except Exception as e:
            log(f"-> ❌ (1등 앙상블) CSV 저장 오류: {e}")

    # --- 6.2) 개별 모델 통계 요약 (로그 출력) ---
    if not individual_model_stats:
        log("-> ⚠️ 개별 모델 통계 없음. 요약 건너뛰기.")
    else:
        log("\n" + "="*50)
        log("✅ 참고용: 개별 챔피언 모델 상승 예측 비율 요약 (@ 0.5 Thr)")
        log("="*50)
        try:
            df_stats = pd.DataFrame(individual_model_stats)
            # ⭐️ model_key (e.g., 'lstm_rank1') 별로 상승 예측(decision=1)의 평균을 계산
            up_ratio_df = df_stats.groupby('model_key')['decision'].mean().reset_index()
            up_ratio_df.rename(columns={'decision': 'predicted_up_ratio'}, inplace=True)
            up_ratio_df['predicted_up_ratio'] = up_ratio_df['predicted_up_ratio'].round(4)
            up_ratio_df = up_ratio_df.sort_values(by='model_key')
            
            log(up_ratio_df.to_string(index=False))
        except Exception as e:
            log(f"-> ❌ 개별 모델 통계 요약 중 오류: {e}")

    log(f"\n🎉 V20 예측 (WINNER_ONLY) 작업 완료!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="V20 Final Prediction (Winner Only)")
    parser.add_argument("--db_date", type=str, default=None, help="YYYYMMDD 형식의 특정 DB 날짜 지정 (e.g., 20251103)")
    args = parser.parse_args()

    if args.db_date:
        log(f"-> 🔔 --db_date 인자 감지. '{args.db_date}' 날짜의 DB 파일을 사용합니다.")
        SQLITE_DB_PATH = os.path.join(project_root, f'predict_data_v20_{args.db_date}.db')
    else:
        log(f"-> 🔔 --db_date 인자 없음. 오늘 날짜('{today_db_str}')의 DB 파일을 사용합니다.")

    run_prediction()
