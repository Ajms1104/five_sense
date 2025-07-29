import os
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from sqlalchemy import create_engine

# 환경변수 로드
load_dotenv()
engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME2')}"
)

def convert_unit(value, unit):
    try:
        value = float(value)
    except:
        return np.nan
    mapping = {'백만원':1_000_000, '천원':1_000, '억원':100_000_000}
    return value * mapping.get(unit, 1)

# 1) 원본 테이블 로드
assets   = pd.read_sql("SELECT * FROM assets", engine)
revenues = pd.read_sql("SELECT * FROM revenues", engine)
labels   = pd.read_sql("SELECT * FROM labels", engine)

# 2) 병합 & 전처리 (setup() 내부와 동일)
assets['context_dt']   = pd.to_datetime(assets['context'], format='%Y.%m', errors='coerce')
revenues['context_dt'] = pd.to_datetime(revenues['context'], format='%Y.%m', errors='coerce')
assets_recent   = assets.sort_values('context_dt').drop_duplicates('rcept_no', keep='last')
revenues_recent = revenues.sort_values('context_dt').drop_duplicates('rcept_no', keep='last')

merged = (
    labels
    .merge(assets_recent.drop(columns=['context_dt']),   on='rcept_no', how='inner')
    .merge(revenues_recent.drop(columns=['context_dt']), on='rcept_no', how='left', suffixes=('','_revenue'))
)
merged['asset_value']   = merged.apply(lambda r: convert_unit(r['value'],         r['unit']), axis=1)
merged['revenue_value'] = merged.apply(lambda r: convert_unit(r['value_revenue'], r['unit_revenue']), axis=1)
merged = merged.fillna({'asset_value':0, 'revenue_value':0})
merged['date']           = pd.to_datetime(merged['context'], format='%Y.%m', errors='coerce')
merged = merged.sort_values(['rcept_no','date'])
merged['future_revenue'] = merged.groupby('rcept_no')['revenue_value'].shift(-1)
merged = merged.dropna(subset=['future_revenue'])
merged['target']         = (merged['future_revenue'] > merged['revenue_value']).astype(int)
merged['time_idx']       = merged.groupby('rcept_no').cumcount()

# ★ 여기서부터 출력 ★

# 1) 컬럼, 데이터 타입, 널카운트 확인
print("=== merged.info() ===")
merged.info()

# 2) 샘플 데이터 (첫 10행)
print("\n=== merged.head(10) ===")
print(merged.head(10))

# 3) 수치형 컬럼 기본 통계
print("\n=== merged[['asset_value','revenue_value','future_revenue']].describe() ===")
print(merged[['asset_value','revenue_value','future_revenue']].describe())

# 4) 타깃 분포
print("\n=== Target value counts ===")
print(merged['target'].value_counts(dropna=False))

# 5) 그룹별 시계열 길이 확인 (상위 10개)
print("\n=== time_idx per group (first 10 groups) ===")
print(
    merged
    .groupby('rcept_no')['time_idx']
    .agg(['min','max','count'])
    .head(10)
)

# (필요 시) df(최종 입력용)으로도 동일하게 찍어보세요:
# df = merged[['rcept_no','time_idx','asset_value','revenue_value','target']].rename(columns={'rcept_no':'group_id'})
# df.info(); print(df.head(10)); print(df['target'].value_counts())
