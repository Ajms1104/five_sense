package com.example.fivesense.controller;

import com.example.fivesense.service.KiwoomApiService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/stock")
public class StockController {

    private final KiwoomApiService kiwoomApiService;

    public StockController(KiwoomApiService kiwoomApiService) {
        this.kiwoomApiService = kiwoomApiService;
    }

    @GetMapping("/price/{stockCode}")
    public ResponseEntity<Map<String, Object>> getStockPrice(
            @PathVariable String stockCode,
            @RequestParam String trId) {
        Map<String, Object> priceData = kiwoomApiService.getStockPrice(stockCode, trId);
        return ResponseEntity.ok(priceData);
    }
    
    @PostMapping("/subscribe/{stockCode}")
    public ResponseEntity<String> subscribeStock(
            @PathVariable String stockCode,
            @RequestBody Map<String, String> request) {
        String trId = request.get("trId");
        kiwoomApiService.subscribeToStock(stockCode, trId);
        return ResponseEntity.ok("Subscribed to " + stockCode);
    }
} 