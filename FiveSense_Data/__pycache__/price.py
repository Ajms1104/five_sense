import requests
import json
import pandas as pd
import psycopg2
import main

#DB 연결
def DBconnect():
	global cur, conn
	try:
		conn = psycopg2.connect(host='localhost', user='postgres', password='1234', dbname='price')
		cur = conn.cursor()
		print("Database Connect Success")
		return cur, conn
	except Exception as err:
		print(str(err))
		

#DB 닫기
def DBdisconnect():
	try:
		conn.close()
		cur.close()
		print("DB Connect Close")
	except:
		print("Error: ", "Database Not Connectes.")
		
#DB 연결 시작
try:
	DBconnect()
	DBdisconnect()
except Exception as error:
	print(str(error))
	


#### 일별주가요청 ######

def fn_ka10086(token, data, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	host = 'https://mockapi.kiwoom.com' # 모의투자
	#host = 'https://api.kiwoom.com' # 실전투자
	endpoint = '/api/dostk/mrkcond'
	url =  host + endpoint

	# 2. header 데이터
	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # 컨텐츠타입
		'authorization': f'Bearer {token}', # 접근토큰
		'cont-yn': cont_yn, # 연속조회여부
		'next-key': next_key, # 연속조회키
		'api-id': 'ka10086', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	print('Code:', response.status_code)
	print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력
	if response.status_code == 200:
		res = response.json()['daly_stkpc']
		df = pd.DataFrame(res)
		print(df)
		df = df[::-1].reset_index(drop=True)
# 실행 구간
if __name__ == '__main__':
	# 1. 토큰 설정
	MY_ACCESS_TOKEN = main.fn_au10001() # 접근토큰

	# 2. 요청 데이터
	params = {
		'stk_cd': '005930', # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
		'qry_dt': '20250407', # 조회일자 YYYYMMDD
		'indc_tp': '0', # 표시구분 0:수량, 1:금액(백만원)
	}

	# 3. API 실행
	fn_ka10086(token=MY_ACCESS_TOKEN, data=params)

	# next-key, cont-yn 값이 있을 경우
	# fn_ka10086(token=MY_ACCESS_TOKEN, data=params, cont_yn='N', next_key='nextkey..')

