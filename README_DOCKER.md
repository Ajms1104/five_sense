# FiveSense Docker 실행 가이드

## 🐳 사전 요구사항

1. **Docker Desktop** 설치 및 실행
   - [Docker Desktop 다운로드](https://www.docker.com/products/docker-desktop/)

## 🚀 빠른 시작

### Windows 사용자
```cmd
docker-run.bat
```

### 수동 실행
```cmd
docker-compose up --build -d
```

## 📊 서비스 구성

- **프론트엔드**: http://localhost:3000 (React)
- **백엔드 API**: http://localhost:8080 (Spring Boot)
- **데이터베이스**: localhost:5432 (PostgreSQL)

## 📝 주요 명령어

```cmd
# 서비스 시작
docker-compose up -d

# 서비스 중지
docker-compose down

# 로그 확인
docker-compose logs -f

# 서비스 상태 확인
docker-compose ps

# 특정 서비스 재시작
docker-compose restart backend
```

## 🔍 문제 해결

### 포트 충돌 시
```cmd
# 사용 중인 포트 확인
netstat -an | findstr :8080
netstat -an | findstr :5173

# 충돌하는 프로세스 종료 후 재시작
docker-compose down
docker-compose up -d
```

### 빌드 실패 시
```cmd
# 캐시 없이 재빌드
docker-compose build --no-cache
```

## 📁 생성된 파일

- `docker-compose.yml` - 메인 설정 파일
- `fivesense/Dockerfile` - 백엔드 Docker 설정
- `frontend/Dockerfile` - 프론트엔드 Docker 설정
- `.dockerignore` - 빌드 제외 파일 목록
- `docker-run.bat` - Windows 실행 스크립트
