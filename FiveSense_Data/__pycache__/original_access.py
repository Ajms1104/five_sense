import requests
import json
import pandas as pd
import psycopg2
import main
import time
from requests.exceptions import RequestException
from psycopg2.extras import execute_values

##### 종목 정보 리스트 요청 (ka10099) #######

def fn_ka10099(token, data, cont_yn='N', next_key='', max_retries=3):
    host = 'https://mockapi.kiwoom.com'  # 모의투자
    endpoint = '/api/dostk/stkinfo'
    url = host + endpoint

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': 'ka10099',
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data)
            print('응답 코드:', response.status_code)
            print('헤더:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
            print('바디:', json.dumps(response.json(), indent=4, ensure_ascii=False))

            if response.status_code == 429:
                print(f"429 Too Many Requests 에러 발생. {attempt + 1}/{max_retries} 재시도 중...")
                time.sleep(2 ** attempt)  # 지수 백오프
                continue

            if response.status_code == 200:
                res = response.json().get('list', [])
                if not res:
                    print("응답에 데이터가 없습니다.")
                    return None, None, None
                
                df = pd.DataFrame(res)
                print("원본 데이터프레임:\n", df)

                # 필요한 컬럼만 선택
                required_columns = ['code', 'name', 'listCount', 'upSizeName']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    print(f"누락된 컬럼: {missing_columns}")
                    return None, None, None
                
                df = df[required_columns]
                print("전처리된 데이터프레임:\n", df)

                time.sleep(1)  # API 호출 제한 방지
                return df, response.headers.get('cont-yn'), response.headers.get('next-key')
            else:
                print(f"API 요청 실패: 상태 코드 {response.status_code}")
                return None, None, None

        except RequestException as e:
            print(f"요청 중 오류 발생: {str(e)}. {attempt + 1}/{max_retries} 재시도 중...")
            time.sleep(2 ** attempt)
            continue

    print("최대 재시도 횟수 초과. API 요청 실패")
    return None, None, None

##### 주식 기본 정보 요청 (ka10001) #######

def fn_ka10001(token, data, cont_yn='N', next_key='', max_retries=3):
    host = 'https://mockapi.kiwoom.com'  # 모의투자
    endpoint = '/api/dostk/stkinfo'
    url = host + endpoint

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': 'ka10001',
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data)
            print('응답 코드:', response.status_code)
            print('헤더:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
            print('바디:', json.dumps(response.json(), indent=4, ensure_ascii=False))

            if response.status_code == 429:
                print(f"429 Too Many Requests 에러 발생. {attempt + 1}/{max_retries} 재시도 중...")
                time.sleep(2 ** attempt)  # 지수 백오프
                continue

            if response.status_code == 200:
                res = response.json()
                if isinstance(res, dict) and res.get('return_code') != 0:
                    print(f"API 오류: {res.get('return_msg', '알 수 없는 오류')}")
                    return None, None, None

                if isinstance(res, list):
                    df = pd.DataFrame(res)
                else:
                    df = pd.DataFrame([res])

                required_columns = ['stk_cd', 'stk_nm', 'mac', 'mac_wght', 'trde_qty']
                available_columns = [col for col in required_columns if col in df.columns]
                df = df[available_columns]

                if df.empty:
                    print("응답 데이터가 비어있습니다.")
                    return None, None, None

                print("전처리된 데이터프레임:\n", df)
                time.sleep(1)  # 요청 간 딜레이
                return df, response.headers.get('cont-yn'), response.headers.get('next-key')
            else:
                print(f"API 요청 실패: 상태 코드 {response.status_code}")
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
                stk_nm VARCHAR(40),
                mac VARCHAR(20),
                mac_wght VARCHAR(20),
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

# 종목 리스트 가져오기 (ka10099)
def fetch_all_data(token, data, max_iterations=50, max_rows=3000):
    all_data = []
    cont_yn = 'N'
    next_key = ''
    iteration = 0
    total_rows = 0

    while True:
        if iteration >= max_iterations:
            print(f"최대 반복 횟수({max_iterations}) 도달. 연속 조회 중단.")
            break

        df, cont_yn, next_key = fn_ka10099(token, data, cont_yn, next_key)
        if df is None:
            print("데이터를 가져오지 못했습니다. 조회 중단.")
            break

        if not df.empty:
            rows_to_add = min(len(df), max_rows - total_rows)
            if rows_to_add > 0:
                df = df.iloc[:rows_to_add]
                all_data.append(df)
                total_rows += len(df)
                print(f"가져온 데이터: {len(df)} rows (총 {total_rows} rows)")

        if total_rows >= max_rows:
            print(f"최대 행 수({max_rows}) 도달. 연속 조회 중단.")
            break

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

# 시가총액 상위 50개 종목 데이터 가져오기
def fetch_top_50_by_market_cap(token, max_iterations=50):
    # 1. 종목 리스트 가져오기 (ka10099)
    params = {
        'mrkt_tp': '0'  # 코스피
    }
    df_codes = fetch_all_data(token, params, max_iterations, max_rows=3000)
    if df_codes is None or df_codes.empty:
        print("종목 리스트를 가져오지 못했습니다.")
        return None

    # 2. 종목코드 추출
    stock_codes = df_codes['code'].tolist()
    print(f"총 {len(stock_codes)}개의 종목코드를 가져왔습니다.")

    # 3. 각 종목에 대해 상세 정보 요청 (ka10001)
    all_data = []
    for stk_cd in stock_codes:
        params = {
            'stk_cd': stk_cd
        }
        df, cont_yn, next_key = fn_ka10001(token, params)
        if df is not None:
            all_data.append(df)
            print(f"종목 {stk_cd} 데이터 가져오기 성공: {len(df)} rows")
        else:
            print(f"종목 {stk_cd} 데이터 가져오기 실패")

    if not all_data:
        print("상세 데이터를 가져오지 못했습니다.")
        return None

    # 4. 데이터 합치기 및 시가총액 정렬
    df = pd.concat(all_data, ignore_index=True)
    try:
        df['mac'] = pd.to_numeric(df['mac'], errors='coerce')
        df = df.dropna(subset=['mac'])  # 시가총액이 숫자가 아닌 경우 제외
        df = df.sort_values(by='mac', ascending=False).head(50)  # 상위 50개 선택
        print("시가총액 상위 50개 종목:\n", df[['stk_cd', 'stk_nm', 'mac']])
    except Exception as e:
        print(f"시가총액 정렬 중 오류: {str(e)}")
        return None

    return df

# 데이터베이스에 데이터 삽입
def insert_to_db(df, batch_size=100):
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

            # 배치 데이터 준비
            values = [
                (
                    row['stk_cd'],
                    row['stk_nm'],
                    str(row['mac']),  # 숫자를 문자열로 변환
                    row['mac_wght'],
                    row['trde_qty']
                )
                for index, row in batch.iterrows()
            ]

            if not values:
                print("배치에 유효한 데이터 없음")
                skipped_count += len(batch)
                continue

            # 배치 삽입 쿼리
            insert_query = """
            INSERT INTO public.original_access_data (
                stk_cd, stk_nm, mac, mac_wght, trde_qty
            )
            VALUES %s
            ON CONFLICT (stk_cd) DO NOTHING;
            """

            # execute_values로 배치 삽입
            execute_values(cur, insert_query, values)
            inserted_count += cur.rowcount
            skipped_count += len(batch) - cur.rowcount
            print(f"배치 삽입 완료: {len(batch)} rows (삽입: {cur.rowcount}, 무시: {len(batch) - cur.rowcount})")

            # 배치 커밋
            conn.commit()

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
    MY_ACCESS_TOKEN = main.fn_au10001()  # 접근 토큰

    # 2. 시가총액 상위 50개 종목 데이터 가져오기
    df = fetch_top_50_by_market_cap(
        token=MY_ACCESS_TOKEN,
        max_iterations=50
    )

    # 3. 데이터베이스에 삽입
    if df is not None:
        print(f"총 {len(df)} rows 데이터를 삽입합니다.")
        insert_to_db(df, batch_size=100)
    else:
        print("삽입할 데이터가 없습니다.")