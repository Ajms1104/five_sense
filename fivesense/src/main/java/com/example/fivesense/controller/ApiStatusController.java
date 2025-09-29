package com.example.fivesense.controller;

import com.example.fivesense.service.ApiRateLimitService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/status")
public class ApiStatusController {

    @Autowired
    private ApiRateLimitService rateLimitService;

    /**
     * API 요청 상태를 조회합니다.
     * 
     * @return API 상태 정보
     */
    @GetMapping("/rate-limit")
    public ResponseEntity<Map<String, Object>> getApiStatus() {
        Map<String, Object> status = new HashMap<>();
        
        status.put("queueSize", rateLimitService.getQueueSize());
        status.put("availablePermits", rateLimitService.getAvailablePermits());
        status.put("rateLimitPerSecond", 5.0);
        status.put("timestamp", System.currentTimeMillis());
        
        return ResponseEntity.ok(status);
    }
}
