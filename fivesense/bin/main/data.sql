-- 테스트용 사용자 데이터 삽입
INSERT INTO users (accountid, password, name, email) 
VALUES ('testuser', 'password123', '테스트 사용자', 'test@example.com')
ON CONFLICT (accountid) DO NOTHING; 