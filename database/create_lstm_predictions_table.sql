-- LSTM 예측 결과를 저장할 테이블 생성 SQL
-- PostgreSQL용

-- 테이블이 이미 존재하면 삭제 (주의: 데이터도 함께 삭제됩니다)
-- DROP TABLE IF EXISTS lstm_predictions CASCADE;

-- LSTM 예측 결과 테이블 생성
CREATE TABLE IF NOT EXISTS lstm_predictions (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    stk_cd VARCHAR(20) NOT NULL,
    lstm_pred_log DOUBLE PRECISION,
    true_target_log_return DOUBLE PRECISION,
    CONSTRAINT unique_date_stock UNIQUE (date, stk_cd)
);

-- 인덱스 생성 (조회 성능 향상)
CREATE INDEX IF NOT EXISTS idx_lstm_date ON lstm_predictions(date);
CREATE INDEX IF NOT EXISTS idx_lstm_stock ON lstm_predictions(stk_cd);
CREATE INDEX IF NOT EXISTS idx_lstm_date_stock ON lstm_predictions(date, stk_cd);

-- 코멘트 추가
COMMENT ON TABLE lstm_predictions IS 'LSTM 모델의 주가 예측 결과 저장';
COMMENT ON COLUMN lstm_predictions.date IS '예측 날짜';
COMMENT ON COLUMN lstm_predictions.stk_cd IS '종목 코드';
COMMENT ON COLUMN lstm_predictions.lstm_pred_log IS 'LSTM 모델의 로그 수익률 예측값';
COMMENT ON COLUMN lstm_predictions.true_target_log_return IS '실제 로그 수익률';


