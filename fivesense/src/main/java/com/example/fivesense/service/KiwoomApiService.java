package com.example.fivesense.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.lang.NonNull;

import java.util.HashMap;
import java.util.Map;

import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.client.WebSocketClient;
import org.springframework.web.socket.client.standard.StandardWebSocketClient;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import org.springframework.web.socket.WebSocketHttpHeaders;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;

import java.net.URI;
import java.io.IOException;
import java.util.Arrays;
import java.util.List;
@Service
public class KiwoomApiService {

    private final WebClient webClient;
    private final SimpMessagingTemplate messagingTemplate;
    private final ObjectMapper objectMapper;
    private WebSocketSession socketSession;
    
    @Value("${kiwoom.api.host}")
    private String apiHost;
    
    @Value("${kiwoom.api.key}")
    private String apiKey;
    
    @Value("${kiwoom.api.secret}")
    private String apiSecret;
    
    @Value("${kiwoom.websocket.url}")
    private String websocketUrl;

    private String accessToken;
    
    public KiwoomApiService(SimpMessagingTemplate messagingTemplate) {
        this.messagingTemplate = messagingTemplate;
        this.objectMapper = new ObjectMapper();
        System.out.println("apiKey: " + apiKey);
        System.out.println("apiSecret: " + apiSecret);
        
        // REST API 클라이언트 설정
        this.webClient = WebClient.builder()
                .baseUrl("https://api.kiwoom.com")
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader("appkey", "b2K5-UsTjlm6ZzCoOpYXfoW7w-f9lIoiCyJPfWbOvjA")
                .defaultHeader("appsecret", "F9011bD31_BQEry1SOorhTUSGAj-mEOjrfjQZc4AD9A")
                .build();
                
        
        // 토큰 발급
        getAccessToken();
        
        // 웹소켓 연결 초기화
        initWebSocketConnection();
    }
    
    private void getAccessToken() {
        try {
            // 1. 요청 데이터 JSON 문자열 생성
            Map<String, String> tokenRequest = new HashMap<>();
            tokenRequest.put("appkey", "b2K5-UsTjlm6ZzCoOpYXfoW7w-f9lIoiCyJPfWbOvjA");
            tokenRequest.put("secretkey", "F9011bD31_BQEry1SOorhTUSGAj-mEOjrfjQZc4AD9A");

            // 2. API 호출
            Map<String, Object> response = webClient.post()
                    .uri("/oauth2/token")
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(tokenRequest)
                    .retrieve()
                    .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                    .block();

            // 3. 응답 처리
            if (response != null) {
                System.out.println("Token Response: " + response);
                
                if ("0".equals(String.valueOf(response.get("return_code")))) {
                    accessToken = (String) response.get("token");
                    System.out.println("Access token received: " + accessToken);
                    System.out.println("Token expires at: " + response.get("expires_dt"));
                } else {
                    System.err.println("Token request failed: " + response.get("return_msg"));
                }
            }
        } catch (Exception e) {
            System.err.println("Error getting access token: " + e.getMessage());
            e.printStackTrace();
        }
    }
    // 웹소켓 연결 초기화
    private void initWebSocketConnection() {
        try {
            WebSocketClient client = new StandardWebSocketClient();
            WebSocketHttpHeaders headers = new WebSocketHttpHeaders();
            
            WebSocketHandler handler = new TextWebSocketHandler() {
                @Override
                public void afterConnectionEstablished(@NonNull WebSocketSession session) {
                    socketSession = session;
                    try {
                        // 로그인 패킷 전송
                        Map<String, Object> loginMessage = new HashMap<>();
                        loginMessage.put("trnm", "LOGIN");
                        loginMessage.put("token", accessToken);
                        
                        System.out.println("실시간 시세 서버로 로그인 패킷을 전송합니다.");
                        session.sendMessage(new TextMessage(objectMapper.writeValueAsString(loginMessage)));
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                }
                
                @Override
                protected void handleTextMessage(@NonNull WebSocketSession session, @NonNull TextMessage message) {
                    try {
                        System.out.println("Received WebSocket message: " + message.getPayload());
                        Map<String, Object> response = objectMapper.readValue(message.getPayload(), 
                            new TypeReference<Map<String, Object>>() {});
                        
                        // PING 메시지 처리
                        if ("PING".equals(response.get("trnm"))) {
                            session.sendMessage(new TextMessage(message.getPayload()));
                            return;
                        }
                        
                        // 로그인 응답 처리
                        if ("LOGIN".equals(response.get("trnm"))) {
                            if (!"0".equals(String.valueOf(response.get("return_code")))) {
                                System.err.println("로그인 실패: " + response.get("return_msg"));
                                try {
                                    session.close();
                                } catch (IOException e) {
                                    e.printStackTrace();
                                }
                            } else {
                                System.out.println("로그인 성공");
                            }
                        }
                    } catch (Exception e) {
                        System.err.println("Error processing WebSocket message: " + e.getMessage());
                        e.printStackTrace();
                    }
                }
                
                @Override
                public void afterConnectionClosed(@NonNull WebSocketSession session, @NonNull CloseStatus status) {
                    socketSession = null;
                    initWebSocketConnection(); // 재연결 시도
                }
            };
            
            client.execute(handler, headers, URI.create("wss://api.kiwoom.com:10000/api/dostk/websocket")).get();
            
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
    

    // 주식 차트 조회
    public Map<String, Object> getDailyStockChart(String stockCode, String baseDate, String apiId) {
        return getDailyStockChart(stockCode, baseDate, apiId, null);
    }

    public Map<String, Object> getDailyStockChart(String stockCode, String baseDate, String apiId, String ticScope) {
        try {
            // 요청 데이터 JSON 문자열 생성
            Map<String, String> requestData = new HashMap<>();
            requestData.put("stk_cd", stockCode);
            requestData.put("upd_stkpc_tp", "1");


            if ("KA10080".equals(apiId)) {
                requestData.put("tic_scope", ticScope != null ? ticScope : "1");
            } else {
                // 다른 차트 타입의 경우 base_dt 추가
                requestData.put("base_dt", baseDate);
            }

            System.out.println("Request data: " + requestData);

            // API 호출
            Map<String, Object> response = webClient.post()
                    .uri("/api/dostk/chart")
                    .header("authorization", "Bearer " + accessToken)
                    .header("cont-yn", "N")
                    .header("next-key", "")
                    .header("api-id", apiId.toLowerCase())
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(requestData)
                    .retrieve()
                    .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                    .block();

            if (response != null) {
                System.out.println("Chart response: " + response);
                return response;
            }
        } catch (Exception e) {
            System.err.println("Error fetching chart: " + e.getMessage());
            e.printStackTrace();
        }
        return new HashMap<>();
    }

    // 당일 거래량 상위 종목 조회
    public Map<String, Object> getDailyTopVolumeStocks() {
        try {
            // 요청 데이터 JSON 문자열 생성
            Map<String, String> requestData = new HashMap<>();
            requestData.put("mrkt_tp", "000");      // 시장구분 (000: 전체)
            requestData.put("sort_tp", "1");        // 정렬구분 (1: 거래량)
            requestData.put("mang_stk_incls", "0"); // 관리종목 포함여부
            requestData.put("crd_tp", "0");         // 신용구분
            requestData.put("trde_qty_tp", "0");    // 거래량구분
            requestData.put("pric_tp", "0");        // 가격구분
            requestData.put("trde_prica_tp", "0");  // 거래대금구분
            requestData.put("mrkt_open_tp", "0");   // 시장구분
            requestData.put("stex_tp", "3");        // 증권구분

            // API 호출
            Map<String, Object> response = webClient.post()
                    .uri("/api/dostk/rkinfo")
                    .header("authorization", "Bearer " + accessToken)
                    .header("cont-yn", "N")
                    .header("next-key", "")
                    .header("api-id", "ka10030")
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(requestData)
                    .retrieve()
                    .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                    .block();
    
            if (response != null) {
                System.out.println("Top volume stocks response: " + response);
                return response;
            }
        } catch (Exception e) {
            System.err.println("Error fetching top volume stocks: " + e.getMessage());
            e.printStackTrace();
        }
        return new HashMap<>();
    }

} 