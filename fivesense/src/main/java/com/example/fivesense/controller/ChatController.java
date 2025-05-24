package com.example.fivesense.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpEntity;
import org.springframework.http.MediaType;
import java.util.HashMap;
import java.util.Map;
import java.util.List;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "http://localhost:5173")
public class ChatController {

    @Value("${rasa.api.url}")
    private String rasaApiUrl;

    @Value("${rasa.api.key}")
    private String rasaApiKey;
    

    @PostMapping("/chat")
    public ResponseEntity<Map<String, String>> chat(@RequestBody Map<String, String> request) {
        
        try {
            String message = request.get("message");
            if (message == null || message.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(createErrorResponse("메시지를 입력해주세요."));
            }
            
            // Rasa API 요청 바디 설정
            Map<String, String> rasaRequest = new HashMap<>();
            rasaRequest.put("sender", "user");
            rasaRequest.put("message", message);
            
            // API 호출
            RestTemplate restTemplate = new RestTemplate();
            List<Map<String, Object>> response = restTemplate.postForObject(
                rasaApiUrl,
                rasaRequest,
                List.class
            );
            
            // Rasa 응답 처리
            if (response != null && !response.isEmpty()) {
                Map<String, Object> firstResponse = response.get(0);
                String text = (String) firstResponse.get("text");
                
                Map<String, String> result = new HashMap<>();
                result.put("response", text != null ? text : "죄송합니다. 응답을 처리할 수 없습니다.");
                return ResponseEntity.ok(result);
            }
            
            return ResponseEntity.ok(createErrorResponse("죄송합니다. 응답을 받지 못했습니다."));
                
        } catch (Exception e) {
            e.printStackTrace();
            return ResponseEntity.status(500)
                .body(createErrorResponse("챗봇 서버와 통신 중 오류가 발생했습니다: " + e.getMessage()));
        }
    }
    
    
    private Map<String, String> createErrorResponse(String message) {
        Map<String, String> response = new HashMap<>();
        response.put("response", message);
        return response;
    }
} 