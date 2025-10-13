package com.example.fivesense.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * LSTM 모델의 예측 결과를 저장하는 Entity
 * 실제 테이블 구조에 맞춤: stock_code, stock_name, predict_date, target_date, latest_close, predicted_close, expected_change
 */
@Entity
@Table(name = "lstm_predictions", 
       indexes = {
           @Index(name = "idx_lstm_predict_date", columnList = "predict_date"),
           @Index(name = "idx_lstm_target_date", columnList = "target_date"),
           @Index(name = "idx_lstm_stock_code", columnList = "stock_code"),
           @Index(name = "idx_lstm_predict_target_stock", columnList = "predict_date,target_date,stock_code")
       })
@Data
@NoArgsConstructor
@AllArgsConstructor
@IdClass(LstmPredictionId.class)
public class LstmPrediction {
    
    @Id
    @Column(name = "stock_code", nullable = false, length = 20)
    private String stockCode;
    
    @Id
    @Column(name = "predict_date", nullable = false)
    private LocalDate predictDate;
    
    @Id
    @Column(name = "target_date", nullable = false)
    private LocalDate targetDate;
    
    @Column(name = "stock_name", length = 100)
    private String stockName;
    
    @Column(name = "latest_close", precision = 20, scale = 2)
    private BigDecimal latestClose;
    
    @Column(name = "predicted_close", precision = 20, scale = 2)
    private BigDecimal predictedClose;
    
    @Column(name = "expected_change", precision = 20, scale = 10)
    private BigDecimal expectedChange;
}

