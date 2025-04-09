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
        
        
        // REST API 클라이언트 설정
        this.webClient = WebClient.builder()
                .baseUrl("https://api.kiwoom.com")
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader("appkey", apiKey)//apikey 값 가져오기(현재  application.properties에 있는 값을 못가져와서 뒷부분에 값을 하드코딩해야함함)
                .defaultHeader("appsecret", apiSecret)//apiSecret 값 가져오기
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
            tokenRequest.put("grant_type", "client_credentials");
            tokenRequest.put("appkey", apiKey);//apikey 값 가져오기(현재  application.properties에 있는 값을 못가져와서 뒷부분에 값을 하드코딩해야함함)
            tokenRequest.put("secretkey", apiSecret);

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
    
    // 주식 시세 조회
    public Map<String, Object> getStockPrice(String stockCode, String trId) {
        System.out.println("Fetching stock price for code: " + stockCode + " with TR ID: " + trId);
        try {
            Map<String, Object> result = webClient.get()
                    .uri("/uapi/domestic-stock/v1/quotations/inquire-price?fid_cond_mrkt_div_code=J&fid_input_iscd={stockCode}",
                            stockCode)
                    .header("tr_id", trId)
                    .retrieve()
                    .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                    .block();
            System.out.println("Stock price response: " + result);
            return result;
        } catch (Exception e) {
            System.err.println("Error fetching stock price: " + e.getMessage());
            e.printStackTrace();
            return new HashMap<>();
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
                                
                                // 실시간 시세 등록
                                Map<String, Object> registerMessage = new HashMap<>();
                                registerMessage.put("trnm", "REG");
                                registerMessage.put("grp_no", "1");
                                registerMessage.put("refresh", "1");
                                
                                Map<String, Object> data = new HashMap<>();
                                data.put("item", Arrays.asList("005930")); // 삼성전자
                                data.put("type", Arrays.asList("0B")); // 실시간 항목
                                
                                registerMessage.put("data", Arrays.asList(data));
                                
                                session.sendMessage(new TextMessage(objectMapper.writeValueAsString(registerMessage)));
                            }
                        }
                        // 실시간 시세 데이터 처리
                        else if ("REAL".equals(response.get("trnm"))) {
                            List<Map<String, Object>> dataList = (List<Map<String, Object>>) response.get("data");
                            if (dataList != null && !dataList.isEmpty()) {
                                Map<String, Object> values = (Map<String, Object>) dataList.get(0).get("values");
                                
                                Map<String, Object> output = new HashMap<>();
                                output.put("현재가", values.get("20"));  // 현재가
                                output.put("거래량", values.get("13"));  // 거래량
                                output.put("시가", values.get("16"));    // 시가
                                output.put("고가", values.get("17"));    // 고가
                                output.put("저가", values.get("18"));    // 저가
                                output.put("전일대비", values.get("10")); // 전일대비
                                output.put("등락률", values.get("12"));   // 등락률
                                
                                Map<String, Object> chartData = new HashMap<>();
                                chartData.put("output", output);
                                
                                String stockCode = (String) dataList.get(0).get("item");
                                messagingTemplate.convertAndSend("/topic/stock/" + stockCode, chartData);
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
    
    // 특정 종목 실시간 시세 구독
    public void subscribeToStock(String stockCode, String trId) {
        if (socketSession != null && socketSession.isOpen()) {
            try {
                Map<String, Object> subscribeMessage = new HashMap<>();
                subscribeMessage.put("header", Map.of(
                    "tr_id", trId,
                    "tr_type", "1"
                ));
                subscribeMessage.put("body", Map.of(
                    "mksc_shrn_iscd", stockCode
                ));
                
                socketSession.sendMessage(new TextMessage(objectMapper.writeValueAsString(subscribeMessage)));
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }
} 