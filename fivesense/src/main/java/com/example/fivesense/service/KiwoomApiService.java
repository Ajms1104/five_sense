package com.example.fivesense.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct; // Spring Boot 3.x 이상에서는 jakarta 사용
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.lang.NonNull;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.WebSocketHttpHeaders;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.client.WebSocketClient;
import org.springframework.web.socket.client.standard.StandardWebSocketClient;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.net.URI;
import java.util.HashMap;
import java.util.Map;

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

    // 1. 생성자: 의존성 주입만 담당하도록 변경 (초기화 로직 제거)
    // WebClient.Builder를 주입받는 것이 Spring의 권장 방식입니다.
    public KiwoomApiService(SimpMessagingTemplate messagingTemplate, WebClient.Builder webClientBuilder) {
        this.messagingTemplate = messagingTemplate;
        this.objectMapper = new ObjectMapper();
        this.webClient = webClientBuilder.baseUrl("https://api.kiwoom.com")
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader("appkey", "IFZoKZtS4RIhUP7qd4DSzgiFJ5_zbzJvgVoRCbb7KtM")
                .defaultHeader("secretkey", "4lD4p6k5ehfmfx3hB6OIaYoQFiqA8DrM3nVG8ybNryg")
                .build();
    }

    // 2. 초기화 메서드: @PostConstruct 어노테이션을 사용하여 분리
    // 이 메서드는 모든 의존성 주입(@Value 포함)이 완료된 후에 실행됩니다.
    @PostConstruct
    public void initialize() {
        System.out.println("--- Initializing KiwoomApiService ---");
        System.out.println("API Key from @Value: " + apiKey);
        System.out.println("API Secret from @Value: " + apiSecret);

        getAccessToken();
        initWebSocketConnection();
        System.out.println("--- KiwoomApiService Initialized ---");
    }

    private void getAccessToken() {
        try {
            Map<String, String> tokenRequest = new HashMap<>();
            tokenRequest.put("grant_type", "client_credentials");
            tokenRequest.put("appkey", this.apiKey); // @Value로 주입된 apiKey 필드 사용
            tokenRequest.put("secretkey", this.apiSecret); // @Value로 주입된 apiSecret 필드 사용

            Map<String, Object> response = webClient.post()
                    .uri("/oauth2/token")
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(tokenRequest)
                    .retrieve()
                    .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                    .block();

            if (response != null) {
                System.out.println("Token Response: " + response);

                // <<-- 수정된 부분: 실제 로그에 찍힌 키 이름으로 변경 -->>
                // 성공 코드는 "return_code"
                if ("0".equals(String.valueOf(response.get("return_code")))) {
                    // 토큰 값은 "token"
                    accessToken = (String) response.get("token");
                    System.out.println("Access token received: " + accessToken);
                } else {
                    // 실패 메시지는 "return_msg"
                    System.err.println("Token request failed: " + response.get("return_msg"));
                }
                // <<-- /수정된 부분 -->>
            }
        } catch (Exception e) {
            System.err.println("Error getting access token: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private void initWebSocketConnection() {
        try {
            WebSocketClient client = new StandardWebSocketClient();
            WebSocketHttpHeaders headers = new WebSocketHttpHeaders();

            WebSocketHandler handler = new TextWebSocketHandler() {
                @Override
                public void afterConnectionEstablished(@NonNull WebSocketSession session) throws Exception {
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
                    Map<String, Object> loginMessage = new HashMap<>();
                    loginMessage.put("trnm", "LOGIN");
                    loginMessage.put("token", accessToken);
                    System.out.println("실시간 시세 서버로 로그인 패킷을 전송합니다. Token: " + accessToken);
                    session.sendMessage(new TextMessage(objectMapper.writeValueAsString(loginMessage)));
                }

                @Override
                protected void handleTextMessage(@NonNull WebSocketSession session, @NonNull TextMessage message) throws Exception {
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
                }

                @Override
                public void afterConnectionClosed(@NonNull WebSocketSession session, @NonNull CloseStatus status) {
                    socketSession = null;
                    // 재연결 로직은 필요에 따라 구현 (예: 5초 후 재시도)
                    // initWebSocketConnection(); 
                }
            };
            client.execute(handler, headers, URI.create(this.websocketUrl)).get();
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
            Map<String, String> requestData = new HashMap<>();
            requestData.put("stk_cd", stockCode);
            requestData.put("upd_stkpc_tp", "1");
            if ("KA10080".equals(apiId)) {
                requestData.put("tic_scope", ticScope != null ? ticScope : "1");
            } else {
                requestData.put("base_dt", baseDate);
            }
            System.out.println("Request data: " + requestData);
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
