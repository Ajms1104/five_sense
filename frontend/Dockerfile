# Node.js 18 기반 이미지 사용
FROM node:18

# 작업 디렉토리 설정
WORKDIR /app

# 모든 파일 복사
COPY . .

# Node.js와 npm 버전 확인
RUN node --version
RUN npm --version

# 의존성 설치 (개발 의존성 포함)
RUN npm ci

# 애플리케이션 빌드
RUN npm run build

# 개발 서버로 실행
EXPOSE 3000

# 개발 서버 시작
CMD ["npm", "run", "dev"]
