# 1단계: 빌드 단계
# Gradle 래퍼와 소스 코드를 빌드할 환경을 설정합니다.
# 이 단계의 이름을 'builder'로 지정합니다.
FROM eclipse-temurin:21-jdk-alpine AS builder


# 작업 디렉토리 설정
WORKDIR /app

# Gradle 래퍼와 설정 파일 복사
COPY gradlew .
COPY gradle gradle
COPY build.gradle .
COPY settings.gradle .

# 줄바꿈 문자 변환 및 실행 권한 부여
RUN dos2unix gradlew && chmod +x gradlew

# 의존성 다운로드 (레이어 캐싱을 위해)
RUN ./gradlew dependencies --no-daemon

# 소스 코드 복사
COPY src src

# 애플리케이션 빌드
RUN ./gradlew build -x test --no-daemon

# 2단계: 실행 단계
# 최종 애플리케이션을 실행할 가벼운 환경을 설정합니다.
FROM openjdk:21-jdk-slim

# 작업 디렉토리 설정
WORKDIR /app

# 빌드된 JAR 파일 복사
# 'builder'라는 이름의 빌드 단계에서 JAR 파일을 복사해옵니다.
COPY --from=builder /app/build/libs/*.jar /app/app.jar

# 포트 노출
EXPOSE 8080

# 애플리케이션 실행
ENTRYPOINT ["java", "-jar", "app.jar"]
