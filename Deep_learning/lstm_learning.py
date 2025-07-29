# deep_learning_context_walkforward.py
# 컨텍스트형 시퀀스 생성 + 워크‑포워드 재작성 (전체 코드)
# - 핵심: 기준일(Train/Val/Test)만 각 구간에 속하면, LSTM 입력 윈도우는 그 이전의 '컨텍스트'에서 가져오도록 구현
# - 평가: 근접도 중심(MAE/RMSE/R²) + 참고용 IC/롱숏
# - 분류헤드/임계값 최적화(Youden/F1) 및 캘리브레이션(선택) 유지

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from dotenv import load_dotenv
from sqlalchemy import create_engine

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score,
    roc_auc_score, roc_curve, accuracy_score,
    precision_recall_curve, precision_recall_fscore_support
)
from sklearn.linear_model import LogisticRegression

import tensorflow as tf
from tensorflow.keras.layers import (
    Input, LSTM, Dense, Dropout, LayerNormalization,
    Embedding, Concatenate, Flatten, Bidirectional, Attention
)
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

# ================================
# 0) CONFIG & Reproducibility
# ================================
SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)

RUN_SINGLE_HOLDOUT = True
RUN_WALKFORWARD   = True
DO_CALIBRATE      = True

TIME_STEPS = 15
HORIZON    = 5
LR_INIT    = 1e-3
EMB_DIM    = 16
ALPHA_CLS  = 0.3

LIQ_WINDOW    = 60
MIN_TURNOVER  = 1e8
MIN_PRICE     = 5000

TOP_FRAC      = 0.30
BOT_FRAC      = 0.30

MIN_N_IC      = 3
MIN_N_LS      = 5

WF_TRAIN_MONTHS = 18
WF_VAL_MONTHS   = 2
WF_TEST_MONTHS  = 1
WF_STEP_MONTHS  = 1

# ================================
# 1) Load env
# ================================
load_dotenv()
DB_USER     = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST     = os.getenv("DB_HOST")
DB_PORT     = os.getenv("DB_PORT")
DB_NAME     = os.getenv("DB_NAME")
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise EnvironmentError("DB 환경변수가 모두 설정되어야 합니다.")

# ================================
# 2) Load data
# ================================
engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
query = """
SELECT p.stk_cd, p.date, p.open_pric, p.high_pric, p.low_pric, p.close_pric,
       o.oyr_hgst, o.oyr_lwst, o.base_pric, o.cur_prc AS access_cur_prc, o.trde_qty,
       b.rank, b.acc_trde_qty,
       i.listcount
FROM price_data p
LEFT JOIN original_access_data o ON p.stk_cd = o.stk_cd
LEFT JOIN buyTop50_data b     ON p.stk_cd = b.stk_cd
LEFT JOIN infolist_data i     ON p.stk_cd = i.code
WHERE p.date IS NOT NULL
ORDER BY p.stk_cd, p.date;
"""
df = pd.read_sql(query, engine)

if np.issubdtype(df['date'].dtype, np.number):
    df['date'] = df['date'].astype(int).astype(str)
df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
df = df.sort_values(['stk_cd', 'date']).reset_index(drop=True)

numeric_cols = [c for c in df.columns if c not in ['stk_cd', 'date']]
df[numeric_cols] = df.groupby('stk_cd')[numeric_cols].ffill().bfill()
df[numeric_cols] = df[numeric_cols].fillna(0)
df = df[df['close_pric'] > 0]

# ================================
# 3) Preprocess & Features
# ================================
def add_indicators(g: pd.DataFrame) -> pd.DataFrame:
    g = g.copy()
    close = g['close_pric'].astype(float)
    high  = g['high_pric'].astype(float)
    low   = g['low_pric'].astype(float)
    vol   = g['trde_qty'].astype(float)

    # 기존 기술적 지표
    g['ma_5']  = close.rolling(5,  min_periods=1).mean()
    g['ma_10'] = close.rolling(10, min_periods=1).mean()
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.rolling(14, min_periods=1).mean()
    avg_loss = loss.rolling(14, min_periods=1).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    g['rsi_14'] = 100 - (100 / (1 + rs))
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    sig   = macd.ewm(span=9, adjust=False).mean()
    g['macd']        = macd
    g['macd_signal'] = sig
    g['ret_1d'] = np.log(close / close.shift(1)).replace([np.inf, -np.inf], 0).fillna(0)
    g['ret_5d'] = np.log(close / close.shift(5)).replace([np.inf, -np.inf], 0).fillna(0)
    g['vol_10d']       = g['ret_1d'].rolling(10, min_periods=1).std().fillna(0)
    g['close_ma10_dev'] = (close / (g['ma_10'] + 1e-9) - 1).fillna(0)
    g['turnover']       = (close * vol).fillna(0)
    g['turnover_ma60']  = g['turnover'].rolling(LIQ_WINDOW, min_periods=1).mean().fillna(0)
    vol_mean20 = vol.rolling(20, min_periods=1).mean()
    vol_std20  = vol.rolling(20, min_periods=1).std().replace(0, np.nan)
    g['vol_z_20'] = ((vol - vol_mean20) / (vol_std20 + 1e-9)).fillna(0)

    # 1) Bollinger Bands (20일, ±2σ)
    window_bb = 20
    g['bb_mid'] = close.rolling(window=window_bb, min_periods=1).mean()
    g['bb_std'] = close.rolling(window=window_bb, min_periods=1).std().fillna(0)
    g['bb_upper'] = g['bb_mid'] + 2 * g['bb_std']
    g['bb_lower'] = g['bb_mid'] - 2 * g['bb_std']

    # 2) True Range & ATR (14일)
    prev_close = close.shift(1).fillna(method='bfill')
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low  - prev_close).abs()
    g['true_range'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    window_atr = 14
    g['atr_14'] = g['true_range'].rolling(window=window_atr, min_periods=1).mean()

    return g

try:
    df = (
        df.groupby('stk_cd', group_keys=True)
          .apply(add_indicators, include_groups=False)
          .reset_index(level=0)
          .reset_index(drop=True)
    )
except TypeError:
    df = (
        df.groupby('stk_cd', group_keys=True)
          .apply(add_indicators)
          .reset_index(level=0)
          .reset_index(drop=True)
    )

# 타깃 설정
df['future_close']       = df.groupby('stk_cd')['close_pric'].shift(-HORIZON)
df['target_log']         = np.log(df['future_close'] / df['close_pric'])
df = df.dropna(subset=['target_log'])
mkt_by_date = df.groupby('date')['target_log'].mean().rename('mkt_target_log')
df = df.merge(mkt_by_date, on='date', how='left')
df['target_excess_log']  = df['target_log'] - df['mkt_target_log']
df = df[(df['target_excess_log'].abs() < 1.0)]
df['target_excess_log']  = df['target_excess_log'].clip(-0.4, 0.4)

# 시장 보정 피처
ret1d_mkt = df.groupby('date')['ret_1d'].mean().rename('mkt_ret_1d')
ret5d_mkt = df.groupby('date')['ret_5d'].mean().rename('mkt_ret_5d')
df = df.merge(ret1d_mkt, on='date', how='left').merge(ret5d_mkt, on='date', how='left')
df['xret_1d'] = df['ret_1d'] - df['mkt_ret_1d']
df['xret_5d'] = df['ret_5d'] - df['mkt_ret_5d']

# 필터
liq_mask = (df['turnover_ma60'] >= MIN_TURNOVER) & (df['close_pric'] >= MIN_PRICE)
df = df[liq_mask].copy()

# 사용할 피처 리스트에 추가
features = [
    'open_pric','high_pric','low_pric','close_pric',
    'oyr_hgst','oyr_lwst','base_pric','access_cur_prc',
    'trde_qty','rank','acc_trde_qty','listcount',
    'ma_5','ma_10','rsi_14','macd','macd_signal',
    'ret_1d','ret_5d','vol_10d','close_ma10_dev','vol_z_20',
    'xret_1d','xret_5d',
    'bb_mid','bb_std','bb_upper','bb_lower',
    'atr_14'
]
df = df.dropna(subset=features + ['target_excess_log'])

# 분류 라벨
df['pct_rank'] = df.groupby('date')['target_excess_log'].transform(
    lambda s: s.rank(pct=True, method='average')
)
df['y_cls_label'] = np.where(
    df['pct_rank'] >= (1 - TOP_FRAC), 1.0,
    np.where(df['pct_rank'] <= BOT_FRAC, 0.0, np.nan)
)

# 종목 임베딩
stk_map     = {s:i for i,s in enumerate(sorted(df['stk_cd'].unique()))}
df['stk_idx'] = df['stk_cd'].map(stk_map).astype('int32')
NUM_STOCKS  = len(stk_map)

# 이하 생략… (make_sequences_context, build_model, 평가 함수, run_single_holdout, run_walkforward, main 실행부)
# 위 add_indicators 부분만 복사해서 사용하시면 됩니다.


# ================================
# 4) Utils
# ================================
def fit_scalers(train_df):
    sx = StandardScaler(); sy = StandardScaler()
    sx.fit(train_df[features].astype(float).values)
    sy.fit(train_df[['target_excess_log']].astype(float).values)
    return sx, sy

def make_sequences_context(df_context: pd.DataFrame, scaler_x, scaler_y,
                           base_start: pd.Timestamp, base_end: pd.Timestamp):
    """
    컨텍스트형 시퀀스 생성:
    - 윈도우 끝(=기준일)이 [base_start, base_end] 범위에 있을 때만 샘플 채택
    - 입력 윈도우는 기준일 이전 TIME_STEPS-1일 포함(동일 종목의 과거 행)
    - y는 기준일의 target_excess_log (이미 전체 df에서 생성됨)
    """
    X_list, y_list, ycls_list, wcls_list, stkidx_list, meta_list = [], [], [], [], [], []
    for stk, g in df_context.groupby('stk_cd'):
        g = g.sort_values('date')
        if len(g) < TIME_STEPS:
            continue
        Xs = scaler_x.transform(g[features].astype(float).values)
        ys = scaler_y.transform(g[['target_excess_log']].astype(float).values).ravel()
        ycls = g['y_cls_label'].values
        dates = g['date'].values
        stk_idx = int(g['stk_idx'].iloc[0])
        # t: 윈도우 끝 index
        for t in range(TIME_STEPS-1, len(g)):
            base_date = pd.Timestamp(dates[t])
            if base_date < base_start or base_date > base_end:
                continue
            # target/label 존재 여부 체크
            y_t = ys[t]
            if np.isnan(y_t):
                continue
            X_win = Xs[t - (TIME_STEPS-1): t + 1]
            if X_win.shape[0] != TIME_STEPS:
                continue
            X_list.append(X_win)
            y_list.append(y_t)
            lab = ycls[t]
            if np.isnan(lab):
                ycls_list.append(0.0); wcls_list.append(0.0)
            else:
                ycls_list.append(float(lab)); wcls_list.append(1.0)
            stkidx_list.append(stk_idx)
            meta_list.append({'stk_cd': stk, 'base_date': base_date})
    if not X_list:
        return (np.empty((0, TIME_STEPS, len(features))),
                np.empty((0,)), np.empty((0,)), np.empty((0,)),
                np.empty((0,), dtype='int32'), [])
    return (np.array(X_list), np.array(y_list), np.array(ycls_list),
            np.array(wcls_list), np.array(stkidx_list, dtype='int32'), meta_list)

def build_model(num_stocks, emb_dim=EMB_DIM, alpha_cls=ALPHA_CLS, lr=LR_INIT):
    seq_input = Input(shape=(TIME_STEPS, len(features)), name='seq')
    stk_input = Input(shape=(), dtype='int32', name='stk_idx')

    x = LSTM(64, return_sequences=True, dropout=0.1, recurrent_dropout=0.1)(seq_input)
    x = LayerNormalization()(x)
    x = Dropout(0.2)(x)
    x = LSTM(32, dropout=0.1, recurrent_dropout=0.1)(x)
    x = LayerNormalization()(x)

    emb = Embedding(input_dim=num_stocks, output_dim=emb_dim, name='stk_emb')(stk_input)
    emb = Flatten()(emb)
    h = Concatenate()([x, emb])
    h = Dense(64, activation='relu')(h)
    h = Dropout(0.2)(h)

    y_reg = Dense(1, name='y_reg')(h)
    y_cls = Dense(1, activation='sigmoid', name='y_cls')(h)

    model = Model(inputs=[seq_input, stk_input], outputs=[y_reg, y_cls])
    model.compile(
        optimizer=Adam(learning_rate=lr),
        loss=[tf.keras.losses.Huber(delta=1.0), 'binary_crossentropy'],
        loss_weights=[1.0, alpha_cls],
        metrics=[['mae'], ['accuracy', tf.keras.metrics.AUC(name='auc')]]
    )
    return model

def find_youden_threshold(y_true_bin, y_prob):
    if len(np.unique(y_true_bin)) < 2:
        return 0.5, np.nan, np.nan
    fpr, tpr, thr = roc_curve(y_true_bin, y_prob)
    j = tpr - fpr
    idx = np.argmax(j)
    return float(thr[idx]), float(tpr[idx]), float(fpr[idx])

def find_f1_threshold(y_true_bin, y_prob):
    if len(np.unique(y_true_bin)) < 2:
        return 0.5, np.nan
    precision, recall, thr = precision_recall_curve(y_true_bin, y_prob)
    thr = np.append(thr, 1.0)
    f1 = 2 * precision * recall / (precision + recall + 1e-9)
    idx = np.nanargmax(f1)
    return float(thr[idx]), float(f1[idx])

def platt_calibrate(y_true_bin, y_prob):
    uniq = np.unique(y_true_bin)
    if len(uniq) < 2:
        return None
    eps = 1e-6
    score = np.log(np.clip(y_prob, eps, 1-eps) / np.clip(1-y_prob, eps, 1-eps))
    lr = LogisticRegression(solver='liblinear')
    lr.fit(score.reshape(-1,1), y_true_bin.astype(int))
    return lr

def apply_calibrator(lr, y_prob):
    if lr is None:
        return y_prob
    eps = 1e-6
    score = np.log(np.clip(y_prob, eps, 1-eps) / np.clip(1-y_prob, eps, 1-eps))
    return lr.predict_proba(score.reshape(-1,1))[:,1]

def daily_ic(df_in: pd.DataFrame, col_pred: str, col_true: str, min_n: int = MIN_N_IC):
    from scipy.stats import spearmanr
    ics = []
    for d, g in df_in.groupby('date'):
        g = g[[col_pred, col_true]].dropna()
        if len(g) >= min_n:
            ic, _ = spearmanr(g[col_pred], g[col_true])
            if not np.isnan(ic):
                ics.append({'date': d, 'ic': ic})
    if len(ics) == 0:
        return pd.DataFrame(columns=['date','ic'])
    return pd.DataFrame(ics).sort_values('date').reset_index(drop=True)

def agg_ic_stats(ic_df: pd.DataFrame, freq: str = 'M'):
    if ic_df.empty:
        return pd.DataFrame()
    out = ic_df.copy()
    out['period'] = out['date'].dt.to_period(freq)
    res = (out.groupby('period')['ic']
           .agg(['mean','std','count'])
           .rename(columns={'count':'n'})
           .reset_index())
    res['t_stat'] = res['mean'] / (res['std'] / np.sqrt(res['n']))
    return res

def daily_long_short_spread(df_in: pd.DataFrame, pred_col='pred_excess', true_col='true_excess',
                            top_frac=0.2, min_n=MIN_N_LS):
    res = []
    for d, g in df_in.groupby('date'):
        g = g[['stk_cd', pred_col, true_col]].dropna()
        n = len(g)
        if n < min_n:
            continue
        k = max(1, int(n * top_frac))
        g = g.sort_values(pred_col)
        bottom = g.iloc[:k]; top = g.iloc[-k:]
        r_top = top[true_col].mean(); r_bot = bottom[true_col].mean()
        spread = r_top - r_bot
        hit_rate = (top[true_col] > 0).mean()
        res.append({'date': d, 'n': n, 'k': k, 'spread': spread, 'top_hit': hit_rate,
                    'r_top': r_top, 'r_bot': r_bot})
    if not res:
        return pd.DataFrame(columns=['date','n','k','spread','top_hit','r_top','r_bot'])
    return pd.DataFrame(res).sort_values('date').reset_index(drop=True)

# ================================
# 5) Single holdout (컨텍스트 사용)
# ================================
def run_single_holdout(full_df: pd.DataFrame):
    df_sorted = full_df.sort_values(['date','stk_cd']).reset_index(drop=True)
    split_idx = int(len(df_sorted) * 0.8)
    train_all = df_sorted.iloc[:split_idx].copy()
    test_all  = df_sorted.iloc[split_idx:].copy()
    val_size = int(len(train_all) * 0.1)
    train_df = train_all.iloc[:-val_size].copy()
    val_df   = train_all.iloc[-val_size:].copy()

    # 구간 경계 정의
    tr_s, tr_e = train_df['date'].min(), train_df['date'].max()
    va_s, va_e = val_df['date'].min(),   val_df['date'].max()
    te_s, te_e = test_all['date'].min(), test_all['date'].max()

    scaler_x, scaler_y = fit_scalers(train_df)

    # 컨텍스트는 각 구간 종료일까지 포함
    X_tr, y_tr, ycls_tr, wcls_tr, stk_tr, meta_tr = make_sequences_context(
        df_context=df_sorted[df_sorted['date']<=tr_e], scaler_x=scaler_x, scaler_y=scaler_y,
        base_start=tr_s, base_end=tr_e
    )
    X_va, y_va, ycls_va, wcls_va, stk_va, meta_va = make_sequences_context(
        df_context=df_sorted[df_sorted['date']<=va_e], scaler_x=scaler_x, scaler_y=scaler_y,
        base_start=va_s, base_end=va_e
    )
    X_te, y_te, ycls_te, wcls_te, stk_te, meta_te = make_sequences_context(
        df_context=df_sorted[df_sorted['date']<=te_e], scaler_x=scaler_x, scaler_y=scaler_y,
        base_start=te_s, base_end=te_e
    )

    print(f"Train seq: {X_tr.shape}, Val seq: {X_va.shape}, Test seq: {X_te.shape}")

    baseline_pred_scaled = np.full_like(y_te, y_tr.mean()) if y_tr.size>0 else np.array([])
    if baseline_pred_scaled.size>0:
        baseline_pred_log = scaler_y.inverse_transform(baseline_pred_scaled.reshape(-1,1)).ravel()
        baseline = np.exp(baseline_pred_log) - 1

    # 분류 불균형 가중치
    wcls_tr_bal = wcls_tr.copy().astype('float32')
    mask_pos = (ycls_tr > 0.5) & (wcls_tr_bal > 0)
    mask_neg = (ycls_tr < 0.5) & (wcls_tr_bal > 0)
    pos_n, neg_n = mask_pos.sum(), mask_neg.sum()
    if pos_n > 0 and neg_n > 0:
        tot = pos_n + neg_n
        pos_w = tot / (2.0 * pos_n)
        neg_w = tot / (2.0 * neg_n)
        scale = np.where(ycls_tr > 0.5, pos_w, neg_w)
        wcls_tr_bal = wcls_tr_bal * scale.astype('float32')

    model = build_model(NUM_STOCKS)
    cbs = [
        EarlyStopping(monitor='val_y_reg_mae', mode='min', patience=10, restore_best_weights=True),
        ReduceLROnPlateau(monitor='val_y_reg_mae', mode='min', patience=5, factor=0.5, verbose=1, min_lr=1e-5)
    ]
    if X_tr.shape[0] > 0 and X_va.shape[0] > 0:
        history = model.fit(
            [X_tr, stk_tr], [y_tr, ycls_tr],
            validation_data=([X_va, stk_va], [y_va, ycls_va], [np.ones_like(y_va, dtype='float32'), wcls_va.astype('float32')]),
            epochs=100, batch_size=64,
            callbacks=cbs,
            sample_weight=[np.ones_like(y_tr, dtype='float32'), wcls_tr_bal],
            verbose=1
        )
    else:
        print("[경고] 홀드아웃 학습용 샘플 부족")
        return

    # Test 예측
    y_pred_scaled, y_prob = model.predict([X_te, stk_te], verbose=0)
    y_pred_scaled = y_pred_scaled.ravel(); y_prob = y_prob.ravel()
    y_pred_log = scaler_y.inverse_transform(y_pred_scaled.reshape(-1,1)).ravel()
    y_true_log = scaler_y.inverse_transform(y_te.reshape(-1,1)).ravel()
    y_pred = np.exp(y_pred_log) - 1; y_true = np.exp(y_true_log) - 1

    mse = mean_squared_error(y_true, y_pred)
    mae = mean_absolute_error(y_true, y_pred)
    r2  = r2_score(y_true, y_pred)
    dir_acc = (np.sign(y_pred) == np.sign(y_true)).mean()
    print(f"Model (reg head) MSE: {mse:.6f}, MAE: {mae:.6f}, R2: {r2:.3f}, Direction Acc(reg): {dir_acc:.3f}")

    # Val 기반 임계값/캘리브레이션
    _, y_prob_va = model.predict([X_va, stk_va], verbose=0)
    y_prob_va = y_prob_va.ravel()
    mask_va = wcls_va > 0
    if mask_va.sum() > 0:
        y_true_va_bin = (ycls_va[mask_va] > 0.5).astype(int)
        calibrator = platt_calibrate(y_true_va_bin, y_prob_va[mask_va]) if DO_CALIBRATE else None
        y_prob_va_eval = apply_calibrator(calibrator, y_prob_va) if calibrator is not None else y_prob_va
        thr_j, _tpr, _fpr = find_youden_threshold(y_true_va_bin, y_prob_va_eval[mask_va])
        thr_f1, _ = find_f1_threshold(y_true_va_bin, y_prob_va_eval[mask_va])
    else:
        calibrator = None
        thr_j, thr_f1 = 0.5, 0.5

    # Test 분류 메트릭(참고용)
    mask_te = wcls_te > 0
    if mask_te.sum() > 0:
        y_true_cls = (ycls_te[mask_te] > 0.5).astype(int)
        y_prob_eval = apply_calibrator(calibrator, y_prob) if calibrator is not None else y_prob
        y_prob_eval = y_prob_eval[mask_te]
        acc05 = accuracy_score(y_true_cls, (y_prob_eval >= 0.5).astype(int)) if len(np.unique(y_true_cls))>1 else np.nan
        auc_  = roc_auc_score(y_true_cls, y_prob_eval) if len(np.unique(y_true_cls))>1 else np.nan
        pred_j  = (y_prob_eval >= thr_j).astype(int)
        acc_j   = accuracy_score(y_true_cls, pred_j)
        p_j, r_j, f1_j, _ = precision_recall_fscore_support(y_true_cls, pred_j, average='binary', zero_division=0)
        pred_f1 = (y_prob_eval >= thr_f1).astype(int)
        acc_f1  = accuracy_score(y_true_cls, pred_f1)
        p_f1, r_f1, f1_f1, _ = precision_recall_fscore_support(y_true_cls, pred_f1, average='binary', zero_division=0)
        print(f"(Cls@0.5) Acc: {acc05:.3f}, AUC: {auc_:.3f} | (Youden {thr_j:.3f}) Acc/P/R/F1: {acc_j:.3f}/{p_j:.3f}/{r_j:.3f}/{f1_j:.3f} | (F1 {thr_f1:.3f}) Acc/P/R/F1: {acc_f1:.3f}/{p_f1:.3f}/{r_f1:.3f}/{f1_f1:.3f}")

    # 근접도 외 참고용: 단면 IC / 롱숏
    eval_df = pd.DataFrame({
        'date': pd.to_datetime([m['base_date'] for m in meta_te]),
        'stk_cd': [m['stk_cd'] for m in meta_te],
        'pred_excess': y_pred,
        'true_excess': y_true
    })
    ic_daily = daily_ic(eval_df, 'pred_excess', 'true_excess', min_n=MIN_N_IC)
    print("\n[Daily Spearman IC] head")
    print(ic_daily.head().to_string(index=False))
    if not ic_daily.empty:
        print(f"Overall mean IC: {ic_daily['ic'].mean():.4f}, std: {ic_daily['ic'].std():.4f}, n_days: {len(ic_daily)}")
    print("\n[Monthly IC stats] (mean, std, n, t)")
    print(agg_ic_stats(ic_daily, 'M').to_string(index=False))

# ================================
# 6) Walk-forward (컨텍스트 사용)
# ================================
def month_floor(d): return pd.Timestamp(d.year, d.month, 1)
def add_months(ts, m):
    y = ts.year + (ts.month - 1 + m) // 12
    mo = (ts.month - 1 + m) % 12 + 1
    return pd.Timestamp(y, mo, 1)

def run_walkforward(full_df: pd.DataFrame):
    print("\n===== Walk-Forward Evaluation (Monthly roll, context-aware) =====")
    dmin, dmax = full_df['date'].min(), full_df['date'].max()
    start_month = month_floor(dmin)

    folds = []
    cur = start_month
    while True:
        tr_s = cur
        tr_e = add_months(tr_s, WF_TRAIN_MONTHS) - pd.offsets.Day(1)
        va_s = add_months(tr_s, WF_TRAIN_MONTHS)
        va_e = add_months(va_s, WF_VAL_MONTHS) - pd.offsets.Day(1)
        te_s = add_months(va_s, WF_VAL_MONTHS)
        te_e = add_months(te_s, WF_TEST_MONTHS) - pd.offsets.Day(1)
        if te_e > dmax:
            break
        folds.append((tr_s, tr_e, va_s, va_e, te_s, te_e))
        cur = add_months(cur, WF_STEP_MONTHS)
    print(f"Total folds: {len(folds)}")

    fold_summaries = []
    all_daily_ic = []

    for fi, (tr_s, tr_e, va_s, va_e, te_s, te_e) in enumerate(folds, 1):
        print(f"\n--- Fold {fi} ---")
        print(f"Train: {tr_s.date()} ~ {tr_e.date()} | Val: {va_s.date()} ~ {va_e.date()} | Test: {te_s.date()} ~ {te_e.date()}")

        df_tr = full_df[(full_df['date']>=tr_s) & (full_df['date']<=tr_e)].copy()
        df_va = full_df[(full_df['date']>=va_s) & (full_df['date']<=va_e)].copy()
        df_te = full_df[(full_df['date']>=te_s) & (full_df['date']<=te_e)].copy()

        if df_tr.empty or df_va.empty or df_te.empty:
            print(" [skip] 구간 데이터 부족"); continue

        scaler_x, scaler_y = fit_scalers(df_tr)

        # 컨텍스트 포함: 윈도우 과거를 위해 각 구간의 종료일까지의 데이터 제공
        X_tr, y_tr, ycls_tr, wcls_tr, stk_tr, meta_tr = make_sequences_context(
            df_context=full_df[full_df['date']<=tr_e], scaler_x=scaler_x, scaler_y=scaler_y,
            base_start=tr_s, base_end=tr_e
        )
        X_va, y_va, ycls_va, wcls_va, stk_va, meta_va = make_sequences_context(
            df_context=full_df[full_df['date']<=va_e], scaler_x=scaler_x, scaler_y=scaler_y,
            base_start=va_s, base_end=va_e
        )
        X_te, y_te, ycls_te, wcls_te, stk_te, meta_te = make_sequences_context(
            df_context=full_df[full_df['date']<=te_e], scaler_x=scaler_x, scaler_y=scaler_y,
            base_start=te_s, base_end=te_e
        )
        print(f"  seq shapes → Train {X_tr.shape} | Val {X_va.shape} | Test {X_te.shape}")

        if X_tr.shape[0] < 100 or X_va.shape[0] < 20 or X_te.shape[0] < 20:
            print(" [skip] 시퀀스 수 부족"); continue

        # 분류 불균형 가중치
        wcls_tr_bal = wcls_tr.copy().astype('float32')
        mask_pos = (ycls_tr > 0.5) & (wcls_tr_bal > 0)
        mask_neg = (ycls_tr < 0.5) & (wcls_tr_bal > 0)
        pos_n, neg_n = mask_pos.sum(), mask_neg.sum()
        if pos_n > 0 and neg_n > 0:
            tot = pos_n + neg_n
            pos_w = tot / (2.0 * pos_n)
            neg_w = tot / (2.0 * neg_n)
            scale = np.where(ycls_tr > 0.5, pos_w, neg_w)
            wcls_tr_bal = wcls_tr_bal * scale.astype('float32')
        else:
            print("  [경고] 분류 클래스 치우침 → 불균형 가중치 미적용")

        model = build_model(NUM_STOCKS)
        cbs = [
            EarlyStopping(monitor='val_y_reg_mae', mode='min', patience=10, restore_best_weights=True),
            ReduceLROnPlateau(monitor='val_y_reg_mae', mode='min', patience=5, factor=0.5, verbose=1, min_lr=1e-5)
        ]
        model.fit(
            [X_tr, stk_tr], [y_tr, ycls_tr],
            validation_data=([X_va, stk_va], [y_va, ycls_va], [np.ones_like(y_va, dtype='float32'), wcls_va.astype('float32')]),
            epochs=100, batch_size=64, callbacks=cbs,
            sample_weight=[np.ones_like(y_tr, dtype='float32'), wcls_tr_bal],
            verbose=0
        )

        # 예측
        y_pred_scaled, y_prob = model.predict([X_te, stk_te], verbose=0)
        y_pred_scaled = y_pred_scaled.ravel(); y_prob = y_prob.ravel()
        y_pred_log = scaler_y.inverse_transform(y_pred_scaled.reshape(-1,1)).ravel()
        y_true_log = scaler_y.inverse_transform(y_te.reshape(-1,1)).ravel()
        y_pred = np.exp(y_pred_log) - 1; y_true = np.exp(y_true_log) - 1

        # Val 기반 임계값/캘리브레이션
        _, y_prob_va = model.predict([X_va, stk_va], verbose=0)
        y_prob_va = y_prob_va.ravel()
        mask_va = wcls_va > 0
        if mask_va.sum() > 0:
            y_true_va_bin = (ycls_va[mask_va] > 0.5).astype(int)
            calibrator = platt_calibrate(y_true_va_bin, y_prob_va[mask_va]) if DO_CALIBRATE else None
            y_prob_va_eval = apply_calibrator(calibrator, y_prob_va) if calibrator is not None else y_prob_va
            thr_j, _tpr, _fpr = find_youden_threshold(y_true_va_bin, y_prob_va_eval[mask_va])
            thr_f1, f1_val = find_f1_threshold(y_true_va_bin, y_prob_va_eval[mask_va])
        else:
            calibrator = None
            thr_j, thr_f1 = 0.5, 0.5

        # 근접도(회귀) 평가
        mse = mean_squared_error(y_true, y_pred)
        mae = mean_absolute_error(y_true, y_pred)
        r2  = r2_score(y_true, y_pred)
        dir_acc = (np.sign(y_pred) == np.sign(y_true)).mean()
        print(f"  [Test] Reg → MAE {mae:.4f}, RMSE {np.sqrt(mse):.4f}, R2 {r2:.3f}, DirAcc {dir_acc:.3f}")

        # 참고: 분류 메트릭
        mask_te = wcls_te > 0
        if mask_te.sum() > 0:
            y_true_cls = (ycls_te[mask_te] > 0.5).astype(int)
            y_prob_eval = apply_calibrator(calibrator, y_prob) if calibrator is not None else y_prob
            y_prob_eval = y_prob_eval[mask_te]
            auc_ = roc_auc_score(y_true_cls, y_prob_eval) if len(np.unique(y_true_cls))>1 else np.nan
            pred_j  = (y_prob_eval >= thr_j).astype(int)
            acc_j   = accuracy_score(y_true_cls, pred_j) if len(np.unique(y_true_cls))>1 else np.nan
            _, _, f1_j, _ = precision_recall_fscore_support(y_true_cls, pred_j, average='binary', zero_division=0)
        else:
            auc_ = acc_j = f1_j = np.nan

        # IC / 롱숏 (참고)
        eval_df = pd.DataFrame({
            'date': pd.to_datetime([m['base_date'] for m in meta_te]),
            'stk_cd': [m['stk_cd'] for m in meta_te],
            'pred_excess': y_pred,
            'true_excess': y_true
        })
        ic_daily = daily_ic(eval_df, 'pred_excess', 'true_excess', min_n=MIN_N_IC)
        ls = daily_long_short_spread(eval_df, 'pred_excess', 'true_excess', top_frac=0.2, min_n=MIN_N_LS)
        all_daily_ic.append(ic_daily)

        fold_summaries.append({
            'fold': fi,
            'train': f"{tr_s.date()}~{tr_e.date()}",
            'val':   f"{va_s.date()}~{va_e.date()}",
            'test':  f"{te_s.date()}~{te_e.date()}",
            'test_days': len(ic_daily),
            'ic_mean': ic_daily['ic'].mean() if not ic_daily.empty else np.nan,
            'ls_mean_spread': ls['spread'].mean() if not ls.empty else np.nan,
            'mae': mae,
            'rmse': np.sqrt(mse),
            'r2': r2,
            'dir_acc': dir_acc,
            'auc': auc_,
            'acc_youden': acc_j,
            'f1_youden': f1_j
        })

    if fold_summaries:
        summ = pd.DataFrame(fold_summaries)
        print("\n[Walk-Forward Fold Summary]")
        print(summ[['fold','test','test_days','mae','rmse','r2','dir_acc','ic_mean','ls_mean_spread','auc']].to_string(index=False))
        print("\nOverall means (ignore NaN):")
        print(summ[['mae','rmse','r2','dir_acc','ic_mean','ls_mean_spread','auc']].mean(numeric_only=True))

    if any([not d.empty for d in all_daily_ic]):
        ic_all = pd.concat([d for d in all_daily_ic if not d.empty], axis=0)
        print("\n[Walk-Forward Monthly IC stats]")
        print(agg_ic_stats(ic_all, 'M').to_string(index=False))

# ================================
# 7) Run
# ================================
if RUN_SINGLE_HOLDOUT:
    print("===== Single Holdout Evaluation (context-aware) =====")
    run_single_holdout(df)

if RUN_WALKFORWARD:
    run_walkforward(df)
