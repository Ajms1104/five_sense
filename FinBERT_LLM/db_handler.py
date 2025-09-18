import psycopg2
from psycopg2 import extras
import pandas as pd
from config import DB_CONFIG


def fetch_news_data(limit=None):
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        query = "SELECT * FROM company_news WHERE label IS NULL"  # 라벨링 안된 것만 가져오기
        if limit:
            query += f" LIMIT {limit}"
        query += ";"

        df = pd.read_sql(query, conn)
        print(f"데이터베이스에서 라벨링이 필요한 뉴스 {df.shape[0]}개를 불러왔습니다.")
        return df
    except Exception as e:
        print(f"데이터베이스 조회 중 에러 발생: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def update_labels_to_db(df):
    if df.empty or 'final_label' not in df.columns or 'id' not in df.columns:
        print("업데이트할 데이터가 없거나 필요한 컬럼('final_label', 'id')이 없습니다.")
        return

    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        try:
            cur.execute("ALTER TABLE company_news ADD COLUMN label VARCHAR(10);")
            conn.commit()
            print("'label' 컬럼을 테이블에 추가했습니다.")
        except psycopg2.errors.DuplicateColumn:
            conn.rollback()

        update_data = [(row['final_label'], row['id']) for _, row in df.iterrows()]
        update_query = "UPDATE company_news SET label = %s WHERE id = %s;"

        extras.execute_batch(cur, update_query, update_data)
        conn.commit()
        print(f"총 {len(update_data)}개의 뉴스에 대한 감성 라벨 업데이트를 완료했습니다.")

    except Exception as e:
        print(f"데이터베이스 업데이트 중 에러 발생: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()