package com.example.fivesense.service;

import com.example.fivesense.model.LstmPrediction;
import com.example.fivesense.repository.LstmPredictionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@Service
@Transactional(readOnly = true)
public class LstmPredictionService {
    
    private final LstmPredictionRepository lstmPredictionRepository;
    
    public LstmPredictionService(LstmPredictionRepository lstmPredictionRepository) {
        this.lstmPredictionRepository = lstmPredictionRepository;
    }
    
    /**
     * 모든 LSTM 예측 결과 조회
     */
    public List<LstmPrediction> getAllPredictions() {
        return lstmPredictionRepository.findAll();
    }
    
    /**
     * 특정 예측 날짜의 모든 예측 조회
     */
    public List<LstmPrediction> getPredictionsByPredictDate(LocalDate predictDate) {
        return lstmPredictionRepository.findByPredictDate(predictDate);
    }
    
    /**
     * 특정 목표 날짜의 모든 예측 조회
     */
    public List<LstmPrediction> getPredictionsByTargetDate(LocalDate targetDate) {
        return lstmPredictionRepository.findByTargetDate(targetDate);
    }
    
    /**
     * 특정 종목의 모든 예측 조회
     */
    public List<LstmPrediction> getPredictionsByStockCode(String stockCode) {
        return lstmPredictionRepository.findByStockCode(stockCode);
    }
    
    /**
     * 특정 종목의 특정 예측 날짜 예측 조회
     */
    public List<LstmPrediction> getPredictionsByStockCodeAndPredictDate(String stockCode, LocalDate predictDate) {
        return lstmPredictionRepository.findByStockCodeAndPredictDate(stockCode, predictDate);
    }
    
    /**
     * 특정 종목의 특정 목표 날짜 예측 조회
     */
    public List<LstmPrediction> getPredictionsByStockCodeAndTargetDate(String stockCode, LocalDate targetDate) {
        return lstmPredictionRepository.findByStockCodeAndTargetDate(stockCode, targetDate);
    }
    
    /**
     * 특정 종목의 특정 예측/목표 날짜 예측 조회
     */
    public Optional<LstmPrediction> getPrediction(String stockCode, LocalDate predictDate, LocalDate targetDate) {
        return lstmPredictionRepository.findByStockCodeAndPredictDateAndTargetDate(stockCode, predictDate, targetDate);
    }
    
    /**
     * 예측 날짜 기간의 예측 조회
     */
    public List<LstmPrediction> getPredictionsByPredictDateRange(LocalDate startDate, LocalDate endDate) {
        return lstmPredictionRepository.findByPredictDateBetween(startDate, endDate);
    }
    
    /**
     * 목표 날짜 기간의 예측 조회
     */
    public List<LstmPrediction> getPredictionsByTargetDateRange(LocalDate startDate, LocalDate endDate) {
        return lstmPredictionRepository.findByTargetDateBetween(startDate, endDate);
    }
    
    /**
     * 특정 종목의 예측 날짜 기간 예측 조회
     */
    public List<LstmPrediction> getPredictionsByStockCodeAndPredictDateRange(
            String stockCode, LocalDate startDate, LocalDate endDate) {
        return lstmPredictionRepository.findByStockCodeAndPredictDateBetween(stockCode, startDate, endDate);
    }
    
    /**
     * 최신 예측 날짜 조회
     */
    public Optional<LocalDate> getLatestPredictDate() {
        return lstmPredictionRepository.findLatestPredictDate();
    }
    
    /**
     * 최신 목표 날짜 조회
     */
    public Optional<LocalDate> getLatestTargetDate() {
        return lstmPredictionRepository.findLatestTargetDate();
    }
    
    /**
     * 최신 예측 날짜의 모든 예측 조회
     */
    public List<LstmPrediction> getLatestPredictions() {
        return lstmPredictionRepository.findLatestPredictions();
    }
    
    /**
     * 특정 종목의 최신 예측 조회
     */
    public Optional<LstmPrediction> getLatestPredictionByStockCode(String stockCode) {
        return lstmPredictionRepository.findLatestByStockCode(stockCode);
    }
    
    /**
     * 모든 종목 코드 조회
     */
    public List<String> getAllStockCodes() {
        return lstmPredictionRepository.findAllStockCodes();
    }
    
    /**
     * 종목명으로 검색
     */
    public List<LstmPrediction> searchByStockName(String stockName) {
        return lstmPredictionRepository.findByStockNameContainingIgnoreCase(stockName);
    }
    
    /**
     * 예상 변화율 기준 상위 조회
     */
    public List<LstmPrediction> getTopByExpectedChange(LocalDate predictDate) {
        return lstmPredictionRepository.findTopByExpectedChange(predictDate);
    }
}

