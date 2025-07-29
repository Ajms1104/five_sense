package com.example.fivesense.service;

import com.theokanning.openai.completion.chat.ChatCompletionRequest;
import com.theokanning.openai.completion.chat.ChatMessage;
import com.theokanning.openai.completion.chat.ChatMessageRole;
import com.theokanning.openai.service.OpenAiService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

@Service
public class ChatGPTService {

    private final OpenAiService openAiService;

    public ChatGPTService(@Value("${openai.api.key}") String apiKey) {
        if (apiKey == null || apiKey.equals("your-api-key-here")) {
            throw new IllegalArgumentException("OpenAI API 키가 설정되지 않았습니다.");
        }
        this.openAiService = new OpenAiService(apiKey, Duration.ofSeconds(60));
    }

    public String getChatResponse(String userMessage) {
        try {
            List<ChatMessage> messages = new ArrayList<>();
            messages.add(new ChatMessage("system", 
                "당신은 주식 투자 전문가입니다. 사용자의 질문에 대해 전문적이고 정확한 답변을 제공해주세요."));
            messages.add(new ChatMessage("user", userMessage));

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
} 