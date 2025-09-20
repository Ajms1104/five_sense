import requests
import json
import pandas as pd
import psycopg2
from requests.exceptions import RequestException
from datetime import datetime, timedelta
import time
import numpy as np
import main  # 토큰을 가져오기 위한 모듈

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
                cur.execute("DROP TABLE IF EXISTS public.investor_data;")
                print("기존 investor_data 테이블 삭제 완료")

                # 새 테이블 생성
                create_table_query = """
                CREATE TABLE public.investor_data (
                    mrkt_tp VARCHAR(1),
                    base_dt NUMERIC,
                    stex_tp VARCHAR(1),
                    inds_cd VARCHAR(20),
                    inds_nm VARCHAR(20),
                    cur_prc NUMERIC,
                    flu_rt NUMERIC,
                    pred_pre NUMERIC,
                    trde_qty NUMERIC,
                    ind_netprps NUMERIC,
                    frgnr_netprps NUMERIC,
                    orgn_netprps NUMERIC,
                    PRIMARY KEY (mrkt_tp, base_dt, stex_tp, inds_cd)
                );
                """
                cur.execute(create_table_query)
                conn.commit()
                print("기본 키 설정 완료: (mrkt_tp, base_dt, stex_tp, inds_cd)")
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

# API 요청 (단일 요청)
def fn_ka10051(token, data, cont_yn='N', next_key='', max_retries=3):
    host = 'https://mockapi.kiwoom.com'  # 모의투자
    endpoint = '/api/dostk/sect'
    url = host + endpoint

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': 'ka10051',
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
                res = response.json().get('inds_netprps', [])  # API 응답에서 inds_netprps 리스트 가져오기
                if not res:
                    print("응답 데이터가 비어 있습니다.")
                    return None, None, None

                df = pd.DataFrame(res)
                print("원본 데이터프레임:\n", df)

                # 필요한 컬럼만 선택
                required_columns = [
                    'inds_cd', 'inds_nm', 'cur_prc', 'flu_rt', 'pred_pre', 
                    'trde_qty', 'ind_netprps', 'frgnr_netprps', 'orgn_netprps'
                ]
                available_columns = [col for col in required_columns if col in df.columns]
                df = df[available_columns]

                # mrkt_tp, base_dt, stex_tp 추가
                df['mrkt_tp'] = data['mrkt_tp']
                df['base_dt'] = data['base_dt']
                df['stex_tp'] = data['stex_tp']

                # 부호를 해석해서 숫자로 변환
                numeric_columns = ['cur_prc', 'flu_rt', 'pred_pre', 'trde_qty', 'ind_netprps', 'frgnr_netprps', 'orgn_netprps']
                for col in numeric_columns:
                    if col in df.columns:
                        df[col] = df[col].astype(str)
                        df[col] = df[col].apply(lambda x: -float(x.replace('--', '')) if x.startswith('--') else float(x.replace('+', '')) if x else None)

                # 날짜순 정렬
                df = df.sort_values(by='base_dt', ascending=True).reset_index(drop=True)
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

# 연속 조회를 포함한 모든 데이터 가져오기 (수정된 함수)
def fetch_all_data(token, data, start_date='20240101', end_date=None, max_iterations=10):
    all_data = []
    
    # end_date가 None이면 현재 날짜로 설정
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')
    print(f"조회 기간: {start_date} ~ {end_date}")

    # start_date와 end_date를 datetime 객체로 변환
    start_date_dt = datetime.strptime(start_date, '%Y%m%d')
    end_date_dt = datetime.strptime(end_date, '%Y%m%d')

    # 이미 처리된 데이터 확인 (최적화)
    try:
        cur.execute("SELECT MAX(base_dt) FROM public.investor_data WHERE mrkt_tp = %s AND stex_tp = %s;", 
                    (data['mrkt_tp'], data['stex_tp']))
        max_date = cur.fetchone()[0]
        if max_date:
            max_date_dt = datetime.strptime(str(int(max_date)), '%Y%m%d') + timedelta(days=1)
            if max_date_dt > start_date_dt:
                start_date_dt = max_date_dt
                print(f"이미 처리된 최신 날짜: {max_date}, 시작 날짜를 {start_date_dt.strftime('%Y%m%d')}로 설정")
    except Exception as e:
        print(f"최신 날짜 확인 중 오류: {str(e)}. 기본 start_date 사용: {start_date}")

    # 날짜 범위 생성
    current_date_dt = end_date_dt
    while current_date_dt >= start_date_dt:
        # API 요청의 base_dt를 현재 날짜로 설정
        data['base_dt'] = current_date_dt.strftime('%Y%m%d')
        print(f"현재 처리 중인 날짜: {data['base_dt']}")

        cont_yn = 'N'
        next_key = ''
        iteration = 0

        # 동일한 날짜 내에서 연속 조회 처리
        while True:
            if iteration >= max_iterations:
                print(f"최대 반복 횟수({max_iterations}) 도달. {data['base_dt']} 날짜의 연속 조회 중단.")
                break

            df, cont_yn, next_key = fn_ka10051(token, data, cont_yn, next_key)
            if df is None:
                print(f"{data['base_dt']} 날짜의 데이터 가져오기 실패. 다음 날짜로 이동.")
                break

            # 데이터프레임에 가져온 데이터 추가
            if not df.empty:
                all_data.append(df)
                print(f"가져온 데이터: {len(df)} rows, 날짜: {df['base_dt'].min()}")

            # 연속 조회가 더 이상 필요 없으면 중단
            if cont_yn != 'Y':
                print(f"{data['base_dt']} 날짜의 데이터 모두 가져옴. 연속 조회 중단.")
                break

            cont_yn = 'Y'
            next_key = next_key or ''
            iteration += 1
            print(f"{data['base_dt']} 날짜의 연속 조회 {iteration}회 완료. 다음 조회를 진행합니다...")

        # 다음 날짜로 이동 (하루 전)
        current_date_dt -= timedelta(days=1)
        time.sleep(1)  # 날짜 간 요청 딜레이 추가

    # 모든 데이터프레임을 하나로 합치기
    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        # 중복 제거 (mrkt_tp, base_dt, stex_tp, inds_cd 기준)
        final_df = final_df.drop_duplicates(subset=['mrkt_tp', 'base_dt', 'stex_tp', 'inds_cd'])
        print(f"총 가져온 데이터: {len(final_df)} rows, 날짜 범위: {final_df['base_dt'].min()} ~ {final_df['base_dt'].max()}")
        return final_df
    return None

# 데이터베이스에 데이터 삽입
def insert_to_db(df, expected_mrkt_tp, expected_stex_tp, expected_inds_cd_list, batch_size=1000):
    global cur, conn
    try:
        # 데이터프레임 크기 확인
        print(f"삽입할 총 데이터: {len(df)} 행")

        # 커서와 연결이 닫혔는지 확인하고 재연결
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
                # mrkt_tp, stex_tp, inds_cd 검증
                if row['mrkt_tp'] != expected_mrkt_tp or row['stex_tp'] != expected_stex_tp or row['inds_cd'] not in expected_inds_cd_list:
                    print(f"데이터 불일치: 예상 mrkt_tp={expected_mrkt_tp}, stex_tp={expected_stex_tp}, inds_cd in {expected_inds_cd_list}, 실제 mrkt_tp={row['mrkt_tp']}, stex_tp={row['stex_tp']}, inds_cd={row['inds_cd']}")
                    continue

                # 중복 데이터 삽입 방지
                insert_query = """
                INSERT INTO public.investor_data (
                    mrkt_tp, base_dt, stex_tp, inds_cd, inds_nm, cur_prc, flu_rt, pred_pre, 
                    trde_qty, ind_netprps, frgnr_netprps, orgn_netprps
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (mrkt_tp, base_dt, stex_tp, inds_cd) DO NOTHING;
                """
                cur.execute(insert_query, (
                    row['mrkt_tp'],
                    row['base_dt'],
                    row['stex_tp'],
                    row['inds_cd'],
                    row['inds_nm'],
                    row['cur_prc'],
                    row['flu_rt'],
                    row['pred_pre'],
                    row['trde_qty'],
                    row['ind_netprps'],
                    row['frgnr_netprps'],
                    row['orgn_netprps']
                ))

            # 배치 커밋
            conn.commit()
            inserted_rows += len(batch)
            print(f"배치 삽입 완료: {len(batch)} 행, 누적 삽입: {inserted_rows} 행")

        print(f"모든 데이터 삽입 완료: 총 {inserted_rows} 행")

    except Exception as err:
        print(f"데이터 삽입 중 오류: {str(err)}")
        if conn is not None and not conn.closed:
            conn.rollback()
        raise

# 실행 구간
if __name__ == '__main__':
    # 1. 토큰 설정
    MY_ACCESS_TOKEN = main.fn_au10001()  # 접근 토큰 가져오기

    # 2. 데이터베이스 연결 및 테이블 생성
    cur, conn = DBconnect(create_table=True)
    if cur is None or conn is None:
        print("프로그램 종료: 데이터베이스 연결 실패")
        exit()

    # 3. 처리할 시장 및 거래소 구분 조합
    market_exchange_combinations = [
        {'mrkt_tp': '0', 'stex_tp': '1'},  # 코스피, KRX
        {'mrkt_tp': '0', 'stex_tp': '3'},  # 코스피, 통합
        {'mrkt_tp': '1', 'stex_tp': '1'},  # 코스닥, KRX
        {'mrkt_tp': '1', 'stex_tp': '3'},  # 코스닥, 통합
    ]

    # 4. 이미 처리된 조합 확인
    cur.execute("SELECT DISTINCT mrkt_tp, stex_tp, inds_cd FROM public.investor_data;")
    already_inserted = {(row[0], row[1], row[2]) for row in cur.fetchall()}
    print("이미 처리된 조합:", already_inserted)

    # 5. 각 조합에 대해 데이터 처리
    for combo in market_exchange_combinations:
        mrkt_tp = combo['mrkt_tp']
        stex_tp = combo['stex_tp']

        # 요청 데이터
        params = {
            'mrkt_tp': mrkt_tp,
            'amt_qty_tp': '0',  # 금액 기준
            'base_dt': None,  
            'stex_tp': stex_tp,
        }

        # 모든 데이터 가져오기
        df = fetch_all_data(
            token=MY_ACCESS_TOKEN,
            data=params,
            start_date='20230101',
            end_date=None,
            max_iterations=100
        )

        # 데이터베이스에 삽입
        if df is not None:
            # 유효한 inds_cd 리스트 추출
            expected_inds_cd_list = df['inds_cd'].unique().tolist()
            print(f"총 {len(df)} row 데이터를 삽입합니다. 업종 코드: {expected_inds_cd_list}")
            insert_to_db(
                df,
                expected_mrkt_tp=mrkt_tp,
                expected_stex_tp=stex_tp,
                expected_inds_cd_list=expected_inds_cd_list,
                batch_size=1000
            )

    # 6. 데이터베이스 연결 종료
    DBdisconnect()