import React, { useState, useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';
import styles from './stockChart.module.css'; // CSS 모듈 import


const ChartHeader = ({ stockInfo, isLoading }) => {
  if (isLoading || !stockInfo) {
    return <div className={styles['header-loading']}>종목 정보를 불러오는 중...</div>;
  }
  return (
    <div className={styles['chart-header']}>
      <div className={styles['stock-identity']}>
        <div className={styles['stock-logo']}>{stockInfo.name.charAt(0)}</div>
        <h2>{stockInfo.name}</h2>
      </div>
      <div className={styles['stock-price-info']}>
        <span className={`${styles['current-price']} ${styles[stockInfo.changeType]}`}>
          {stockInfo.price.toLocaleString()}원
        </span>
        <span className={`${styles['change-amount']} ${styles[stockInfo.changeType]}`}>
          {stockInfo.changeAmount >= 0 ? '▲' : '▼'} {Math.abs(stockInfo.changeAmount).toLocaleString()} ({stockInfo.changeRate}%)
        </span>
      </div>
    </div>
  );
};

const MainTabs = () => (
  <div className={styles['main-tabs']}>
    <button className={`${styles['tab-button']} ${styles.active}`}>차트·호가</button>
    <button className={styles['tab-button']}>종목정보</button>
    <button className={styles['tab-button']}>뉴스·공시</button>
    <button className={styles['tab-button']}>커뮤니티</button>
  </div>
);

const ChartControls = ({ chartType, onChartTypeChange }) => (
  <div className={styles['chart-controls']}>
    <div className={styles['timeframe-selector']}>
      {['1분', '일', '주', '월', '년'].map(type => (
        <button
          key={type}
          className={chartType === type ? styles.active : ''}
          onClick={() => onChartTypeChange(type)}
        >
          {type}
        </button>
      ))}
    </div>
    <div className={styles['tool-selector']}>
      <button>+ 보조지표</button>
      <button>그리기</button>
      <button>종목비교</button>
      <button>📊</button>
      <button>🗑️</button>
      <button>차트 크게보기 ↗</button>
    </div>
  </div>
);

// --- 메인 차트 컴포넌트 ---
const StockChart = ({ stockCode = '005930' }) => {
  const priceChartContainerRef = useRef(null);
  const volumeChartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candlestickSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);

  const [stockInfo, setStockInfo] = useState(null);
  const [chartType, setChartType] = useState('일');
  const [error, setError] = useState(null);

  // 차트 초기화 및 리사이즈 로직 (이전과 거의 동일)
  useEffect(() => {
    if (!priceChartContainerRef.current || !volumeChartContainerRef.current) return;

    // ... createChart 및 시리즈 생성 로직 (학생분의 기존 코드 유지)
    // ... 오류 처리 및 동기화 로직 등
    
    // 이 부분은 변경 없음
    const priceChart = createChart(priceChartContainerRef.current, { /* ... 옵션 ... */ });
    const volumeChart = createChart(volumeChartContainerRef.current, { /* ... 옵션 ... */ });
    candlestickSeriesRef.current = priceChart.addCandlestickSeries({ /* ... 옵션 ... */ });
    volumeSeriesRef.current = volumeChart.addHistogramSeries({ /* ... 옵션 ... */ });
    chartRef.current = { priceChart, volumeChart };

    return () => {
      if (chartRef.current) {
        chartRef.current.priceChart.remove();
        chartRef.current.volumeChart.remove();
      }
    };
  }, []);

  // 데이터 로딩 및 차트 업데이트 로직 (이전과 거의 동일)
  useEffect(() => {
    if (!candlestickSeriesRef.current || !volumeSeriesRef.current) return;

    const fetchChartData = async () => {
      setStockInfo(null);
      setError(null);
      try {
        // ... API 호출 및 데이터 가공 로직 ...
        // 학생분의 기존 코드와 동일하게 유지하면 됩니다.
        // 예시 데이터 설정 로직 (실제 API 호출로 대체)
        const response = await fetch(`/api/stock/daily-chart/${stockCode}?chartType=${chartType}`);
        if (!response.ok) throw new Error('데이터를 불러오는데 실패했습니다.');
        const data = await response.json();
        // ... 데이터 처리 ...
        // setStockInfo({ ... });
        // candlestickSeriesRef.current.setData(...);
        // volumeSeriesRef.current.setData(...);

      } catch (err) {
        console.error('차트 데이터 로딩 중 오류:', err);
        setError('차트 데이터를 불러올 수 없습니다. 잠시 후 다시 시도해주세요.');
      }
    };

    fetchChartData();
  }, [stockCode, chartType]);

  return (
    <div className={styles['stock-chart-layout']}>
      <ChartHeader stockInfo={stockInfo} isLoading={!stockInfo && !error} />
      <MainTabs />
      <ChartControls chartType={chartType} onChartTypeChange={setChartType} />
      
      <div className={styles['chart-area-container']}>
        {error ? (
          <div className={styles.error}>{error}</div>
        ) : (
          <>
            <div ref={priceChartContainerRef} className={styles['price-chart-container']} />
            <div ref={volumeChartContainerRef} className={styles['volume-chart-container']} />
          </>
        )}
      </div>
    </div>
  );
};

export default StockChart;
