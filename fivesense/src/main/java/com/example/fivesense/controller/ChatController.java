package com.example.fivesense.controller;

import com.example.fivesense.model.ChatList;
import com.example.fivesense.service.ChatGPTService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/chat")
@CrossOrigin(origins = "http://localhost:5173")
public class ChatController {

    private final ChatGPTService chatGPTService;

    @Autowired
    public ChatController(ChatGPTService chatGPTService) {
        this.chatGPTService = chatGPTService;
    }

    // 새로운 채팅 시작
    @PostMapping
    public ResponseEntity<?> sendMessage(@RequestBody Map<String, String> request) {
        try {
            System.out.println("=== 채팅 메시지 수신 ===");
            System.out.println("사용자 메시지: " + request.get("message"));
            
            String userMessage = request.get("message");
            if (userMessage == null || userMessage.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(Map.of("error", "메시지가 비어있습니다."));
            }

            // 새로운 채팅방 생성
            ChatList aiResponse = chatGPTService.createNewChat(userMessage);
            
            System.out.println("AI 응답 생성 완료: " + aiResponse.getContent());
            
            return ResponseEntity.ok(Map.of(
                "message", "메시지가 성공적으로 전송되었습니다.",
                "aiResponse", aiResponse.getContent(),
                "roomId", aiResponse.getRoomId()
            ));
            
        } catch (Exception e) {
            System.err.println("=== 채팅 메시지 처리 오류 ===");
            System.err.println("오류 메시지: " + e.getMessage());
            e.printStackTrace();
            return ResponseEntity.internalServerError().body(Map.of("error", "메시지 처리 중 오류가 발생했습니다: " + e.getMessage()));
        }
    }

    // 기존 채팅방에 메시지 추가
    @PostMapping("/{roomId}")
    public ResponseEntity<?> addMessageToRoom(
            @PathVariable Long roomId,
            @RequestBody Map<String, String> request) {
        try {
            System.out.println("=== 기존 채팅방 메시지 추가 ===");
            System.out.println("채팅방 ID: " + roomId);
            System.out.println("사용자 메시지: " + request.get("message"));
            
            String userMessage = request.get("message");
            if (userMessage == null || userMessage.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(Map.of("error", "메시지가 비어있습니다."));
            }

            // 기존 채팅방에 메시지 추가
            ChatList aiResponse = chatGPTService.addMessageToChat(userMessage, roomId);
            
            System.out.println("AI 응답 생성 완료: " + aiResponse.getContent());
            
            return ResponseEntity.ok(Map.of(
                "message", "메시지가 성공적으로 전송되었습니다.",
                "aiResponse", aiResponse.getContent(),
                "roomId", roomId
            ));
            
        } catch (Exception e) {
            System.err.println("=== 기존 채팅방 메시지 처리 오류 ===");
            System.err.println("오류 메시지: " + e.getMessage());
            e.printStackTrace();
            return ResponseEntity.internalServerError().body(Map.of("error", "메시지 처리 중 오류가 발생했습니다: " + e.getMessage()));
        }
    }

    // 채팅 기록 조회
    @GetMapping("/history")
    public ResponseEntity<List<ChatList>> getChatHistory() {
        try {
            System.out.println("=== 채팅 기록 조회 요청 ===");
            
            // 임시로 최근 채팅방의 메시지를 반환 (실제로는 사용자별로 구분해야 함)
            List<ChatList> chatHistory = chatGPTService.getChatHistory(System.currentTimeMillis());
            
            System.out.println("조회된 채팅 기록 개수: " + chatHistory.size());
            
            return ResponseEntity.ok(chatHistory);
            
        } catch (Exception e) {
            System.err.println("=== 채팅 기록 조회 오류 ===");
            System.err.println("오류 메시지: " + e.getMessage());
            e.printStackTrace();
            return ResponseEntity.internalServerError().build();
        }
    }

    // 특정 채팅방의 메시지 조회
    @GetMapping("/history/{roomId}")
    public ResponseEntity<List<ChatList>> getChatHistoryByRoom(@PathVariable Long roomId) {
        try {
            System.out.println("=== 특정 채팅방 기록 조회 ===");
            System.out.println("채팅방 ID: " + roomId);
            
            List<ChatList> chatHistory = chatGPTService.getChatHistory(roomId);
            
            System.out.println("조회된 채팅 기록 개수: " + chatHistory.size());
            
            return ResponseEntity.ok(chatHistory);
            
        } catch (Exception e) {
            System.err.println("=== 특정 채팅방 기록 조회 오류 ===");
            System.err.println("오류 메시지: " + e.getMessage());
            e.printStackTrace();
            return ResponseEntity.internalServerError().build();
        }
    }
} 