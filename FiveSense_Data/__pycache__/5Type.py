import requests
import json
import pandas as pd
import psycopg2
import time
from requests.exceptions import RequestException
from psycopg2.extras import execute_values
import numpy as np

# 데이터베이스 연결 설정
def connect_db():
    try:
        conn = psycopg2.connect(
            host='localhost',
            user='postgres',
            password='1234',
            dbname='kiwoom_data'
        )
        cur = conn.cursor()
        print("Database Connect Success")

        # 테이블 생성 (없을 경우)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.data_5type (
                stk_cd VARCHAR(20) PRIMARY KEY,
                stk_nm VARCHAR(40),
                eps NUMERIC,
                bps NUMERIC,
                sale_amt NUMERIC,
                bus_pro NUMERIC,
                cup_nga NUMERIC
            );
        """)
        conn.commit()
        print("테이블 확인/생성 완료: data_5type")
        return cur, conn
    except Exception as err:
        print(f"DB 연결 오류: {str(err)}")
        return None, None

# 데이터베이스 연결 종료
def disconnect_db(cur, conn):
    try:
        if cur and not cur.closed:
            cur.close()
            print("커서 닫기 완료")
        if conn and not conn.closed:
            conn.close()
            print("DB Connect Close")
    except Exception as err:
        print(f"연결 종료 중 오류: {str(err)}")

# ka10099 API 요청 (종목 리스트)
def fn_ka10099(token, data, cont_yn='N', next_key='', max_retries=3):
    host = 'https://mockapi.kiwoom.com'
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

            if response.status_code == 429:
                print(f"429 Too Many Requests 에러 발생. {attempt + 1}/{max_retries} 재시도 중...")
                time.sleep(2 ** attempt)
                continue

            if response.status_code == 200:
                res = response.json().get('list', [])
                if not res:
                    print("응답에 데이터가 없습니다.")
                    return None, None, None
                
                df = pd.DataFrame(res)
                required_columns = ['code']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    print(f"누락된 컬럼: {missing_columns}")
                    return None, None, None
                
                df = df[required_columns]
                print("전처리된 데이터프레임:\n", df)
                time.sleep(1)
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

# ka10001 API 요청 (시가총액 정보)
def fn_ka10001(token, data, cont_yn='N', next_key='', max_retries=3):
    host = 'https://mockapi.kiwoom.com'
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

            if response.status_code == 429:
                print(f"429 Too Many Requests 에러 발생. {attempt + 1}/{max_retries} 재시도 중...")
                time.sleep(2 ** attempt)
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

                required_columns = ['stk_cd', 'mac']
                available_columns = [col for col in required_columns if col in df.columns]
                df = df[available_columns]

                if df.empty:
                    print("응답 데이터가 비어있습니다.")
                    return None, None, None

                print("전처리된 데이터프레임:\n", df)
                time.sleep(1)
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

# ka10001 API 요청 (상세 데이터)
def fetch_ka10001(token, data, cont_yn='N', next_key='', max_retries=3, delay=1):
    url = 'https://mockapi.kiwoom.com/api/dostk/stkinfo'
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
            print(f'응답 코드: {response.status_code}')
            print('헤더:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))

            if response.status_code == 429:
                print(f"429 Too Many Requests 에러 발생. {attempt + 1}/{max_retries} 재시도 중...")
                time.sleep(2 ** attempt + delay)
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
                print("원본 데이터프레임:\n", df)

                # 필요한 컬럼만 선택
                required_columns = ['stk_cd', 'stk_nm', 'eps', 'bps', 'sale_amt', 'bus_pro', 'cup_nga']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    print(f"누락된 컬럼: {missing_columns}")
                    return None, None, None

                df = df[required_columns]

                # 부호를 해석해서 숫자로 변환 (stk_nm 제외)
                numeric_columns = ['eps', 'bps', 'sale_amt', 'bus_pro', 'cup_nga']
                for col in numeric_columns:
                    df[col] = pd.to_numeric(
                        df[col].astype(str)
                               .str.replace('--', '-', regex=False)  # --123 → -123
                               .str.replace(',', '', regex=False)   # 1,234 → 1234
                               .replace('', np.nan), 
                        errors='coerce'
                    )


                print("전처리된 데이터프레임:\n", df)
                time.sleep(delay)
                return df, response.headers.get('cont-yn'), response.headers.get('next-key')
            else:
                print(f"API 요청 실패: {response.status_code}")
                return None, None, None

        except RequestException as e:
            print(f"요청 중 오류 발생: {str(e)}. {attempt + 1}/{max_retries} 재시도 중...")
            time.sleep(2 ** attempt + delay)
            continue

    print("최대 재시도 횟수 초과. API 요청 실패")
    return None, None, None

# 연속 조회를 포함한 ka10099 데이터 가져오기
def fetch_all_ka10099(token, data, max_iterations=50, max_rows=3000):
    all_data = []
    cont_yn = 'N'
    next_key = ''
    iteration = 0
    total_rows = 0

    while iteration < max_iterations:
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

    return pd.concat(all_data, ignore_index=True) if all_data else None

# 연속 조회를 포함한 ka10001 데이터 가져오기
def fetch_all_ka10001(token, data, max_iterations=10, delay=1):
    all_data = []
    cont_yn = 'N'
    next_key = ''
    iteration = 0

    while iteration < max_iterations:
        df, cont_yn, next_key = fetch_ka10001(token, data, cont_yn, next_key, delay=delay)
        if df is None:
            break

        if not df.empty:
            all_data.append(df)
            print(f"가져온 데이터: {len(df)} rows")

        if cont_yn != 'Y' or not next_key:
            print("더 이상 가져올 데이터가 없습니다. 조회 중단.")
            break

        cont_yn = 'Y'
        next_key = next_key or ''
        iteration += 1
        print(f"연속 조회 {iteration}회 완료. 다음 조회를 진행합니다...")

    return pd.concat(all_data, ignore_index=True) if all_data else None

# 데이터베이스에 데이터 삽입
def insert_to_db(cur, conn, df, expected_stk_cd, batch_size=1000):
    try:
        print(f"삽입할 총 데이터: {len(df)} 행")
        insert_query = """
        INSERT INTO public.data_5type (stk_cd, stk_nm, eps, bps, sale_amt, bus_pro, cup_nga)
        VALUES %s
        ON CONFLICT (stk_cd) DO NOTHING;
        """

        inserted_count = 0
        skipped_count = 0

        for start in range(0, len(df), batch_size):
            end = min(start + batch_size, len(df))
            batch = df[start:end]
            print(f"배치 삽입 시작: {start} ~ {end - 1} 행")

            # NaN, "" → None 처리
            batch = batch.replace({np.nan: None, "": None})

            # 배치 데이터 준비
            values = [
                (
                    row['stk_cd'],
                    row['stk_nm'],
                    row['eps'],
                    row['bps'],
                    row['sale_amt'],
                    row['bus_pro'],
                    row['cup_nga']
                )
                for _, row in batch.iterrows() if row['stk_cd'] == expected_stk_cd
            ]

            if not values:
                print(f"배치 {start} ~ {end - 1}에서 유효한 데이터 없음 (stk_cd 불일치)")
                skipped_count += len(batch)
                continue

            # execute_values로 배치 삽입
            execute_values(cur, insert_query, values)
            inserted_count += cur.rowcount
            skipped_count += len(batch) - cur.rowcount
            conn.commit()
            print(f"배치 삽입 완료: {len(batch)} rows (삽입: {cur.rowcount}, 무시: {len(batch) - cur.rowcount})")

        print(f"모든 데이터 삽입 완료 - 총 삽입: {inserted_count}, 총 무시: {skipped_count}")
        return inserted_count, skipped_count

    except Exception as err:
        print(f"데이터 삽입 중 오류: {str(err)}")
        conn.rollback()
        raise

# 시가총액 상위 50개 종목의 상세 데이터 가져오기
def fetch_top_50_fundamentals(token, max_iterations=50):
    # 1. 종목 리스트 가져오기 (ka10099)
    params = {
        'mrkt_tp': '0'  # 코스피
    }
    df_codes = fetch_all_ka10099(token, params, max_iterations, max_rows=3000)
    if df_codes is None or df_codes.empty:
        print("종목 리스트를 가져오지 못했습니다.")
        return None

    # 2. 각 종목에 대해 시가총액 정보 요청 (ka10001)
    all_mac_data = []
    for stk_cd in df_codes['code']:
        params = {
            'stk_cd': stk_cd
        }
        df, cont_yn, next_key = fn_ka10001(token, params)
        if df is not None:
            all_mac_data.append(df)
            print(f"종목 {stk_cd} 시가총액 데이터 가져오기 성공: {len(df)} rows")
        else:
            print(f"종목 {stk_cd} 시가총액 데이터 가져오기 실패")

    if not all_mac_data:
        print("시가총액 데이터를 가져오지 못했습니다.")
        return None

    # 3. 시가총액 상위 50개 종목 선택
    df_mac = pd.concat(all_mac_data, ignore_index=True)
    try:
        df_mac['mac'] = pd.to_numeric(df_mac['mac'], errors='coerce')
        df_mac = df_mac.dropna(subset=['mac'])
        df_mac = df_mac.sort_values(by='mac', ascending=False).head(50)
        print("시가총액 상위 50개 종목:\n", df_mac[['stk_cd', 'mac']])
    except Exception as e:
        print(f"시가총액 정렬 중 오류: {str(e)}")
        return None

    # 4. 상위 50개 종목의 상세 데이터 가져오기 (ka10001)
    all_data = []
    for stk_cd in df_mac['stk_cd']:
        print(f"\n{stk_cd} 데이터 조회 중")
        params = {
            'stk_cd': stk_cd,
            'qry_dt': None,
            'indc_tp': '0',
        }
        df = fetch_all_ka10001(token, params, max_iterations=10, delay=1)
        if df is not None and not df.empty:
            all_data.append(df)
            print(f"종목 {stk_cd} 상세 데이터 가져오기 성공: {len(df)} rows")
        else:
            print(f"종목 {stk_cd} 상세 데이터 가져오기 실패")

    if not all_data:
        print("상세 데이터를 가져오지 못했습니다.")
        return None

    return pd.concat(all_data, ignore_index=True)

# 메인 실행
if __name__ == '__main__':
    # 1. 토큰 설정
    try:
        import main
        MY_ACCESS_TOKEN = main.fn_au10001()
    except ImportError:
        print("main 모듈을 찾을 수 없습니다. 토큰을 직접 입력하세요.")
        MY_ACCESS_TOKEN = '사용자 AccessToken'

    # 2. 데이터베이스 연결
    cur, conn = connect_db()
    if cur is None or conn is None:
        print("프로그램 종료: 데이터베이스 연결 실패")
        exit()

    try:
        # 3. 시가총액 상위 50개 종목의 상세 데이터 가져오기
        df = fetch_top_50_fundamentals(
            token=MY_ACCESS_TOKEN,
            max_iterations=50
        )

        # 4. 데이터베이스에 삽입
        if df is not None and not df.empty:
            print(f"총 {len(df)} rows 데이터를 삽입합니다.")
            for stk_cd in df['stk_cd'].unique():
                df_stock = df[df['stk_cd'] == stk_cd]
                insert_to_db(cur, conn, df_stock, expected_stk_cd=stk_cd, batch_size=1000)
        else:
            print("삽입할 데이터가 없습니다.")

    finally:
        # 5. 데이터베이스 연결 종료
        disconnect_db(cur, conn)