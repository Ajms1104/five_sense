package com.example.fivesense.config; // 학생분의 패키지 경로에 맞게 수정했습니다.

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class CorsConfig implements WebMvcConfigurer {

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**") // 모든 경로(/**)에 대해 CORS 설정을 적용합니다.
                .allowedOrigins("http://localhost:5173") // React 개발 서버 주소
                .allowedMethods("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS") // 허용할 HTTP 메서드 종류를 명시합니다.
                .allowedHeaders("*") // 모든 종류의 HTTP 헤더를 허용합니다.
                .allowCredentials(true) // 자격 증명(쿠키 등) 정보의 전송을 허용합니다.
                .maxAge(3600); // Pre-flight 요청의 결과를 캐싱할 시간(초)을 설정합니다.
    }
}
