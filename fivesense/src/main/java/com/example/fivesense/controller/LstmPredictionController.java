package com.example.fivesense.controller;

import com.example.fivesense.model.LstmPrediction;
import com.example.fivesense.service.LstmPredictionService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/**
 * LSTM 예측 결과 조회 API Controller
 */
@RestController
@RequestMapping("/api/predictions/lstm")
@CrossOrigin(origins = "*")
public class LstmPredictionController {
    
    private final LstmPredictionService lstmPredictionService;
    
    public LstmPredictionController(LstmPredictionService lstmPredictionService) {
        this.lstmPredictionService = lstmPredictionService;
    }
    
    /**
     * 모든 LSTM 예측 결과 조회
     * GET /api/predictions/lstm
     */
    @GetMapping
    public ResponseEntity<List<LstmPrediction>> getAllPredictions() {
        List<LstmPrediction> predictions = lstmPredictionService.getAllPredictions();
        return ResponseEntity.ok(predictions);
    }
    
    /**
     * 최신 예측 날짜의 모든 예측 조회
     * GET /api/predictions/lstm/latest
     */
    @GetMapping("/latest")
    public ResponseEntity<List<LstmPrediction>> getLatestPredictions() {
        List<LstmPrediction> predictions = lstmPredictionService.getLatestPredictions();
        return ResponseEntity.ok(predictions);
    }
    
    /**
     * 최신 예측 날짜 조회
     * GET /api/predictions/lstm/latest-predict-date
     */
    @GetMapping("/latest-predict-date")
    public ResponseEntity<Map<String, LocalDate>> getLatestPredictDate() {
        return lstmPredictionService.getLatestPredictDate()
                .map(date -> ResponseEntity.ok(Map.of("latestPredictDate", date)))
                .orElse(ResponseEntity.notFound().build());
    }
    
    /**
     * 최신 목표 날짜 조회
     * GET /api/predictions/lstm/latest-target-date
     */
    @GetMapping("/latest-target-date")
    public ResponseEntity<Map<String, LocalDate>> getLatestTargetDate() {
        return lstmPredictionService.getLatestTargetDate()
                .map(date -> ResponseEntity.ok(Map.of("latestTargetDate", date)))
                .orElse(ResponseEntity.notFound().build());
    }
    
    /**
     * 특정 예측 날짜의 모든 예측 조회
     * GET /api/predictions/lstm/predict-date/{date}
     */
    @GetMapping("/predict-date/{date}")
    public ResponseEntity<List<LstmPrediction>> getPredictionsByPredictDate(
            @PathVariable @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date) {
        List<LstmPrediction> predictions = lstmPredictionService.getPredictionsByPredictDate(date);
        return ResponseEntity.ok(predictions);
    }
    
    /**
     * 특정 목표 날짜의 모든 예측 조회
     * GET /api/predictions/lstm/target-date/{date}
     */
    @GetMapping("/target-date/{date}")
    public ResponseEntity<List<LstmPrediction>> getPredictionsByTargetDate(
            @PathVariable @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date) {
        List<LstmPrediction> predictions = lstmPredictionService.getPredictionsByTargetDate(date);
        return ResponseEntity.ok(predictions);
    }
    
    /**
     * 예측 날짜 기간의 예측 조회
     * GET /api/predictions/lstm/predict-date-range?startDate=2021-01-01&endDate=2021-12-31
     */
    @GetMapping("/predict-date-range")
    public ResponseEntity<List<LstmPrediction>> getPredictionsByPredictDateRange(
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate startDate,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate endDate) {
        List<LstmPrediction> predictions = lstmPredictionService.getPredictionsByPredictDateRange(startDate, endDate);
        return ResponseEntity.ok(predictions);
    }
    
    /**
     * 목표 날짜 기간의 예측 조회
     * GET /api/predictions/lstm/target-date-range?startDate=2021-01-01&endDate=2021-12-31
     */
    @GetMapping("/target-date-range")
    public ResponseEntity<List<LstmPrediction>> getPredictionsByTargetDateRange(
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate startDate,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate endDate) {
        List<LstmPrediction> predictions = lstmPredictionService.getPredictionsByTargetDateRange(startDate, endDate);
        return ResponseEntity.ok(predictions);
    }
    
    /**
     * 특정 종목의 모든 예측 조회
     * GET /api/predictions/lstm/stock/{stockCode}
     */
    @GetMapping("/stock/{stockCode}")
    public ResponseEntity<List<LstmPrediction>> getPredictionsByStockCode(
            @PathVariable String stockCode) {
        List<LstmPrediction> predictions = lstmPredictionService.getPredictionsByStockCode(stockCode);
        return ResponseEntity.ok(predictions);
    }
    
    /**
     * 특정 종목의 최신 예측 조회
     * GET /api/predictions/lstm/stock/{stockCode}/latest
     */
    @GetMapping("/stock/{stockCode}/latest")
    public ResponseEntity<LstmPrediction> getLatestPredictionByStockCode(
            @PathVariable String stockCode) {
        return lstmPredictionService.getLatestPredictionByStockCode(stockCode)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }
    
    /**
     * 특정 종목의 특정 예측 날짜 예측 조회
     * GET /api/predictions/lstm/stock/{stockCode}/predict-date/{date}
     */
    @GetMapping("/stock/{stockCode}/predict-date/{date}")
    public ResponseEntity<List<LstmPrediction>> getPredictionsByStockCodeAndPredictDate(
            @PathVariable String stockCode,
            @PathVariable @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date) {
        List<LstmPrediction> predictions = lstmPredictionService.getPredictionsByStockCodeAndPredictDate(stockCode, date);
        return ResponseEntity.ok(predictions);
    }
    
    /**
     * 특정 종목의 특정 목표 날짜 예측 조회
     * GET /api/predictions/lstm/stock/{stockCode}/target-date/{date}
     */
    @GetMapping("/stock/{stockCode}/target-date/{date}")
    public ResponseEntity<List<LstmPrediction>> getPredictionsByStockCodeAndTargetDate(
            @PathVariable String stockCode,
            @PathVariable @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date) {
        List<LstmPrediction> predictions = lstmPredictionService.getPredictionsByStockCodeAndTargetDate(stockCode, date);
        return ResponseEntity.ok(predictions);
    }
    
    /**
     * 특정 종목의 특정 예측/목표 날짜 예측 조회
     * GET /api/predictions/lstm/stock/{stockCode}/predict-date/{predictDate}/target-date/{targetDate}
     */
    @GetMapping("/stock/{stockCode}/predict-date/{predictDate}/target-date/{targetDate}")
    public ResponseEntity<LstmPrediction> getPrediction(
            @PathVariable String stockCode,
            @PathVariable @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate predictDate,
            @PathVariable @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate targetDate) {
        return lstmPredictionService.getPrediction(stockCode, predictDate, targetDate)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }
    
    /**
     * 특정 종목의 예측 날짜 기간 예측 조회
     * GET /api/predictions/lstm/stock/{stockCode}/predict-date-range?startDate=2021-01-01&endDate=2021-12-31
     */
    @GetMapping("/stock/{stockCode}/predict-date-range")
    public ResponseEntity<List<LstmPrediction>> getPredictionsByStockCodeAndPredictDateRange(
            @PathVariable String stockCode,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate startDate,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate endDate) {
        List<LstmPrediction> predictions = lstmPredictionService.getPredictionsByStockCodeAndPredictDateRange(
                stockCode, startDate, endDate);
        return ResponseEntity.ok(predictions);
    }
    
    /**
     * 모든 종목 코드 조회
     * GET /api/predictions/lstm/stocks
     */
    @GetMapping("/stocks")
    public ResponseEntity<List<String>> getAllStockCodes() {
        List<String> stockCodes = lstmPredictionService.getAllStockCodes();
        return ResponseEntity.ok(stockCodes);
    }
    
    /**
     * 종목명으로 검색
     * GET /api/predictions/lstm/search?stockName=삼성
     */
    @GetMapping("/search")
    public ResponseEntity<List<LstmPrediction>> searchByStockName(
            @RequestParam String stockName) {
        List<LstmPrediction> predictions = lstmPredictionService.searchByStockName(stockName);
        return ResponseEntity.ok(predictions);
    }
    
    /**
     * 예상 변화율 기준 상위 조회
     * GET /api/predictions/lstm/top-by-change?predictDate=2021-09-24
     */
    @GetMapping("/top-by-change")
    public ResponseEntity<List<LstmPrediction>> getTopByExpectedChange(
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate predictDate) {
        List<LstmPrediction> predictions = lstmPredictionService.getTopByExpectedChange(predictDate);
        return ResponseEntity.ok(predictions);
    }
}

