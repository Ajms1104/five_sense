package com.example.fivesense.controller;

import com.example.fivesense.model.ChatList;
import com.example.fivesense.service.ChatGPTService;
import com.example.fivesense.repository.ChatMessageRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/chat")
@CrossOrigin(origins = "http://localhost:5173")
public class ChatController {

    private final ChatGPTService chatGPTService;
    private final ChatMessageRepository chatMessageRepository;

    @Autowired
    public ChatController(ChatGPTService chatGPTService, ChatMessageRepository chatMessageRepository) {
        this.chatGPTService = chatGPTService;
        this.chatMessageRepository = chatMessageRepository;
    }

    // 새로운 채팅 시작
    @PostMapping("/new")
    public ResponseEntity<Map<String, Object>> startNewChat(@RequestBody Map<String, String> request) {
        Map<String, Object> response = new HashMap<>();
        
        try {
            String userMessage = request.get("message");
            if (userMessage == null || userMessage.trim().isEmpty()) {
                response.put("success", false);
                response.put("message", "메시지를 입력해주세요.");
                return ResponseEntity.badRequest().body(response);
            }

            ChatList aiResponse = chatGPTService.createNewChat(userMessage);
            
            response.put("success", true);
            response.put("message", "새로운 채팅이 시작되었습니다.");
            response.put("roomId", aiResponse.getRoomId());
            response.put("aiResponse", aiResponse.getContent());
            
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            response.put("success", false);
            response.put("message", "채팅 생성 중 오류가 발생했습니다: " + e.getMessage());
            return ResponseEntity.badRequest().body(response);
        }
    }

    // 기존 채팅방에 메시지 추가
    @PostMapping("/send")
    public ResponseEntity<Map<String, Object>> sendMessage(@RequestBody Map<String, Object> request) {
        Map<String, Object> response = new HashMap<>();
        
        try {
            String userMessage = (String) request.get("message");
            Long roomId = Long.valueOf(request.get("roomId").toString());
            
            if (userMessage == null || userMessage.trim().isEmpty()) {
                response.put("success", false);
                response.put("message", "메시지를 입력해주세요.");
                return ResponseEntity.badRequest().body(response);
            }

            ChatList aiResponse = chatGPTService.addMessageToChat(userMessage, roomId);
            
            response.put("success", true);
            response.put("message", "메시지가 전송되었습니다.");
            response.put("aiResponse", aiResponse.getContent());
            
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            response.put("success", false);
            response.put("message", "메시지 전송 중 오류가 발생했습니다: " + e.getMessage());
            return ResponseEntity.badRequest().body(response);
        }
    }

    // 채팅방 내역 조회
    @GetMapping("/history/{roomId}")
    public ResponseEntity<Map<String, Object>> getChatHistory(@PathVariable Long roomId) {
        Map<String, Object> response = new HashMap<>();
        
        try {
            List<ChatList> messages = chatGPTService.getChatHistory(roomId);
            
            response.put("success", true);
            response.put("messages", messages);
            response.put("roomId", roomId);
            
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            response.put("success", false);
            response.put("message", "채팅 내역 조회 중 오류가 발생했습니다: " + e.getMessage());
            return ResponseEntity.badRequest().body(response);
        }
    }

    // 채팅방 목록 조회
    @GetMapping("/rooms")
    public ResponseEntity<Map<String, Object>> getChatRooms() {
        Map<String, Object> response = new HashMap<>();
        
        try {
            List<Long> roomIds = chatMessageRepository.findAllRoomIds();
            
            response.put("success", true);
            response.put("rooms", roomIds);
            
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            response.put("success", false);
            response.put("message", "채팅방 목록 조회 중 오류가 발생했습니다: " + e.getMessage());
            return ResponseEntity.badRequest().body(response);
        }
    }

    // 채팅방 삭제
    @DeleteMapping("/room/{roomId}")
    public ResponseEntity<Map<String, Object>> deleteChatRoom(@PathVariable Long roomId) {
        Map<String, Object> response = new HashMap<>();
        
        try {
            List<ChatList> messages = chatMessageRepository.findByRoomIdOrderByTimestampAsc(roomId);
            chatMessageRepository.deleteAll(messages);
            
            response.put("success", true);
            response.put("message", "채팅방이 삭제되었습니다.");
            
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            response.put("success", false);
            response.put("message", "채팅방 삭제 중 오류가 발생했습니다: " + e.getMessage());
            return ResponseEntity.badRequest().body(response);
        }
    }
} 