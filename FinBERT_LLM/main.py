import pandas as pd
from config import OUTPUT_CSV_NAME
import db_handler
import finbert_analyzer
import gemini_analyzer

def main():
    """메인 실행 함수"""
    # 1. DB에서 분석할 데이터 불러오기
    df = db_handler.fetch_news_data(limit=100) # 테스트 시
    #df = db_handler.fetch_news_data()  # 전체 데이터 분석 시
    if df.empty:
        print("분석할 새로운 뉴스가 없습니다.")
        return

    # 2. FinBERT로 뉴스 제목 분석
    titles = df['title'].tolist()
    df['predicted_label'] = finbert_analyzer.analyze_titles(titles)

    # 3. Gemini로 뉴스 본문 분석
    descriptions = df["description"].dropna().tolist()
    gemini_labels = gemini_analyzer.analyze_descriptions(descriptions)
    df['gemini_label'] = gemini_labels

    # 4. 최종 라벨 결정
    print("제목과 본문 분석 결과를 종합하여 최종 라벨을 결정합니다...")
    df['final_label'] = df['predicted_label']
    mismatched_mask = (df['predicted_label'] != df['gemini_label']) & (df['gemini_label'] != 'unknown')
    df.loc[mismatched_mask, 'final_label'] = 'neutral'

    print("최종 라벨 분포:")
    print(df['final_label'].value_counts())

    # 5. 결과 저장
    df.to_csv(OUTPUT_CSV_NAME, index=False, encoding='utf-8-sig')
    print(f"분석 결과가 '{OUTPUT_CSV_NAME}' 파일로 저장되었습니다.")

    db_handler.update_labels_to_db(df)

if __name__ == "__main__":
    main()