import requests
import json
import pandas as pd
import psycopg2
import main
import time
from requests.exceptions import RequestException
from datetime import datetime

# DB 연결
def DBconnect():
    global cur, conn
    try:
        conn = psycopg2.connect(
            host='localhost',
            user='postgres',
            password='5692',
            dbname='kiwoom_data'
        )
        cur = conn.cursor()
        print("Database Connect Success")
        return cur, conn
    except Exception as err:
        print(f"데이터베이스 연결 실패: {str(err)}")
        return None, None

# DB 닫기
def DBdisconnect():
    try:
        conn.close()
        cur.close()
        print("DB Connect Close")
    except:
        print("Error: Database Not Connected.")

####### 프로그램 순매수 상위 50 요청 및 데이터베이스 저장 #############
def fn_ka90003(token, data, max_retries=3, max_items=50):
    host = 'https://mockapi.kiwoom.com'
    endpoint = '/api/dostk/stkinfo'
    url = host + endpoint

    all_data = []
    cont_yn = 'N'
    next_key = ''
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': 'ka90003',
    }

    while len(all_data) < max_items:
        headers['cont-yn'] = cont_yn
        headers['next-key'] = next_key

        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=data)
                print('응답 코드:', response.status_code)
                print('응답 헤더:', json.dumps({
                    'next-key': response.headers.get('next-key', ''),
                    'cont-yn': response.headers.get('cont-yn', ''),
                    'api-id': response.headers.get('api-id', '')
                }, indent=4, ensure_ascii=False))

                if response.status_code == 429:
                    print(f"429 Too Many Requests 에러 발생. {attempt + 1}/{max_retries} 재시도 중...")
                    time.sleep(2 ** attempt)
                    continue

                if response.status_code == 200:
                    response_data = response.json()
                    prm_list = response_data.get('prm_netprps_upper_50', [])
                    print(f"API 응답 데이터 개수: {len(prm_list)}")

                    if not prm_list:
                        print("더 이상 데이터가 없습니다.")
                        break

                    all_data.extend(prm_list)
                    print(f"현재까지 수집된 데이터 개수: {len(all_data)}")

                    cont_yn = response.headers.get('cont-yn', 'N')
                    next_key = response.headers.get('next-key', '')
                    if cont_yn != 'Y' or not next_key:
                        print("연속 조회 종료")
                        break

                    break

                else:
                    print(f"API 요청 실패: 상태 코드 {response.status_code}")
                    return None, None, None

            except RequestException as e:
                print(f"요청 중 오류 발생: {str(e)}. {attempt + 1}/{max_retries} 재시도 중...")
                time.sleep(2 ** attempt)
                continue

        else:
            print("최대 재시도 횟수 초과. API 요청 실패")
            return None, None, None

        if cont_yn != 'Y':
            break

    all_data = all_data[:max_items]
    print(f"최종 수집된 데이터 개수: {len(all_data)}")

    if not all_data:
        print("데이터가 없습니다.")
        return None, None, None

    df = pd.DataFrame(all_data)
    print("원본 데이터프레임:\n", df)

    required_columns = ['rank', 'stk_cd', 'stk_nm', 'cur_prc', 'acc_trde_qty']
    df = df[required_columns]

    df['rank'] = df['rank'].astype(int)
    string_columns = ['stk_cd', 'stk_nm', 'cur_prc', 'acc_trde_qty']
    for col in string_columns:
        df[col] = df[col].astype(str).replace('', None)

    print(f"중복 제거 전 행 수: {len(df)}")
    df = df.drop_duplicates(subset=['stk_cd'], keep='first')
    print(f"중복 제거 후 행 수: {len(df)}")

    df = df.sort_values(by='rank', ascending=True).reset_index(drop=True)
    print("rank 오름차순 정렬 및 중복 제거된 데이터프레임:\n", df)

    df['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print("최종 데이터프레임:\n", df)
    return df, cont_yn, next_key

# 데이터베이스에 데이터 삽입
def insert_to_db(df, batch_size=1000):
    try:
        cur, conn = DBconnect()
        if cur is None or conn is None:
            raise Exception("DB 연결 실패")

        # 테이블 생성 (기본 키를 stk_cd로 설정)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.buyTop50_data (
                rank INTEGER,
                stk_cd VARCHAR(20),
                stk_nm VARCHAR(20),
                cur_prc VARCHAR(20),
                acc_trde_qty VARCHAR(20),
                created_at TIMESTAMP,
                CONSTRAINT buyTop50_data_pkey PRIMARY KEY (stk_cd)
            );
        """)
        conn.commit()
        print("buyTop50_data 테이블 확인/생성 완료!")

        # 삽입 전 중복 체크 (stk_cd 기준)
        existing_stk_cds = set()
        cur.execute("SELECT stk_cd FROM public.buyTop50_data")
        for row in cur.fetchall():
            existing_stk_cds.add(row[0])

        # 삽입할 데이터 중 이미 존재하는 stk_cd 제외
        df_to_insert = df[~df['stk_cd'].isin(existing_stk_cds)]
        if df_to_insert.empty:
            print("삽입할 새로운 종목 코드가 없습니다. 삽입을 건너뜁니다.")
            return

        print(f"삽입할 데이터 개수: {len(df_to_insert)}")

        # 배치 삽입
        for start in range(0, len(df_to_insert), batch_size):
            batch = df_to_insert[start:start + batch_size]
            print(f"배치 삽입 시작: {start} ~ {start + len(batch) - 1} 행")

            for index, row in batch.iterrows():
                insert_query = """
                INSERT INTO public.buyTop50_data (rank, stk_cd, stk_nm, cur_prc, acc_trde_qty, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (stk_cd) DO NOTHING;
                """
                cur.execute(insert_query, (
                    row['rank'],    # 순위
                    row['stk_cd'],   # 종목코드
                    row['stk_nm'],   # 종목명
                    row['cur_prc'],   # 현재가
                    row['acc_trde_qty'],   # 누적거래량
                    row['created_at']   # DB에 저장되기 전 시각(데이터를 받은 시각)
                ))

            conn.commit()
            print(f"배치 삽입 완료: {len(batch)} rows")

        print("모든 데이터 삽입 완료")

    except Exception as err:
        print(f"데이터 삽입 중 오류: {str(err)}")
        if conn is not None:
            conn.rollback()

    finally:
        DBdisconnect()

# 실행 구간
if __name__ == '__main__':
    MY_ACCESS_TOKEN = main.fn_au10001()
    params = {
        'trde_upper_tp': '2',
        'amt_qty_tp': '1',
        'mrkt_tp': 'P00101',
        'stex_tp': '1',
    }
    df, cont_yn, next_key = fn_ka90003(
        token=MY_ACCESS_TOKEN,
        data=params,
        max_retries=3,
        max_items=50
    )
    if df is not None:
        print(f"총 {len(df)} rows 데이터를 삽입합니다.")
        insert_to_db(df, batch_size=1000)
    else:
        print("데이터를 가져오지 못했습니다.")