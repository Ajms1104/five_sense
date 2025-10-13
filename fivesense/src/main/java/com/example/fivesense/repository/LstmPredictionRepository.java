package com.example.fivesense.repository;

import com.example.fivesense.model.LstmPrediction;
import com.example.fivesense.model.LstmPredictionId;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@Repository
public interface LstmPredictionRepository extends JpaRepository<LstmPrediction, LstmPredictionId> {
    
    // 특정 예측 날짜의 모든 예측 조회
    List<LstmPrediction> findByPredictDate(LocalDate predictDate);
    
    // 특정 목표 날짜의 모든 예측 조회
    List<LstmPrediction> findByTargetDate(LocalDate targetDate);
    
    // 특정 종목 코드의 모든 예측 조회
    List<LstmPrediction> findByStockCode(String stockCode);
    
    // 특정 종목의 특정 예측 날짜 예측 조회
    List<LstmPrediction> findByStockCodeAndPredictDate(String stockCode, LocalDate predictDate);
    
    // 특정 종목의 특정 목표 날짜 예측 조회
    List<LstmPrediction> findByStockCodeAndTargetDate(String stockCode, LocalDate targetDate);
    
    // 특정 종목의 특정 예측/목표 날짜 예측 조회
    Optional<LstmPrediction> findByStockCodeAndPredictDateAndTargetDate(
        String stockCode, LocalDate predictDate, LocalDate targetDate);
    
    // 예측 날짜 기간의 예측 조회
    List<LstmPrediction> findByPredictDateBetween(LocalDate startDate, LocalDate endDate);
    
    // 목표 날짜 기간의 예측 조회
    List<LstmPrediction> findByTargetDateBetween(LocalDate startDate, LocalDate endDate);
    
    // 특정 종목의 예측 날짜 기간 예측 조회
    List<LstmPrediction> findByStockCodeAndPredictDateBetween(
        String stockCode, LocalDate startDate, LocalDate endDate);
    
    // 최신 예측 날짜 조회
    @Query("SELECT MAX(l.predictDate) FROM LstmPrediction l")
    Optional<LocalDate> findLatestPredictDate();
    
    // 최신 목표 날짜 조회
    @Query("SELECT MAX(l.targetDate) FROM LstmPrediction l")
    Optional<LocalDate> findLatestTargetDate();
    
    // 최신 예측 날짜의 모든 예측 조회
    @Query("SELECT l FROM LstmPrediction l WHERE l.predictDate = (SELECT MAX(l2.predictDate) FROM LstmPrediction l2)")
    List<LstmPrediction> findLatestPredictions();
    
    // 특정 종목의 최신 예측 조회
    @Query("SELECT l FROM LstmPrediction l WHERE l.stockCode = :stockCode " +
           "AND l.predictDate = (SELECT MAX(l2.predictDate) FROM LstmPrediction l2 WHERE l2.stockCode = :stockCode)")
    Optional<LstmPrediction> findLatestByStockCode(@Param("stockCode") String stockCode);
    
    // 모든 종목 코드 조회
    @Query("SELECT DISTINCT l.stockCode FROM LstmPrediction l ORDER BY l.stockCode")
    List<String> findAllStockCodes();
    
    // 종목명으로 검색
    List<LstmPrediction> findByStockNameContainingIgnoreCase(String stockName);
    
    // 예상 변화율 기준 상위 N개 조회
    @Query("SELECT l FROM LstmPrediction l WHERE l.predictDate = :predictDate ORDER BY l.expectedChange DESC")
    List<LstmPrediction> findTopByExpectedChange(@Param("predictDate") LocalDate predictDate);
}

