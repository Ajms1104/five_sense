# deep_learning_v1.py
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score,
    roc_auc_score, roc_curve, accuracy_score, precision_recall_fscore_support
)
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow.keras.layers import LSTM, Dense, Dropout, LayerNormalization, Embedding, Input, Concatenate
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

# ================================
# 0) CONFIG & Reproducibility
# ================================
SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)

TIME_STEPS = 15
HORIZON = 5
LR_INIT = 1e-3
EMB_DIM = 16
ALPHA_CLS = 0.3

# (C) 유동성/가격 필터 - 완화
LIQ_WINDOW = 60
MIN_TURNOVER = 2e8        # <- 2e8로 완화
MIN_PRICE = 5000

# (B) 분류 라벨 기준
TOP_FRAC = 0.30
BOT_FRAC = 0.30

# ================================
# 1) Load environment variables
# ================================
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise EnvironmentError("DB 환경변수가 모두 설정되어야 합니다.")

# ================================
# 2) DB connection & data load
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

# ================================
# 3) Preprocessing
# ================================
if np.issubdtype(df['date'].dtype, np.number):
    df['date'] = df['date'].astype(int).astype(str)
df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
df = df.sort_values(['stk_cd', 'date']).reset_index(drop=True)

numeric_cols = [c for c in df.columns if c not in ['stk_cd', 'date']]
df[numeric_cols] = df.groupby('stk_cd')[numeric_cols].ffill().bfill()
df[numeric_cols] = df[numeric_cols].fillna(0)
df = df[df['close_pric'] > 0]

def add_indicators(g: pd.DataFrame) -> pd.DataFrame:
    g = g.copy()
    close = g['close_pric'].astype(float)
    vol = g['trde_qty'].astype(float)
    g['ma_5'] = close.rolling(5, min_periods=1).mean()
    g['ma_10'] = close.rolling(10, min_periods=1).mean()
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14, min_periods=1).mean()
    avg_loss = loss.rolling(14, min_periods=1).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    g['rsi_14'] = 100 - (100 / (1 + rs))
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    g['macd'] = macd
    g['macd_signal'] = signal
    g['ret_1d'] = np.log(close / close.shift(1)).replace([np.inf, -np.inf], 0).fillna(0)
    g['ret_5d'] = np.log(close / close.shift(5)).replace([np.inf, -np.inf], 0).fillna(0)
    g['vol_10d'] = g['ret_1d'].rolling(10, min_periods=1).std().fillna(0)
    g['close_ma10_dev'] = (close / (g['ma_10'] + 1e-9) - 1).fillna(0)
    g['turnover'] = (close * vol).fillna(0)
    g['turnover_ma60'] = g['turnover'].rolling(LIQ_WINDOW, min_periods=1).mean().fillna(0)
    vol_mean20 = vol.rolling(20, min_periods=1).mean()
    vol_std20  = vol.rolling(20, min_periods=1).std().replace(0, np.nan)
    g['vol_z_20'] = ((vol - vol_mean20) / (vol_std20 + 1e-9)).fillna(0)
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
assert 'stk_cd' in df.columns

df['future_close'] = df.groupby('stk_cd')['close_pric'].shift(-HORIZON)
df['target_log']   = np.log(df['future_close'] / df['close_pric'])
df = df.dropna(subset=['target_log'])

mkt_by_date = df.groupby('date')['target_log'].mean().rename('mkt_target_log')
df = df.merge(mkt_by_date, on='date', how='left')
df['target_excess_log'] = df['target_log'] - df['mkt_target_log']

df = df[(df['target_excess_log'].abs() < 1.0)]
df['target_excess_log'] = df['target_excess_log'].clip(-0.4, 0.4)

ret1d_mkt = df.groupby('date')['ret_1d'].mean().rename('mkt_ret_1d')
ret5d_mkt = df.groupby('date')['ret_5d'].mean().rename('mkt_ret_5d')
df = df.merge(ret1d_mkt, on='date', how='left').merge(ret5d_mkt, on='date', how='left')
df['xret_1d'] = df['ret_1d'] - df['mkt_ret_1d']
df['xret_5d'] = df['ret_5d'] - df['mkt_ret_5d']

liq_mask = (df['turnover_ma60'] >= MIN_TURNOVER) & (df['close_pric'] >= MIN_PRICE)
df = df[liq_mask].copy()

features = [
    'open_pric','high_pric','low_pric','close_pric',
    'oyr_hgst','oyr_lwst','base_pric','access_cur_prc',
    'trde_qty','rank','acc_trde_qty','listcount',
    'ma_5','ma_10','rsi_14','macd','macd_signal',
    'ret_1d','ret_5d','vol_10d','close_ma10_dev','vol_z_20',
    'xret_1d','xret_5d'
]
df = df.dropna(subset=features + ['target_excess_log'])

# (B) 상/하 30% 라벨
df['pct_rank'] = df.groupby('date')['target_excess_log'].transform(
    lambda s: s.rank(pct=True, method='average')
)
df['y_cls_label'] = np.where(
    df['pct_rank'] >= (1 - TOP_FRAC), 1.0,
    np.where(df['pct_rank'] <= BOT_FRAC, 0.0, np.nan)
)

# 종목 인덱스
stk_map = {s:i for i,s in enumerate(sorted(df['stk_cd'].unique()))}
df['stk_idx'] = df['stk_cd'].map(stk_map).astype('int32')
NUM_STOCKS = len(stk_map)

# ================================
# 4) Split
# ================================
df = df.sort_values(['date', 'stk_cd']).reset_index(drop=True)
split_idx = int(len(df) * 0.8)
train_all = df.iloc[:split_idx].copy()
test_df  = df.iloc[split_idx:].copy()
val_size = int(len(train_all) * 0.1)
train_df = train_all.iloc[:-val_size].copy()
val_df   = train_all.iloc[-val_size:].copy()

# ================================
# 5) Scalers
# ================================
scaler_x = StandardScaler()
scaler_y = StandardScaler()
scaler_x.fit(train_df[features].astype(float).values)
scaler_y.fit(train_df[['target_excess_log']].astype(float).values)

# ================================
# 6) Sequences
# ================================
def make_sequences(df_part: pd.DataFrame):
    X_list, y_list, ycls_list, wcls_list, stkidx_list, meta_list = [], [], [], [], [], []
    for stk, g in df_part.groupby('stk_cd'):
        g = g.sort_values('date')
        if len(g) < TIME_STEPS:
            continue
        X_scaled = scaler_x.transform(g[features].astype(float).values)
        y_scaled = scaler_y.transform(g[['target_excess_log']].astype(float).values).ravel()
        y_cls    = g['y_cls_label'].values
        dates    = g['date'].values
        stk_idx  = g['stk_idx'].values[0]
        for i in range(len(g) - TIME_STEPS):
            X_list.append(X_scaled[i:i+TIME_STEPS])
            y_list.append(y_scaled[i + TIME_STEPS - 1])
            lab = y_cls[i + TIME_STEPS - 1]
            if np.isnan(lab):
                ycls_list.append(0.0); wcls_list.append(0.0)
            else:
                ycls_list.append(float(lab)); wcls_list.append(1.0)
            stkidx_list.append(stk_idx)
            meta_list.append({'stk_cd': stk, 'base_date': dates[i + TIME_STEPS - 1]})
    if not X_list:
        return (np.empty((0, TIME_STEPS, len(features))),
                np.empty((0,)), np.empty((0,)), np.empty((0,)),
                np.empty((0,), dtype='int32'), [])
    return (np.array(X_list), np.array(y_list), np.array(ycls_list),
            np.array(wcls_list), np.array(stkidx_list, dtype='int32'), meta_list)

X_train_seq, y_train_seq, ycls_train, wcls_train, stk_train, meta_train = make_sequences(train_df)
X_val_seq,   y_val_seq,   ycls_val,   wcls_val,   stk_val,   meta_val   = make_sequences(val_df)
X_test_seq,  y_test_seq,  ycls_test,  wcls_test,  stk_test,  meta_test  = make_sequences(test_df)

print(f"Train seq: {X_train_seq.shape}, Val seq: {X_val_seq.shape}, Test seq: {X_test_seq.shape}")
if X_train_seq.shape[0] < 200:
    print("[경고] 학습 시퀀스가 적습니다. 필터/기간을 조정해 보세요.")

# Baseline
baseline_pred_scaled = np.full_like(y_test_seq, y_train_seq.mean())
baseline_mae_scaled = mean_absolute_error(y_test_seq, baseline_pred_scaled)
baseline_pred_excess_log = scaler_y.inverse_transform(baseline_pred_scaled.reshape(-1,1)).ravel()
print(f"Baseline MAE (scaled): {baseline_mae_scaled:.4f}")

# ================================
# 8) Model
# ================================
seq_input = Input(shape=(TIME_STEPS, len(features)), name='seq')
stk_input = Input(shape=(), dtype='int32', name='stk_idx')

x = LSTM(64, return_sequences=True, dropout=0.1, recurrent_dropout=0.1)(seq_input)
x = LayerNormalization()(x)
x = Dropout(0.2)(x)
x = LSTM(32, dropout=0.1, recurrent_dropout=0.1)(x)
x = LayerNormalization()(x)

emb = Embedding(input_dim=NUM_STOCKS, output_dim=EMB_DIM, name='stk_emb')(stk_input)
emb = tf.keras.layers.Flatten()(emb)
h = Concatenate()([x, emb])
h = Dense(64, activation='relu')(h)
h = Dropout(0.2)(h)

y_reg = Dense(1, name='y_reg')(h)
y_cls = Dense(1, activation='sigmoid', name='y_cls')(h)

model = Model(inputs=[seq_input, stk_input], outputs=[y_reg, y_cls])
model.compile(
    optimizer=Adam(learning_rate=LR_INIT),
    loss=[tf.keras.losses.Huber(delta=1.0), 'binary_crossentropy'],
    loss_weights=[1.0, ALPHA_CLS],
    metrics=[['mae'], ['accuracy', tf.keras.metrics.AUC(name='auc')]]
)

callbacks = [
    EarlyStopping(monitor='val_y_reg_mae', mode='min', patience=10, restore_best_weights=True),
    ReduceLROnPlateau(monitor='val_y_reg_mae', mode='min', patience=5, factor=0.5, verbose=1, min_lr=1e-5),
]

train_x = [X_train_seq, stk_train]
train_y = [y_train_seq, ycls_train]
train_sw = [np.ones_like(y_train_seq, dtype='float32'), wcls_train.astype('float32')]
val_x = [X_val_seq, stk_val]
val_y = [y_val_seq, ycls_val]
val_sw = [np.ones_like(y_val_seq, dtype='float32'), wcls_val.astype('float32')]

history = model.fit(
    train_x, train_y,
    validation_data=(val_x, val_y, val_sw),
    epochs=100,
    batch_size=64,
    callbacks=callbacks,
    sample_weight=train_sw,
    verbose=1
)

# ================================
# 9) Evaluation (inverse-transform)
# ================================
y_pred_scaled, y_pred_cls = model.predict([X_test_seq, stk_test], verbose=0)
y_pred_scaled = y_pred_scaled.ravel()
y_pred_cls    = y_pred_cls.ravel()

y_pred_excess_log = scaler_y.inverse_transform(y_pred_scaled.reshape(-1,1)).ravel()
y_true_excess_log = scaler_y.inverse_transform(y_test_seq.reshape(-1,1)).ravel()
y_pred_excess = np.exp(y_pred_excess_log) - 1
y_true_excess = np.exp(y_true_excess_log) - 1

mse = mean_squared_error(y_true_excess, y_pred_excess)
mae = mean_absolute_error(y_true_excess, y_pred_excess)
r2  = r2_score(y_true_excess, y_pred_excess)
direction_acc_from_reg = (np.sign(y_pred_excess) == np.sign(y_true_excess)).mean()

# ---- (Youden J) 임계값 최적화: Validation에서 best threshold 추정
def find_youden_threshold(y_true_bin, y_prob):
    # 클래스가 한쪽만 있으면 기본 0.5
    if len(np.unique(y_true_bin)) < 2:
        return 0.5, np.nan, np.nan
    fpr, tpr, thr = roc_curve(y_true_bin, y_prob)
    j = tpr - fpr
    idx = np.argmax(j)
    return float(thr[idx]), float(tpr[idx]), float(fpr[idx])

mask_val = wcls_val > 0
if mask_val.sum() > 0:
    y_true_val_bin = (ycls_val[mask_val] > 0.5).astype(int)
    y_prob_val = model.predict([X_val_seq[mask_val], stk_val[mask_val]], verbose=0)[1].ravel()
    best_thr, best_tpr, best_fpr = find_youden_threshold(y_true_val_bin, y_prob_val)
else:
    best_thr, best_tpr, best_fpr = 0.5, np.nan, np.nan

# (분류 헤드) 상/하위 30%만 평가
mask_cls = wcls_test > 0
if mask_cls.sum() > 0:
    y_true_cls = (ycls_test[mask_cls] > 0.5).astype(int)
    y_prob_cls = y_pred_cls[mask_cls]
    # 0.5 기준
    y_pred_cls_05 = (y_prob_cls >= 0.5).astype(int)
    acc_05 = accuracy_score(y_true_cls, y_pred_cls_05)
    auc_   = roc_auc_score(y_true_cls, y_prob_cls) if len(np.unique(y_true_cls))>1 else np.nan
    # 최적 임계값 기준
    y_pred_cls_opt = (y_prob_cls >= best_thr).astype(int)
    acc_opt = accuracy_score(y_true_cls, y_pred_cls_opt)
    prec_opt, rec_opt, f1_opt, _ = precision_recall_fscore_support(y_true_cls, y_pred_cls_opt, average='binary', zero_division=0)
else:
    acc_05 = auc_ = acc_opt = prec_opt = rec_opt = f1_opt = np.nan

print(f"Model (reg head) MSE: {mse:.6f}, MAE: {mae:.6f}, R2: {r2:.3f}, Direction Acc(reg): {direction_acc_from_reg:.3f}")
print(f"(Cls@0.5) Acc: {acc_05:.3f}, AUC: {auc_:.3f} | (Cls@Youden {best_thr:.3f}) Acc: {acc_opt:.3f}, P: {prec_opt:.3f}, R: {rec_opt:.3f}, F1: {f1_opt:.3f}")
scaled_mae = mean_absolute_error(y_test_seq, y_pred_scaled)
print(f"Scaled MAE: {scaled_mae:.4f}")

baseline_excess = np.exp(baseline_pred_excess_log) - 1
baseline_mae = mean_absolute_error(y_true_excess, baseline_excess)
baseline_rmse = np.sqrt(mean_squared_error(y_true_excess, baseline_excess))
print(f"Baseline MAE(%): {baseline_mae:.6f}, RMSE(%): {baseline_rmse:.6f}")

from scipy.stats import spearmanr, pearsonr
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    ic_overall_s, _ = spearmanr(y_true_excess, y_pred_excess, nan_policy='omit')
    ic_overall_p, _ = pearsonr(y_true_excess, y_pred_excess)
print(f"Spearman IC (overall): {ic_overall_s:.4f}, Pearson: {ic_overall_p:.4f}")

# ================================
# 10) Visualization
# ================================
plt.figure(figsize=(8,6))
plt.scatter(y_true_excess, y_pred_excess, alpha=0.4)
mn, mx = y_true_excess.min(), y_true_excess.max()
plt.plot([mn, mx], [mn, mx], 'r--')
plt.xlabel(f"Actual Excess {HORIZON}D Return")
plt.ylabel(f"Predicted Excess {HORIZON}D Return")
plt.title(f"Actual vs Predicted Excess {HORIZON}-Day Returns")
plt.grid(True)
plt.show()

errors = y_pred_excess - y_true_excess
plt.figure(figsize=(8,4))
plt.hist(errors, bins=50)
plt.title("Prediction Error Distribution (Excess Return)")
plt.xlabel("Error"); plt.ylabel("Count")
plt.grid(True); plt.show()

plt.figure(figsize=(8,4))
plt.plot(history.history['y_reg_mae'], label='train y_reg_mae')
plt.plot(history.history['val_y_reg_mae'], label='val y_reg_mae')
plt.xlabel("Epoch"); plt.ylabel("MAE (scaled)")
plt.title("Training History (Monitor = val_y_reg_mae)")
plt.legend(); plt.grid(True); plt.show()

# ================================
# 11) Detailed report
# ================================
def evaluation_report(
    y_true_excess_log, y_pred_excess_log, y_pred_scaled, y_test_scaled,
    baseline_pred_excess_log, baseline_pred_scaled,
    history, model, horizon, cls_metrics
):
    from scipy.stats import spearmanr, pearsonr
    import warnings
    y_true = np.exp(y_true_excess_log) - 1
    y_pred = np.exp(y_pred_excess_log) - 1
    baseline = np.exp(baseline_pred_excess_log) - 1
    mae_val = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mask = np.abs(y_true) > 1e-6
    mape_str = f"{(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100):.2f}%" if mask.sum() > 0 else "N/A"
    r2_val = r2_score(y_true, y_pred)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        corr_p, _ = pearsonr(y_true, y_pred)
        corr_s, _ = spearmanr(y_true, y_pred)
    print("="*60)
    print(f"📊 종합 성능 평가 (Excess {horizon}-Day Return)")
    print("="*60)
    print(f"✅ MAE (%):                {mae_val:.6f}")
    print(f"✅ RMSE (%):               {rmse:.6f}")
    print(f"✅ MAPE (%):               {mape_str}")
    print(f"✅ R² Score:               {r2_val:.4f}")
    print(f"✅ Pearson IC:             {corr_p:.4f}")
    print(f"✅ Spearman IC:            {corr_s:.4f}")
    print(f"✅ Cls@0.5 Acc/AUC:        {cls_metrics['acc_05']:.4f} / {cls_metrics['auc']:.4f}")
    print(f"✅ Cls@Youden(th={cls_metrics['thr']:.3f}) Acc/P/R/F1: {cls_metrics['acc_opt']:.4f}/{cls_metrics['prec_opt']:.4f}/{cls_metrics['rec_opt']:.4f}/{cls_metrics['f1_opt']:.4f}")
    print(f"✅ Scaled MAE:             {mean_absolute_error(y_test_scaled, y_pred_scaled):.4f}")
    print("-"*60)
    print(f"🔁 Baseline MAE (%):       {mean_absolute_error(y_true, baseline):.6f}")
    print(f"🔁 Baseline RMSE (%):      {np.sqrt(mean_squared_error(y_true, baseline)):.6f}")
    print(f"🔁 Baseline MAE (scaled):  {mean_absolute_error(y_test_scaled, baseline_pred_scaled):.4f}")
    print("-"*60)
    print(f"📉 최종 학습 epoch 수:      {len(history.history['loss'])}")
    print(f"📈 최종 Validation y_reg_mae: {history.history['val_y_reg_mae'][-1]:.4f}")
    try:
        current_lr = float(tf.keras.backend.get_value(model.optimizer.learning_rate))
    except Exception:
        current_lr = None
    print(f"🧪 최종 학습률(LR):         {current_lr if current_lr is not None else 'N/A'}")
    print("="*60)

cls_metrics = {
    'acc_05': float(acc_05) if not np.isnan(acc_05) else np.nan,
    'auc': float(auc_) if not np.isnan(auc_) else np.nan,
    'thr': float(best_thr),
    'acc_opt': float(acc_opt) if not np.isnan(acc_opt) else np.nan,
    'prec_opt': float(prec_opt) if not np.isnan(prec_opt) else np.nan,
    'rec_opt': float(rec_opt) if not np.isnan(rec_opt) else np.nan,
    'f1_opt': float(f1_opt) if not np.isnan(f1_opt) else np.nan,
}

evaluation_report(
    y_true_excess_log, y_pred_excess_log,
    y_pred_scaled, y_test_seq,
    baseline_pred_excess_log, baseline_pred_scaled,
    history, model, HORIZON, cls_metrics
)

# ==========================================================
# 12) Evaluation DF (for cross-sectional tests)
# ==========================================================
eval_df = pd.DataFrame({
    'date': pd.to_datetime([m['base_date'] for m in meta_test]),
    'stk_cd': [m['stk_cd'] for m in meta_test],
    'pred_excess': y_pred_excess,
    'true_excess': y_true_excess,
    'pred_excess_log': y_pred_excess_log,
    'true_excess_log': y_true_excess_log,
    'pred_cls_prob': y_pred_cls,
})

mkt_map = (test_df[['date','mkt_target_log']]
           .drop_duplicates()
           .set_index('date')['mkt_target_log'])
eval_df['mkt_log'] = eval_df['date'].map(mkt_map)
eval_df['true_raw_log'] = eval_df['true_excess_log'] + eval_df['mkt_log']
eval_df['true_raw']     = np.exp(eval_df['true_raw_log']) - 1
eval_df['pred_raw_log'] = eval_df['pred_excess_log'] + eval_df['mkt_log']
eval_df['pred_raw']     = np.exp(eval_df['pred_raw_log']) - 1

# ================================
# 13) Cross-sectional IC by date — 방어 로직 포함
# ================================
from scipy.stats import spearmanr

def daily_ic(df_in: pd.DataFrame, col_pred: str, col_true: str, min_n: int = 3):
    ics = []
    for d, g in df_in.groupby('date'):
        g = g[[col_pred, col_true]].dropna()
        if len(g) >= min_n:
            ic, _ = spearmanr(g[col_pred], g[col_true])
            if not np.isnan(ic):
                ics.append({'date': d, 'ic': ic})
    if len(ics) == 0:
        return pd.DataFrame(columns=['date','ic'])
    ic_df = pd.DataFrame(ics).sort_values('date').reset_index(drop=True)
    return ic_df

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

ic_daily = daily_ic(eval_df, 'pred_excess', 'true_excess', min_n=3)
print("\n[Daily Spearman IC] head")
print(ic_daily.head().to_string(index=False))
if not ic_daily.empty:
    print(f"Overall mean IC: {ic_daily['ic'].mean():.4f}, std: {ic_daily['ic'].std():.4f}, n_days: {len(ic_daily)}")
else:
    print("IC 계산에 충분한 종목 수/유효 값이 없어 비어 있습니다.")

ic_month = agg_ic_stats(ic_daily, freq='M')
ic_quart = agg_ic_stats(ic_daily, freq='Q')
print("\n[Monthly IC stats] (mean, std, n, t)")
print(ic_month.to_string(index=False))
print("\n[Quarterly IC stats] (mean, std, n, t)")
print(ic_quart.to_string(index=False))

plt.figure(figsize=(9,3))
if not ic_daily.empty:
    plt.plot(ic_daily['date'], ic_daily['ic'])
plt.axhline(0, linestyle='--', color='r')
plt.title('Daily Spearman IC (Excess Return)')
plt.xlabel('Date'); plt.ylabel('IC')
plt.grid(True); plt.show()

# ================================
# 14) Long-Short Spread (Top-vs-Bottom)
# ================================
def select_non_overlap_dates(dates: pd.Series, step: int) -> np.ndarray:
    uniq = np.array(sorted(pd.to_datetime(dates.unique())))
    return uniq[::step]

def daily_long_short_spread(df_in: pd.DataFrame, pred_col='pred_excess', true_col='true_excess',
                            top_frac=0.2, equal_weight=True, use_non_overlap=False, horizon=5):
    res = []
    df_local = df_in.copy()
    if use_non_overlap:
        allowed = set(select_non_overlap_dates(df_local['date'], horizon))
        df_local = df_local[df_local['date'].isin(allowed)].copy()
    for d, g in df_local.groupby('date'):
        g = g[['stk_cd', pred_col, true_col]].dropna()
        n = len(g)
        if n < 10:  # 최소 표본 제한
            continue
        k = max(1, int(n * top_frac))
        g = g.sort_values(pred_col)
        bottom = g.iloc[:k]; top = g.iloc[-k:]
        r_top = top[true_col].mean(); r_bot = bottom[true_col].mean()
        spread = r_top - r_bot
        hit_rate = (top[true_col] > 0).mean()
        res.append({'date': d, 'n': n, 'k': k, 'spread': spread, 'top_hit': hit_rate,
                    'r_top': r_top, 'r_bot': r_bot})
    if len(res) == 0:
        return pd.DataFrame(columns=['date','n','k','spread','top_hit','r_top','r_bot'])
    out = pd.DataFrame(res).sort_values('date').reset_index(drop=True)
    return out

def cum_return(series: pd.Series) -> pd.Series:
    return (1.0 + series.fillna(0)).cumprod() - 1.0

ls_all   = daily_long_short_spread(eval_df, 'pred_excess', 'true_excess',
                                   top_frac=0.2, equal_weight=True, use_non_overlap=False, horizon=HORIZON)
ls_purge = daily_long_short_spread(eval_df, 'pred_excess', 'true_excess',
                                   top_frac=0.2, equal_weight=True, use_non_overlap=True, horizon=HORIZON)

print("\n[Long-Short Spread] (Overlapped)")
print(ls_all.head().to_string(index=False))
if not ls_all.empty:
    print(f"Mean spread: {ls_all['spread'].mean():.6f}, Std: {ls_all['spread'].std():.6f}, n_days: {len(ls_all)}")
    print(f"Top-bucket mean hit-rate: {ls_all['top_hit'].mean():.3f}")
else:
    print("표본 부족으로 스프레드를 계산하지 못했습니다.")

print("\n[Long-Short Spread] (Non-overlap, purged)")
print(ls_purge.head().to_string(index=False))
if not ls_purge.empty:
    print(f"Mean spread: {ls_purge['spread'].mean():.6f}, Std: {ls_purge['spread'].std():.6f}, n_days: {len(ls_purge)}")
    print(f"Top-bucket mean hit-rate: {ls_purge['top_hit'].mean():.3f}")
else:
    print("표본 부족으로 비겹침 스프레드를 계산하지 못했습니다.")

if not ls_all.empty:
    plt.figure(figsize=(9,3))
    plt.plot(ls_all['date'], cum_return(ls_all['spread']), label='Overlapped')
    if not ls_purge.empty:
        plt.plot(ls_purge['date'], cum_return(ls_purge['spread']), label='Non-overlap')
    plt.axhline(0, linestyle='--', color='r')
    plt.title(f'Long-Short Cumulative Return (Excess, Top 20% vs Bottom 20%)')
    plt.legend(); plt.grid(True); plt.show()

# ================================
# 15) Bucketed portfolio (Q1~Q5)
# ================================
def bucket_returns(df_in: pd.DataFrame, pred_col='pred_excess', true_col='true_excess', q=5):
    rows = []
    for d, g in df_in.groupby('date'):
        g = g[['stk_cd', pred_col, true_col]].dropna()
        if len(g) < q:
            continue
        try:
            g = g.copy()
            g['bucket'] = pd.qcut(g[pred_col].rank(method='first'), q, labels=False, duplicates='drop') + 1
        except ValueError:
            continue
        by = g.groupby('bucket')[true_col].mean()
        rec = {'date': d}
        for i in range(1, int(by.index.max())+1):
            rec[f'Q{i}'] = by.get(i, np.nan)
        rows.append(rec)
    if len(rows) == 0:
        return pd.DataFrame()
    br = pd.DataFrame(rows).sort_values('date').reset_index(drop=True)
    return br

br = bucket_returns(eval_df, 'pred_excess', 'true_excess', q=5)
if not br.empty:
    cols = [c for c in br.columns if c.startswith('Q')]
    br_mean = br[cols].mean()
    print("\n[Bucket mean returns by predicted score]")
    print(br_mean.to_string())
    if 'Q1' in br_mean and 'Q5' in br_mean:
        print(f"Q5 - Q1 spread (mean): {br_mean['Q5'] - br_mean['Q1']:.6f}")
else:
    print("\n[Bucket mean returns] 표본 부족으로 계산 불가")
    
# ================================
# 16) Latest Inference
# ================================
def predict_latest_for_each_stock(model, scaler_x, scaler_y, full_df, features, time_steps=15, horizon=5):
    results = []
    for stk, g in full_df.groupby('stk_cd'):
        g_sorted = g.sort_values('date')
        if len(g_sorted) < time_steps:
            continue
        window_feat = scaler_x.transform(g_sorted[features].astype(float).values)[-time_steps:]
        last_close = float(g_sorted.iloc[-1]['close_pric'])
        last_date = g_sorted.iloc[-1]['date']
        stk_idx = int(g_sorted.iloc[-1]['stk_idx'])
        pred_scaled, pred_cls = model.predict(
            [window_feat.reshape(1, time_steps, len(features)), np.array([stk_idx])],
            verbose=0
        )
        pred_excess_log = float(scaler_y.inverse_transform(pred_scaled)[0, 0])
        pred_excess = np.exp(pred_excess_log) - 1
        pred_future_close = last_close * (1.0 + pred_excess)
        results.append({
            'stk_cd': stk,
            'last_date': last_date,
            'last_close': last_close,
            f'pred_excess_return_{horizon}d': float(pred_excess),
            f'pred_price_in_{horizon}d_excess_only': float(pred_future_close),
            'direction_prob': float(pred_cls.ravel()[0])
        })
    return pd.DataFrame(results)

latest_pred_df = predict_latest_for_each_stock(model, scaler_x, scaler_y, df, features, TIME_STEPS, HORIZON)
print("\n[종목별 최신 예측 결과] (초과수익률 기반 5일 뒤)")
print(latest_pred_df.sort_values('stk_cd').to_string(index=False))
