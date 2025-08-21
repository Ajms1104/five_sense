# Five_sense
-AI를 이용한 주식 분석 시스템

~~~
Backend 실행
필요한 거 : 네이버 뉴스 API Key, OPEN AI API key, 키움증권 Rest API Key
Backend 파일명 : fivesense
./src/main/resources/Acpplication.properties - 파일에 키움증권, OPEN AI Key 넣기
./news.py - 파일에 네이버 뉴스 API key 넣기 및 실행 DB 연결까지 확인할 것
~~~

주의할 점
1. git push 할 때 open ai key는 지우고 올릴 것
: 보안이슈 때문에 강제로 푸시하면 key 사라짐
: 계속 재발급 받아야함 알고 싶지 않았음

~~~
Frontend 실행
필요한 거 : 프리텐다드 폰트, 크롬
Frontend 파일명 : frontend
./frontend 파일로 이동 후 터미널에서 npm start
~~~
주의할 점
1. 1920*1080에서 작업함 그래서 본인 크롬 주소칸에 돋보기 있으면 원래대로 돌리고 실행 할 것
2. 사람에 따라 모듈 설치가 필요할 수 도 있음
3. 폰트 없으면 절대 안됨

