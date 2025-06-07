package com.example.fivesense.controller;

import com.example.fivesense.model.ChatMessage;
import com.example.fivesense.repository.ChatMessageRepository;
import com.example.fivesense.service.ChatGPTService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/chat")
public class ChatController {

    @Autowired
    private ChatMessageRepository chatMessageRepository;

    @Autowired
    private ChatGPTService chatGPTService;

    @PostMapping
    public ResponseEntity<?> handleChat(@RequestBody Map<String, String> request) {
        String userMessage = request.get("message");
        if (userMessage == null || userMessage.trim().isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("error", "메시지를 입력해주세요."));
        }
        
        try {
            // 사용자 메시지 저장
            ChatMessage userChatMessage = new ChatMessage();
            userChatMessage.setContent(userMessage);
            userChatMessage.setType("USER");
            chatMessageRepository.save(userChatMessage);

            // ChatGPT API 호출
            String aiResponse = chatGPTService.getChatResponse(userMessage);

            // AI 응답 저장
            ChatMessage aiChatMessage = new ChatMessage();
            aiChatMessage.setContent(aiResponse);
            aiChatMessage.setType("AI");
            chatMessageRepository.save(aiChatMessage);

            return ResponseEntity.ok(Map.of("response", aiResponse));
        } catch (IllegalArgumentException e) {
            // API 키 관련 에러
            return ResponseEntity.status(500).body(Map.of("error", "서버 설정 오류: " + e.getMessage()));
        } catch (RuntimeException e) {
            // ChatGPT API 호출 실패
            return ResponseEntity.status(500).body(Map.of("error", "AI 응답 생성 중 오류가 발생했습니다: " + e.getMessage()));
        } catch (Exception e) {
            // 기타 예상치 못한 에러
            return ResponseEntity.status(500).body(Map.of("error", "서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."));
        }
    }

    @GetMapping("/history")
    public ResponseEntity<?> getChatHistory() {
        try {
            List<ChatMessage> messages = chatMessageRepository.findAll();
            return ResponseEntity.ok(messages);
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of("error", "채팅 기록을 불러오는데 실패했습니다."));
        }
    }
} 