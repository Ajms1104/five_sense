package com.example.fivesense.model;

import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.io.Serializable;
import java.time.LocalDate;

/**
 * LSTM 예측 결과의 복합 기본 키
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class LstmPredictionId implements Serializable {
    
    private String stockCode;
    private LocalDate predictDate;
    private LocalDate targetDate;
    
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        
        LstmPredictionId that = (LstmPredictionId) o;
        
        if (stockCode != null ? !stockCode.equals(that.stockCode) : that.stockCode != null) return false;
        if (predictDate != null ? !predictDate.equals(that.predictDate) : that.predictDate != null) return false;
        return targetDate != null ? targetDate.equals(that.targetDate) : that.targetDate == null;
    }
    
    @Override
    public int hashCode() {
        int result = stockCode != null ? stockCode.hashCode() : 0;
        result = 31 * result + (predictDate != null ? predictDate.hashCode() : 0);
        result = 31 * result + (targetDate != null ? targetDate.hashCode() : 0);
        return result;
    }
}
