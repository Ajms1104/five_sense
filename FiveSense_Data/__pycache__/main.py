import requests
import json
import os
from dotenv import load_dotenv

# .env 파일에서 APP_KEY, APP_SECRET 불러오기
load_dotenv()
app_key = os.getenv("KIWOOM_APP_KEY")
app_secret = os.getenv("KIWOOM_SECRET")


#### 접근토큰 발급코드 #######

def fn_au10001():  # data 인자 제거
    # 1. 요청 데이터
    params = {
        'grant_type': 'client_credentials',  # grant_type
        'appkey': app_key,  # 앱키
        'secretkey': app_secret,  # 시크릿키
    }

    # 1. 요청할 API URL
    host = 'https://mockapi.kiwoom.com'  # 모의투자
    # host = 'https://api.kiwoom.com' # 실전투자
    endpoint = '/oauth2/token'
    url = host + endpoint

    # 2. header 데이터
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',  # 컨텐츠타입
    }

    # 3. http POST 요청
    response = requests.post(url, headers=headers, json=params) # params로 변경

    # 4. 응답 상태 코드 확인 및 데이터 처리
    if response.status_code == 200:
        try:
            response_json = response.json()  # JSON 응답을 파싱
            token = response_json['token']  # 'token' 필드에서 토큰 추출
            return token
        except (KeyError, json.JSONDecodeError) as e:
            print(f"토큰 추출 실패: {e}")
            print(f"응답 내용: {response.text}")  # 디버깅을 위해 응답 내용 출력
            return None
    else:
        print(f"API 요청 실패: 상태 코드 {response.status_code}")
        print(f"응답 내용: {response.text}")  # 디버깅을 위해 응답 내용 출력
        return None

# (선택 사항) main.py가 직접 실행될 때 토큰을 출력하도록 할 수 있습니다.
if __name__ == '__main__':
    token = fn_au10001()
    if token:
        print(token)
    else:
        print("토큰 발급 실패")