package com.example.fivesense.controller;

import com.example.fivesense.service.KiwoomApiService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.List;
import java.util.ArrayList;
import java.util.HashMap;

@RestController
@RequestMapping("/api/stock")
@CrossOrigin(origins = "http://localhost:5173")

public class StockController {

    private final KiwoomApiService kiwoomApiService;

    public StockController(KiwoomApiService kiwoomApiService) {
        this.kiwoomApiService = kiwoomApiService;
    }

    @PostMapping("/daily-chart/{stockCode}")
    public Map<String, Object> getDailyChart(
            @PathVariable String stockCode,
            @RequestBody Map<String, Object> requestData,
            @RequestParam(value = "apiId", required = false, defaultValue = "KA10081") String apiId) {
        System.out.println("차트 데이터 요청: " + stockCode + ", apiId: " + apiId + ", requestData: " + requestData);
        String baseDate = requestData.containsKey("base_dt") ? (String) requestData.get("base_dt") : null;
        if (baseDate == null) {
            baseDate = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
        }
        
        // 분봉 차트인 경우 tic_scope 파라미터 추가
        if ("KA10080".equals(apiId) && requestData.containsKey("tic_scope")) {
            return kiwoomApiService.getDailyStockChart(stockCode, baseDate, apiId, (String) requestData.get("tic_scope"));
        }
        
        return kiwoomApiService.getDailyStockChart(stockCode, baseDate, apiId);
    }

    @GetMapping("/top-volume")
    public Map<String, Object> getTopVolumeStocks() {
        return kiwoomApiService.getDailyTopVolumeStocks();
    }

@GetMapping("/news")
public List<Map<String, Object>> getLatestNews(@RequestParam(value = "page", defaultValue = "1") int page) {
        System.out.println("=== /news 엔드포인트 호출됨 ===");
        System.out.println("페이지 번호: " + page);

        int pageSize = 4;
        int offset = (page - 1) * pageSize;
        List<Map<String, Object>> newsList = new ArrayList<>();

        System.out.println("데이터베이스 연결 시도 중...");
        try (Connection conn = DriverManager.getConnection(
                "jdbc:postgresql://localhost:5432/fivesense", "postgres", "1234")) {
            System.out.println("데이터베이스 연결 성공!");

            PreparedStatement stmt = conn.prepareStatement(
                "SELECT title, link FROM company_news ORDER BY pub_date DESC LIMIT 40 OFFSET 0");
            System.out.println("SQL 쿼리 실행 중...");

            ResultSet rs = stmt.executeQuery();
            System.out.println("쿼리 실행 완료, 결과 처리 중...");

            int idx = 0;
            while (rs.next() && newsList.size() < 40) {
                if (idx >= offset && newsList.size() < offset + pageSize) {
                    Map<String, Object> news = new HashMap<>();
                    news.put("title", rs.getString("title"));
                    news.put("link", rs.getString("link"));
                    newsList.add(news);
                }
                idx++;
            }
        } catch (Exception e) {
            System.err.println("=== /news 엔드포인트 오류 발생 ===");
            System.err.println("오류 메시지: " + e.getMessage());
            e.printStackTrace();
        }
        return newsList;
    }

}