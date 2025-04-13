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
        conn = psycopg2.connect(host='localhost', user='postgres', password='1234', dbname='kiwoom_data')
        cur = conn.cursor()
        print("Database Connect Success")

        # 기존 기본 키 삭제 및 새로운 기본 키 추가
        try:
            cur.execute("ALTER TABLE public.price_data DROP CONSTRAINT IF EXISTS price_data_pkey;")
            cur.execute("""
                ALTER TABLE public.price_data
                ADD CONSTRAINT price_data_pkey PRIMARY KEY (stk_cd, date);
            """)
            conn.commit()
            print("기본 키 설정 완료: (stk_cd, date)")
        except Exception as e:
            print(f"기본 키 설정 중 오류: {str(e)}")
            conn.rollback()

        return cur, conn
    except Exception as err:
        print(str(err))
        return None, None

# DB 닫기
def DBdisconnect():
    try:
        conn.close()
        cur.close()
        print("DB Connect Close")
    except:
        print("Error: Database Not Connected.")

# API 요청 (단일 요청)
def fn_ka10086(token, data, cont_yn='N', next_key='', max_retries=3):
    host = 'https://mockapi.kiwoom.com'  # 모의투자
    endpoint = '/api/dostk/mrkcond'
    url = host + endpoint

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': 'ka10086',
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data)
            print('Code:', response.status_code)
            print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
            print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))

            if response.status_code == 429:
                print(f"429 Too Many Requests 에러 발생. {attempt + 1}/{max_retries} 재시도 중...")
                time.sleep(2 ** attempt)  # 지수 백오프 (1초, 2초, 4초 대기)
                continue

            if response.status_code == 200:
                res = response.json()['daly_stkpc']
                df = pd.DataFrame(res)
                print("원본 데이터프레임:\n", df)

                # 필요한 컬럼만 선택
                required_columns = ['date', 'open_pric', 'high_pric', 'low_pric', 'close_pric', 'ind_netprps']
                df = df[required_columns]

                # stk_cd 추가
                df['stk_cd'] = data['stk_cd']

                # 부호를 해석해서 숫자로 변환
                numeric_columns = ['open_pric', 'high_pric', 'low_pric', 'close_pric', 'ind_netprps']
                for col in numeric_columns:
                    df[col] = df[col].astype(str)
                    df[col] = df[col].apply(lambda x: -float(x.replace('--', '')) if x.startswith('--') else float(x.replace('+', '')) if x else None)

                # 날짜순으로 정렬 (오름차순)
                df = df.sort_values(by='date', ascending=True).reset_index(drop=True)
                print("전처리된 데이터프레임:\n", df)

                # 요청 간 딜레이 추가
                time.sleep(1)  # 1초 대기

                return df, response.headers.get('cont-yn'), response.headers.get('next-key')
            else:
                print("API 요청 실패")
                return None, None, None

        except RequestException as e:
            print(f"요청 중 오류 발생: {str(e)}. {attempt + 1}/{max_retries} 재시도 중...")
            time.sleep(2 ** attempt)
            continue

    print("최대 재시도 횟수 초과. API 요청 실패")
    return None, None, None

# 연속 조회를 포함한 모든 데이터 가져오기 (날짜 범위 제한 추가)
def fetch_all_data(token, data, start_date='20230101', end_date=None, max_iterations=10):
    all_data = []
    cont_yn = 'N'
    next_key = ''
    iteration = 0

    # end_date가 None이면 현재 날짜로 설정
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')
    print(f"조회 기간: {start_date} ~ {end_date}")

    # start_date와 end_date를 datetime 객체로 변환
    start_date_dt = datetime.strptime(start_date, '%Y%m%d')
    end_date_dt = datetime.strptime(end_date, '%Y%m%d')

    # API 요청의 qry_dt를 end_date로 설정
    data['qry_dt'] = end_date

    while True:
        if iteration >= max_iterations:
            print(f"최대 반복 횟수({max_iterations}) 도달. 연속 조회 중단.")
            break

        df, cont_yn, next_key = fn_ka10086(token, data, cont_yn, next_key)
        if df is None:
            break

        # 날짜를 datetime 객체로 변환하여 비교
        df['date_dt'] = pd.to_datetime(df['date'], format='%Y%m%d')
        earliest_date = df['date_dt'].min()
        latest_date = df['date_dt'].max()

        # start_date와 end_date 사이의 데이터만 필터링
        df = df[(df['date_dt'] >= start_date_dt) & (df['date_dt'] <= end_date_dt)].copy()
        df = df.drop(columns=['date_dt'])  # 임시 컬럼 삭제

        if not df.empty:
            all_data.append(df)
            print(f"가져온 데이터: {len(df)} rows, 날짜 범위: {df['date'].min()} ~ {df['date'].max()}")

        # 가장 오래된 날짜가 start_date보다 이전이면 더 이상 조회하지 않음
        if earliest_date < start_date_dt:
            print(f"가장 오래된 날짜({earliest_date.strftime('%Y%m%d')})가 시작 날짜({start_date})보다 이전입니다. 연속 조회 중단.")
            break

        # 가장 최신 날짜가 end_date보다 이후이면 더 이상 조회하지 않음
        if latest_date > end_date_dt:
            print(f"가장 최신 날짜({latest_date.strftime('%Y%m%d')})가 종료 날짜({end_date})보다 이후입니다. 연속 조회 중단.")
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

# 데이터베이스에 데이터 삽입
def insert_to_db(df, expected_stk_cd, batch_size=1000):
    try:
        # DB 연결
        cur, conn = DBconnect()
        if cur is None or conn is None:
            raise Exception("DB 연결 실패")

        # 데이터프레임의 각 행을 테이블에 삽입 (배치 처리)
        for start in range(0, len(df), batch_size):
            batch = df[start:start + batch_size]
            print(f"배치 삽입 시작: {start} ~ {start + len(batch) - 1} 행")

            for index, row in batch.iterrows():
                # stk_cd 검증
                if row['stk_cd'] != expected_stk_cd:
                    print(f"stk_cd 불일치: 예상값 {expected_stk_cd}, 실제값 {row['stk_cd']}")
                    continue

                insert_query = """
                INSERT INTO public.price_data (stk_cd, date, open_pric, high_pric, low_pric, close_pric, ind_netprps)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (stk_cd, date) DO NOTHING;
                """
                cur.execute(insert_query, (
                    row['stk_cd'],
                    row['date'],
                    row['open_pric'],
                    row['high_pric'],
                    row['low_pric'],
                    row['close_pric'],
                    row['ind_netprps']
                ))
            
            # 배치 커밋
            conn.commit()
            print(f"배치 삽입 완료: {len(batch)} rows")

        print("모든 데이터 삽입 완료")

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

    # 2. 요청 데이터
    params = {
        'stk_cd': '005930',  # 종목 코드 (삼성전자)
        'qry_dt': None,      # fetch_all_data에서 동적으로 설정
        'indc_tp': '0',      # 표시 구분 (0: 수량)
    }

    # 3. 모든 데이터 가져오기 (2020년 1월 1일 ~ 현재 날짜)
    df = fetch_all_data(
        token=MY_ACCESS_TOKEN,
        data=params,
        start_date='20200101',  # 2020년 1월 1일
        end_date=None,          # 현재 날짜로 동적 설정
        max_iterations=150       # 충분한 횟수로 설정 (2년치 데이터라면 넉넉히 + 3년치 더 넣음(총 5년치))
    )

    # 4. 데이터베이스에 삽입
    if df is not None:
        print(f"총 {len(df)} rows 데이터를 삽입합니다.")
        insert_to_db(df, expected_stk_cd=params['stk_cd'], batch_size=1000)
        

