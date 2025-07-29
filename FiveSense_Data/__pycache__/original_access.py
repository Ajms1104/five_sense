import requests
import json
import pandas as pd
import psycopg2
import main
import time
from requests.exceptions import RequestException

##### 주식기본정보요청 #######

def fn_ka10001(token, data, cont_yn='N', next_key='', max_retries=3):
    # 1. 요청할 API URL
    host = 'https://mockapi.kiwoom.com'  # 모의투자
    # host = 'https://api.kiwoom.com'  # 실전투자
    endpoint = '/api/dostk/stkinfo'
    url = host + endpoint

    # 2. header 데이터
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',  # 컨텐츠타입
        'authorization': f'Bearer {token}',  # 접근토큰
        'cont-yn': cont_yn,  # 연속조회여부
        'next-key': next_key,  # 연속조회키
        'api-id': 'ka10001',  # TR명
    }

    # 3. http POST 요청
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data)
            print('Code:', response.status_code)
            print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
            print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))

            if response.status_code == 429:
                print(f"429 Too Many Requests 에러 발생. {attempt + 1}/{max_retries} 재시도 중...")
                time.sleep(2 ** attempt)  # 지수 백오프
                continue

            if response.status_code == 200:
                res = response.json()
                # 응답이 리스트인지 단일 객체인지 확인
                if isinstance(res, list):
                    df = pd.DataFrame(res)
                else:
                    df = pd.DataFrame([res])

                # 필요한 컬럼만 선택
                required_columns = ['stk_cd', 'stk_nm', 'oyr_hgst', 'oyr_lwst', 'lst_pric', 'base_pric', 'cur_prc', 'trde_qty']
                available_columns = [col for col in required_columns if col in df.columns]
                df = df[available_columns]

                if df.empty:
                    print("응답 데이터가 비어있습니다.")
                    return None, None, None

                print("전처리된 데이터프레임:\n", df)
                time.sleep(1)  # 요청 간 딜레이
                return df, response.headers.get('cont-yn'), response.headers.get('next-key')
            else:
                print(f"API 요청 실패: {response.status_code}")
                return None, None, None

        except RequestException as e:
            print(f"요청 중 오류 발생: {str(e)}. {attempt + 1}/{max_retries} 재시도 중...")
            time.sleep(2 ** attempt)
            continue

    print("최대 재시도 횟수 초과. API 요청 실패")
    return None, None, None

# DB 연결
def DBconnect():
    global cur, conn
    try:
        conn = psycopg2.connect(host='localhost', user='postgres', password='1234', dbname='kiwoom_data')
        cur = conn.cursor()
        print("Database Connect Success")

        # 테이블 생성 (없을 경우)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.original_access_data (
                stk_cd VARCHAR(20) PRIMARY KEY,
                stk_nm VARCHAR(20),
                oyr_hgst VARCHAR(20),
                oyr_lwst VARCHAR(20),
                lst_pric VARCHAR(20),
                base_pric VARCHAR(20),
                cur_prc VARCHAR(20),
                trde_qty VARCHAR(20)
            );
        """)
        conn.commit()
        print("테이블 확인/생성 완료: original_access_data")
        return cur, conn
    except Exception as err:
        print(f"DB 연결 오류: {str(err)}")
        return None, None

# DB 닫기
def DBdisconnect():
    try:
        cur.close()
        conn.close()
        print("DB Connect Close")
    except:
        print("Error: Database Not Connected.")

# 연속 조회를 포함한 모든 데이터 가져오기
def fetch_all_data(token, data, max_iterations=10):
    all_data = []
    cont_yn = 'N'
    next_key = ''
    iteration = 0

    while True:
        if iteration >= max_iterations:
            print(f"최대 반복 횟수({max_iterations}) 도달. 연속 조회 중단.")
            break

        df, cont_yn, next_key = fn_ka10001(token, data, cont_yn, next_key)
        if df is None:
            break

        all_data.append(df)
        print(f"가져온 데이터: {len(df)} rows")

        if cont_yn != 'Y':
            print("더 이상 가져올 데이터가 없습니다. 연속 조회 중단.")
            break

        cont_yn = 'Y'
        next_key = next_key or ''
        iteration += 1
        print(f"연속 조회 {iteration}회 완료. 다음 조회를 진행합니다...")

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None

# 데이터베이스에 데이터 삽입
def insert_to_db(df, expected_stk_cd, batch_size=100):
    try:
        # DB 연결
        cur, conn = DBconnect()
        if cur is None or conn is None:
            raise Exception("DB 연결 실패")

        inserted_count = 0
        skipped_count = 0

        # 데이터프레임의 각 행을 테이블에 삽입 (배치 처리)
        for start in range(0, len(df), batch_size):
            batch = df[start:start + batch_size]
            print(f"배치 삽입 시작: {start} ~ {start + len(batch) - 1} 행")

            for index, row in batch.iterrows():
                # stk_cd 검증
                if row['stk_cd'] != expected_stk_cd:
                    print(f"stk_cd 불일치: 예상값 {expected_stk_cd}, 실제값 {row['stk_cd']}")
                    skipped_count += 1
                    continue

                insert_query = """
                INSERT INTO public.original_access_data (
                    stk_cd, stk_nm, oyr_hgst, oyr_lwst, lst_pric, base_pric, cur_prc, trde_qty
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (stk_cd) DO NOTHING;
                """
                cur.execute(insert_query, (
                    row['stk_cd'],
                    row['stk_nm'],
                    row['oyr_hgst'],
                    row['oyr_lwst'],
                    row['lst_pric'],
                    row['base_pric'],
                    row['cur_prc'],
                    row['trde_qty']
                ))

                # 삽입 여부 확인
                if cur.rowcount > 0:
                    inserted_count += 1
                else:
                    skipped_count += 1
                    print(f"중복 데이터 무시됨: stk_cd={row['stk_cd']}")

            # 배치 커밋
            conn.commit()
            print(f"배치 삽입 완료: {len(batch)} rows (삽입: {inserted_count}, 무시: {skipped_count})")

        print(f"모든 데이터 삽입 완료 - 총 삽입: {inserted_count}, 총 무시: {skipped_count}")

    except Exception as err:
        print("데이터 삽입 중 오류:", str(err))
        if conn is not None:
            conn.rollback()

    finally:
        DBdisconnect()

# 실행 구간
if __name__ == '__main__':
    # 1. 토큰 설정
    MY_ACCESS_TOKEN = main.fn_au10001()  # 접근토큰

    # 2. 요청 데이터
    params = {
        'stk_cd': '005930',  # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
    }

    # 3. 모든 데이터 가져오기
    df = fetch_all_data(
        token=MY_ACCESS_TOKEN,
        data=params,
        max_iterations=50  # 충분한 횟수로 설정
    )

    # 4. 데이터베이스에 삽입
    if df is not None:
        print(f"총 {len(df)} rows 데이터를 삽입합니다.")
        insert_to_db(df, expected_stk_cd=params['stk_cd'], batch_size=100)