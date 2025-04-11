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

    


    @GetMapping("/daily-chart/{stockCode}")
    public Map<String, Object> getDailyChart(
            @PathVariable String stockCode,
            @RequestParam(required = false) String baseDate) {
        if (baseDate == null) {
            // 기본값으로 오늘 날짜 사용
            baseDate = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
        }
        return kiwoomApiService.getDailyStockChart(stockCode, baseDate);
    }

} 