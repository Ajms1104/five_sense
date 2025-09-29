import requests
import json
import pandas as pd
import psycopg2
import time
from requests.exceptions import RequestException
from datetime import datetime
import numpy as np
import main  # 토큰 획득을 위한 main 모듈 (가정)

# DB 연결
def DBconnect(create_table=False):
    global cur, conn
    try:
        conn = psycopg2.connect(host='localhost', user='postgres', password='1234', dbname='kiwoom_data')
        cur = conn.cursor()
        print("데이터베이스 연결 성공")
        if create_table:
            try:
                # 기존 테이블 삭제
                cur.execute("DROP TABLE IF EXISTS public.stock_daily_data;")
                print("기존 stock_daily_data 테이블 삭제 완료")
                
                create_table_query = """
                CREATE TABLE public.stock_daily_data (
                    stk_cd VARCHAR(20),
                    dt NUMERIC,
                    cur_prc NUMERIC,
                    trde_qty NUMERIC,
                    open_pric NUMERIC,
                    high_pric NUMERIC,
                    low_pric NUMERIC,
                    trde_prica NUMERIC,
                    volatility NUMERIC,
                    PRIMARY KEY (stk_cd, dt)
                );
                """
                cur.execute(create_table_query)
                conn.commit()
                print("기본 키 설정 완료: (stk_cd, dt)")
            except Exception as e:
                print(f"기본 키 설정 중 오류: {str(e)}")
                conn.rollback()
        return cur, conn
    except Exception as err:
        print(f"데이터베이스 연결 실패: {str(err)}")
        return None, None

# DB 닫기
def DBdisconnect():
    global cur, conn
    try:
        if cur is not None and not cur.closed:
            cur.close()
            print("커서 닫기 완료")
        if conn is not None and not conn.closed:
            conn.close()
            print("데이터베이스 연결 종료")
    except Exception as err:
        print(f"연결 종료 중 오류: {str(err)}")
    finally:
        cur = None
        conn = None

# 상위 50 요청 
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

# 주식 일봉 차트 조회 요청
def fn_ka10081(token, data, cont_yn='N', next_key='', max_retries=3):
    host = 'https://mockapi.kiwoom.com'
    endpoint = '/api/dostk/chart'
    url = host + endpoint
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': 'ka10081',
    }
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data)
            print('응답 코드:', response.status_code)
            print('헤더:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
            print('바디:', json.dumps(response.json(), indent=4, ensure_ascii=False))
            if response.status_code == 429:
                print(f"429 Too Many Requests 에러 발생. {attempt + 1}/{max_retries} 재시도 중...")
                time.sleep(2 ** attempt)
                continue
            if response.status_code == 200:
                res = response.json().get('stk_dt_pole_chart_qry', [])
                df = pd.DataFrame(res)
                print("원본 데이터프레임:\n", df)
                if df.empty:
                    print("받은 데이터가 비어 있습니다.")
                    return None, None, None
                required_columns = ['dt', 'open_pric', 'high_pric', 'low_pric', 'cur_prc', 'trde_qty', 'trde_prica']
                if not all(col in df.columns for col in required_columns):
                    missing_cols = [col for col in required_columns if col not in df.columns]
                    print(f"필수 컬럼이 누락되었습니다: {missing_cols}")
                    return None, None, None
                df = df[required_columns]
                df['stk_cd'] = data['stk_cd']
                numeric_columns = ['cur_prc', 'open_pric', 'high_pric', 'low_pric']
                for col in numeric_columns:
                    df[col] = df[col].astype(str)
                    df[col] = df[col].apply(lambda x: float(x.replace('--', '')) / 100 if x.startswith('--') else float(x.replace('+', '')) / 100 if x else None)
                df['trde_qty'] = df['trde_qty'].astype(str).replace('', np.nan).astype(float)
                df['trde_prica'] = df['trde_prica'].astype(str).replace('', np.nan).astype(float)
                # 변동성 계산: (high_pric - low_pric) / cur_prc
                df['volatility'] = (df['high_pric'] - df['low_pric']) / df['cur_prc']
                df = df.sort_values(by='dt', ascending=True).reset_index(drop=True)
                print("전처리된 데이터프레임:\n", df)
                time.sleep(1)
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

# 연속 조회를 포함한 모든 데이터 가져오기
def fetch_all_data(token, data, start_date='20240101', end_date=None, max_iterations=10):
    all_data = []
    cont_yn = 'N'
    next_key = ''
    iteration = 0
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')
    print(f"조회 기간: {start_date} ~ {end_date}")
    try:
        start_date_dt = datetime.strptime(start_date, '%Y%m%d')
    except ValueError:
        print(f"잘못된 start_date 형식: {start_date}. YYYYMMDD 형식이어야 합니다.")
        return None
    end_date_dt = datetime.strptime(end_date, '%Y%m%d')
    data['base_dt'] = end_date
    while True:
        if iteration >= max_iterations:
            print(f"최대 반복 횟수({max_iterations}) 도달. 연속 조회 중단.")
            break
        df, cont_yn, next_key = fn_ka10081(token, data, cont_yn, next_key)
        if df is None:
            break
        df['date_dt'] = pd.to_datetime(df['dt'], format='%Y%m%d')
        earliest_date = df['date_dt'].min()
        latest_date = df['date_dt'].max()
        df = df[(df['date_dt'] >= start_date_dt) & (df['date_dt'] <= end_date_dt)].copy()
        df = df.drop(columns=['date_dt'])
        if not df.empty:
            all_data.append(df)
            print(f"가져온 데이터: {len(df)} rows, 날짜 범위: {df['dt'].min()} ~ {df['dt'].max()}")
        if earliest_date < start_date_dt:
            print(f"가장 오래된 날짜({earliest_date.strftime('%Y%m%d')})가 시작 날짜({start_date})보다 이전입니다. 연속 조회 중단.")
            break
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
    global cur, conn
    try:
        print(f"삽입할 총 데이터: {len(df)} 행")
        if conn is None or conn.closed or cur is None or cur.closed:
            print("커서 또는 연결이 닫혔습니다. 재연결 시도...")
            cur, conn = DBconnect(create_table=False)
            if cur is None or conn is None:
                raise Exception("데이터베이스 재연결 실패")
        inserted_rows = 0
        for start in range(0, len(df), batch_size):
            end = min(start + batch_size, len(df))
            batch = df[start:end]
            print(f"배치 삽입 시작: {start} ~ {end - 1} 행 ({len(batch)} 행)")
            for index, row in batch.iterrows():
                if row['stk_cd'] != expected_stk_cd:
                    print(f"stk_cd 불일치: 예상값 {expected_stk_cd}, 실제값 {row['stk_cd']}")
                    continue
                insert_query = """
                INSERT INTO public.stock_daily_data (stk_cd, dt, cur_prc, trde_qty, open_pric, high_pric, low_pric, trde_prica, volatility)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (stk_cd, dt) DO NOTHING;
                """
                cur.execute(insert_query, (
                    row['stk_cd'],
                    row['dt'],
                    row['cur_prc'],
                    row['trde_qty'],
                    row['open_pric'],
                    row['high_pric'],
                    row['low_pric'],
                    row['trde_prica'],
                    row['volatility']
                ))
            conn.commit()
            inserted_rows += len(batch)
            print(f"배치 삽입 완료: {len(batch)} 행, 누적 삽입: {inserted_rows} 행")
        print(f"모든 데이터 삽입 완료: 총 {inserted_rows} 행")
    except Exception as err:
        print(f"데이터 삽입 중 오류: {str(err)}")
        if conn is not None and not conn.closed:
            conn.rollback()
        raise

# 상위 50개 종목 코드 가져오기
def get_top50_codes(token):
    params = {
        'trde_upper_tp': '2',
        'amt_qty_tp': '1',
        'mrkt_tp': 'P00101',
        'stex_tp': '1',
    }
    df, _, _ = fn_ka90003(
        token=token,
        data=params,
        max_retries=3,
        max_items=50
    )
    if df is not None and not df.empty:
        return df['stk_cd'].tolist()
    else:
        print("❌ Top50 종목 코드를 가져오지 못했습니다.")
        return []

# 변동성 분석
def analyze_volatility(start_date='20200101', end_date=None):
    global cur, conn
    try:
        cur, conn = DBconnect(create_table=False)
        if cur is None or conn is None:
            raise Exception("데이터베이스 연결 실패")

        # 데이터 조회
        query = """
        SELECT stk_cd, dt, cur_prc, high_pric, low_pric, volatility
        FROM public.stock_daily_data
        WHERE dt >= %s AND dt <= %s;
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        cur.execute(query, (start_date, end_date))
        data = cur.fetchall()
        if not data:
            print("데이터베이스에서 데이터를 조회하지 못했습니다.")
            return None

        # 데이터프레임 생성
        df = pd.DataFrame(data, columns=['stk_cd', 'dt', 'cur_prc', 'high_pric', 'low_pric', 'volatility'])
        df['dt'] = pd.to_datetime(df['dt'], format='%Y%m%d')

        # 월별 평균 변동성 집계
        df['year_month'] = df['dt'].dt.to_period('M')
        monthly_volatility = df.groupby('year_month')['volatility'].mean().reset_index()
        monthly_volatility = monthly_volatility.sort_values(by='volatility', ascending=False)

        print("\n월별 평균 변동성 (상위 50개):")
        print(monthly_volatility)

        # 상위 5개 변동성 날짜 (종목별 상위 날짜)
        daily_volatility = df.groupby(['stk_cd', 'dt'])['volatility'].mean().reset_index()
        daily_volatility = daily_volatility.sort_values(by='volatility', ascending=False)
        daily_volatility['dt'] = daily_volatility['dt'].dt.strftime('%Y%m%d')

        print("\n종목별 상위 50개 변동성 날짜:")
        print(daily_volatility)

        return monthly_volatility, daily_volatility

    except Exception as err:
        print(f"변동성 분석 중 오류: {str(err)}")
        return None
    finally:
        DBdisconnect()

# 실행 구간
if __name__ == '__main__':
    # 1. 토큰 설정
    MY_ACCESS_TOKEN = main.fn_au10001()  
    # 2. 데이터베이스 연결 및 테이블 생성
    cur, conn = DBconnect(create_table=True)
    if cur is None or conn is None:
        print("프로그램 종료: 데이터베이스 연결 실패")
        exit()
    # 3. 상위 50개 주식 코드 가져오기
    stk_cd_list = get_top50_codes(MY_ACCESS_TOKEN)
    if not stk_cd_list:
        print("프로그램 종료: 주식 코드 리스트를 가져오지 못했습니다.")
        DBdisconnect()
        exit()
    print(f"\n조회할 주식 코드: {stk_cd_list}")
    # 4. 각 주식 코드에 대해 데이터 조회 및 삽입
    for stk_cd in stk_cd_list:
        print(f"\n주식 (stk_cd: {stk_cd}) 데이터 조회 중")
        params = {
            'stk_cd': stk_cd,
            'base_dt': None,
            'upd_stkpc_tp': '1',
        }
        cur.execute("SELECT DISTINCT stk_cd FROM public.stock_daily_data WHERE stk_cd = %s;", (stk_cd,))
        already_inserted = {row[0] for row in cur.fetchall()}
        if stk_cd in already_inserted:
            print(f"{stk_cd} 이미 처리됨. 최신 데이터만 추가로 조회.")
            cur.execute("SELECT MAX(dt) FROM public.stock_daily_data WHERE stk_cd = %s;", (stk_cd,))
            latest_date = cur.fetchone()[0]
            if latest_date:
                start_date = (datetime.strptime(str(int(latest_date)), '%Y%m%d') + pd.Timedelta(days=1)).strftime('%Y%m%d')
            else:
                start_date = '20200101'
        else:
            start_date = '20200101'
        df = fetch_all_data(
            token=MY_ACCESS_TOKEN,
            data=params,
            start_date=start_date,
            end_date=None,
            max_iterations=100
        )
        if df is not None and not df.empty:
            print(f"총 {len(df)} row 데이터를 삽입합니다.")
            insert_to_db(df, expected_stk_cd=stk_cd, batch_size=1000)
        else:
            print("가져온 데이터가 없습니다.")
    # 5. 변동성 분석
    monthly_volatility, daily_volatility = analyze_volatility(start_date='20200101')
    if monthly_volatility is not None:
        print("\n변동성 분석 완료")
    else:
        print("\n변동성 분석 실패")
    # 6. 데이터베이스 연결 종료
    DBdisconnect()