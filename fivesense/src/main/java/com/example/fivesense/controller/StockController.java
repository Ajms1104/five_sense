package com.example.fivesense.controller;

import com.example.fivesense.service.KiwoomApiService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

@RestController
@RequestMapping("/api/stock")
public class StockController {

    private final KiwoomApiService kiwoomApiService;

    public StockController(KiwoomApiService kiwoomApiService) {
        this.kiwoomApiService = kiwoomApiService;
    }

    


    @PostMapping("/daily-chart/{stockCode}")
    public Map<String, Object> getDailyChart(
            @PathVariable String stockCode,
            @RequestBody Map<String, Object> requestData,
            @RequestParam(required = false, defaultValue = "KA10081") String apiId) {
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

} 