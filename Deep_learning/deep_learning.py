import pandas as pd
import glob

# --- 1. LSTM 예측 결과 파일 통합 ---
lstm_files_path = 'lstm_predictions/lstm_preds_fold_*.csv'
lstm_files = sorted(glob.glob(lstm_files_path))

if not lstm_files:
    print(f"Error: No files found matching the pattern: {lstm_files_path}")
    lstm_combined_df = pd.DataFrame()
else:
    all_lstm_dfs = [pd.read_csv(f) for f in lstm_files]
    lstm_combined_df = pd.concat(all_lstm_dfs, ignore_index=True)

print("--- Combined LSTM Predictions ---")
print(f"Loaded {len(lstm_files)} LSTM prediction files.")
print(lstm_combined_df.head())
print("\n")


# --- 2. 뉴스 감성 분석 파일 불러오기 ---
sentiment_file_path = 'finbert_predictions/News_DB_sentiment_results.csv'
try:
    sentiment_df = pd.read_csv(sentiment_file_path)
except FileNotFoundError:
    print(f"Error: File not found at '{sentiment_file_path}'")
    sentiment_df = pd.DataFrame()

print("--- News Sentiment Data ---")
print(sentiment_df.head())
print("\n")


# 데이터 로딩 실패 시 프로그램 중단
if lstm_combined_df.empty or sentiment_df.empty:
    print("One or both dataframes could not be loaded. Exiting.")
else:
    # --- 3. 데이터 전처리 및 병합 준비 ---
    try:
        # 각 파일에 맞는 날짜 컬럼 이름을 'Date'로 통일
        lstm_combined_df.rename(columns={'date': 'Date'}, inplace=True)
        sentiment_df.rename(columns={'created_at': 'Date'}, inplace=True) # 'created_at'을 'Date'로 변경

        # 'Date' 컬럼을 datetime 형식으로 변환
        lstm_combined_df['Date'] = pd.to_datetime(lstm_combined_df['Date'])
        sentiment_df['Date'] = pd.to_datetime(sentiment_df['Date'])

        # 뉴스 데이터의 시간 정보를 제거하고 날짜만 남김 (중요)
        sentiment_df['Date'] = sentiment_df['Date'].dt.normalize()

        # 감성 레이블(문자열)을 숫자(1, 0, -1)로 변환
        label_map = {'positive': 1, 'neutral': 0, 'negative': -1}
        sentiment_df['sentiment_score'] = sentiment_df['final_label'].map(label_map)

        # 날짜별로 데이터 집계 (평균 계산)
        lstm_agg_df = lstm_combined_df.groupby('Date').mean(numeric_only=True).reset_index()
        sentiment_agg_df = sentiment_df.groupby('Date')['sentiment_score'].mean().reset_index()

        # --- 4. 최종 데이터 병합 ---
        final_df = pd.merge(lstm_agg_df, sentiment_agg_df, on='Date', how='inner')
        final_df = final_df.sort_values(by='Date').reset_index(drop=True)

        # 결과를 새 CSV 파일로 저장
        final_df.to_csv('final_combined_data.csv', index=False, encoding='utf-8-sig')

        print("--- Final Merged Data ---")
        print(final_df.head())
        print(f"\nSuccessfully merged the data and saved to 'final_combined_data.csv'")

    except Exception as e:
        print(f"An error occurred during data processing: {e}")