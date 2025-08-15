package com.example.fivesense.service;

import com.theokanning.openai.completion.chat.ChatCompletionRequest;
import com.theokanning.openai.completion.chat.ChatMessage;
import com.theokanning.openai.service.OpenAiService;
import com.example.fivesense.model.ChatList;
import com.example.fivesense.repository.ChatMessageRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

@Service
public class ChatGPTService {

    private final OpenAiService openAiService;
    private final ChatMessageRepository chatMessageRepository;

    @Autowired
    public ChatGPTService(@Value("${openai.api.key}") String apiKey, 
                         ChatMessageRepository chatMessageRepository) {
        if (apiKey == null || apiKey.equals("your-api-key-here")) {
            throw new IllegalArgumentException("OpenAI API 키가 설정되지 않았습니다.");
        }
        this.openAiService = new OpenAiService(apiKey, Duration.ofSeconds(60));
        this.chatMessageRepository = chatMessageRepository;
    }

    public String getChatResponse(String userMessage, Long roomId) {
        try {
            List<com.theokanning.openai.completion.chat.ChatMessage> messages = new ArrayList<>();
            
            // 시스템 메시지 추가
            messages.add(new com.theokanning.openai.completion.chat.ChatMessage(
                "system", 
                "당신은 주식 투자 전문가입니다. 사용자의 질문에 대해 전문적이고 정확한 답변을 제공해주세요."
            ));
            
            // 이전 대화 내역 추가 (최근 10개 메시지)
            List<ChatList> previousMessages = chatMessageRepository.findRecentMessagesByRoomId(roomId, 10);
            for (ChatList msg : previousMessages) {
                String role = "USER".equals(msg.getType()) ? "user" : "assistant";
                messages.add(new com.theokanning.openai.completion.chat.ChatMessage(role, msg.getContent()));
            }
            
            // 현재 사용자 메시지 추가
            messages.add(new com.theokanning.openai.completion.chat.ChatMessage("user", userMessage));

            ChatCompletionRequest request = ChatCompletionRequest.builder()
                    .model("gpt-3.5-turbo")
                    .messages(messages)
                    .maxTokens(1000)
                    .temperature(0.7)
                    .build();

            return openAiService.createChatCompletion(request)
                    .getChoices().get(0).getMessage().getContent();
        } catch (Exception e) {
            throw new RuntimeException("ChatGPT API 호출 중 오류가 발생했습니다: " + e.getMessage());
        }
    }
    
    // 채팅방별 메시지 조회
    public List<ChatList> getChatHistory(Long roomId) {
        return chatMessageRepository.findByRoomIdOrderByTimestampAsc(roomId);
    }
    
    // 새로운 채팅방 생성 (첫 번째 메시지)
    public ChatList createNewChat(String userMessage) {
        // 새로운 roomId 생성 (현재 시간을 기반으로)
        Long newRoomId = System.currentTimeMillis();
        
        // 사용자 메시지 저장
        ChatList userMsg = new ChatList();
        userMsg.setContent(userMessage);
        userMsg.setType("USER");
        userMsg.setRoomId(newRoomId);
        chatMessageRepository.save(userMsg);
        
        // AI 응답 생성
        String aiResponse = getChatResponse(userMessage, newRoomId);
        
        // AI 메시지 저장
        ChatList aiMsg = new ChatList();
        aiMsg.setContent(aiResponse);
        aiMsg.setType("AI");
        aiMsg.setRoomId(newRoomId);
        chatMessageRepository.save(aiMsg);
        
        return aiMsg;
    }
    
    // 기존 채팅방에 메시지 추가
    public ChatList addMessageToChat(String userMessage, Long roomId) {
        // 사용자 메시지 저장
        ChatList userMsg = new ChatList();
        userMsg.setContent(userMessage);
        userMsg.setType("USER");
        userMsg.setRoomId(roomId);
        chatMessageRepository.save(userMsg);
        
        // AI 응답 생성
        String aiResponse = getChatResponse(userMessage, roomId);
        
        // AI 메시지 저장
        ChatList aiMsg = new ChatList();
        aiMsg.setContent(aiResponse);
        aiMsg.setType("AI");
        aiMsg.setRoomId(roomId);
        chatMessageRepository.save(aiMsg);
        
        return aiMsg;
    }
} 