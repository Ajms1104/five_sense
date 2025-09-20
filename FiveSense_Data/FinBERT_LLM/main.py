import pandas as pd
from config import OUTPUT_CSV_NAME, FINBERT_SCORE_WEIGHT, GEMINI_SCORE_WEIGHT
import db_handler
import finbert_analyzer
import gemini_analyzer


def score_to_label(score, threshold=0.1):
    """감성 점수를 기준으로 라벨을 부여합니다."""
    if score is None or pd.isna(score):
        return 'unknown'
    if score > threshold:
        return 'positive'
    elif score < -threshold:
        return 'negative'
    else:
        return 'neutral'


def main():
    """메인 실행 함수"""
    # 0. 데이터베이스 테이블 준비
    db_handler.prepare_database()

    # 1. DB에서 분석할 데이터 불러오기
    #df = db_handler.fetch_news_data(limit=100) # 테스트용
    df = db_handler.fetch_news_data()

    if df.empty:
        print("분석할 새로운 뉴스가 없습니다.")
        return
    print(f"--- 1. DB에서 {len(df)}개 데이터 로드 완료 ---")

    # --- 2. ID를 Key로 사용하여 분석 및 결과 매핑 (데이터 어긋남 방지) ---
    # 분석에 사용할 ID와 텍스트를 추출
    ids = df['id'].tolist()
    titles = df['title'].tolist()
    descriptions = df["description"].fillna('').tolist()

    # 각 분석기는 텍스트 리스트를 입력받아 점수 리스트를 반환
    print("\n>>> FinBERT 분석 시작...")
    finbert_scores = finbert_analyzer.analyze_titles(titles)

    print("\n>>> Gemini 분석 시작...")
    gemini_scores = gemini_analyzer.analyze_descriptions(descriptions)

    # 결과를 'id: score' 형태의 딕셔너리로 변환
    id_to_finbert_score = dict(zip(ids, finbert_scores))
    id_to_gemini_score = dict(zip(ids, gemini_scores))

    # map 함수를 사용하여 id를 기준으로 점수를 정확하게 매핑
    df['finbert_score'] = df['id'].map(id_to_finbert_score)
    df['gemini_score'] = df['id'].map(id_to_gemini_score)
    print("\n--- 2. ID 기준 분석 결과 매핑 완료 ---")

    # 3. 최종 점수 및 라벨 결정
    print("\n최종 감성 점수와 라벨을 결정합니다...")

    # NaN 값이 있는 행은 점수 계산에서 제외되도록 안전하게 처리
    df['final_score'] = (df['finbert_score'].fillna(0) * FINBERT_SCORE_WEIGHT) + \
                        (df['gemini_score'].fillna(0) * GEMINI_SCORE_WEIGHT)
    df['final_score'] = df['final_score'].clip(-1.0, 1.0)

    df['final_label'] = df['final_score'].apply(score_to_label)

    print("\n최종 분석 결과 요약 (상위 5개):")
    print(df[['id', 'title', 'finbert_score', 'gemini_score', 'final_score', 'final_label']].head())
    print("\n최종 라벨 분포:")
    print(df['final_label'].value_counts())

    # 4. 결과 저장
    df.to_csv(OUTPUT_CSV_NAME, index=False, encoding='utf-8-sig')
    print(f"\n분석 결과가 '{OUTPUT_CSV_NAME}' 파일로 저장되었습니다.")

    db_handler.update_results_to_db(df)


if __name__ == "__main__":
    main()