import psycopg2
from psycopg2 import extras
import pandas as pd
from config import DB_CONFIG


def prepare_database():
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("ALTER TABLE company_news ADD COLUMN IF NOT EXISTS label VARCHAR(10);")
        cur.execute("ALTER TABLE company_news ADD COLUMN IF NOT EXISTS score FLOAT;")
        conn.commit()
        print("데이터베이스 테이블 준비 완료. 'label'과 'score' 컬럼이 존재합니다.")
    except Exception as e:
        print(f"데이터베이스 준비 중 에러 발생: {e}")
        raise  # 에러 발생 시 프로그램 중단
    finally:
        if cur: cur.close()
        if conn: conn.close()


def fetch_news_data(limit=None):
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        query = "SELECT * FROM company_news WHERE label IS NULL OR score IS NULL ORDER BY id"
        if limit:
            query += f" LIMIT {limit}"
        query += ";"
        df = pd.read_sql(query, conn)
        print(f"데이터베이스에서 분석이 필요한 뉴스 {df.shape[0]}개를 ID 순서로 불러왔습니다.")
        return df
    except psycopg2.Error as e:
        print(f"데이터베이스 조회 중 에러 발생: {e}")
        return pd.DataFrame()
    finally:
        if conn: conn.close()


def update_results_to_db(df):
    if df.empty or 'final_label' not in df.columns or 'final_score' not in df.columns or 'id' not in df.columns:
        print("업데이트할 데이터가 없거나 필요한 컬럼이 없습니다.")
        return

    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # DataFrame에서 NaN 값을 None으로 변환
        df_to_update = df[['id', 'final_label', 'final_score']].copy()
        df_to_update = df_to_update.where(pd.notnull(df_to_update), None)

        update_data = [(row['final_label'], row['final_score'], row['id']) for _, row in df_to_update.iterrows()]
        update_query = "UPDATE company_news SET label = %s, score = %s WHERE id = %s;"

        print(f"DB에 {len(update_data)}개 레코드 업데이트를 시도합니다...")
        extras.execute_batch(cur, update_query, update_data)

        conn.commit()
        print(f"총 {cur.rowcount}개의 뉴스에 대한 업데이트를 완료했습니다.")

    except Exception as e:
        print(f"!!!!!!!! 데이터베이스 업데이트 중 심각한 에러 발생 !!!!!!!!")
        print(f"에러 내용: {e}")
        if conn:
            print("변경사항을 모두 되돌립니다 (롤백).")
            conn.rollback()
    finally:
        if cur: cur.close()
        if conn: conn.close()