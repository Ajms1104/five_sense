import React, { useState, useEffect, useRef } from 'react';
import { createChart, CrosshairMode } from 'lightweight-charts';
import styles from './stockChart.module.css'; // CSS 모듈 import


const ChartHeader = ({ stockInfo, isLoading }) => {
  if (isLoading || !stockInfo) {
    return <div className={styles['header-loading']}>종목 정보를 불러오는 중...</div>;
  }
  
  // stockInfo의 필수 속성들이 존재하는지 확인
  if (!stockInfo.name || stockInfo.price === undefined || stockInfo.changeAmount === undefined) {
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
    if (!priceChartContainerRef.current || !volumeChartContainerRef.current) {
      console.log('차트 컨테이너가 아직 준비되지 않았습니다.');
      return;
    }

    console.log('차트 컨테이너 크기:', {
      price: {
        width: priceChartContainerRef.current.clientWidth,
        height: priceChartContainerRef.current.clientHeight
      },
      volume: {
        width: volumeChartContainerRef.current.clientWidth,
        height: volumeChartContainerRef.current.clientHeight
      }
    });

    // 차트 생성
    const priceChart = createChart(priceChartContainerRef.current, {
      width: Math.max(priceChartContainerRef.current.clientWidth, 100),
      height: Math.max(priceChartContainerRef.current.clientHeight, 100),
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333333',
        fontFamily: "'Open Sans', sans-serif"
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' }
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: '#999999',
          width: 1,
          style: 1,
          labelBackgroundColor: '#ffffff'
        },
        horzLine: {
          color: '#999999',
          width: 1,
          style: 1,
          labelBackgroundColor: '#ffffff'
        }
      },
      timeScale: {
        borderColor: '#dddddd',
        borderVisible: true,
        timeVisible: true,
        secondsVisible: false
      },
      rightPriceScale: {
        borderColor: '#dddddd',
        borderVisible: true,
        scaleMargins: { top: 0.1, bottom: 0.1 }
      }
    });

    const volumeChart = createChart(volumeChartContainerRef.current, {
      width: Math.max(volumeChartContainerRef.current.clientWidth, 100),
      height: Math.max(volumeChartContainerRef.current.clientHeight, 100),
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333333',
        fontFamily: "'Open Sans', sans-serif"
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' }
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: '#999999',
          width: 1,
          style: 1,
          labelBackgroundColor: '#ffffff'
        },
        horzLine: {
          color: '#999999',
          width: 1,
          style: 1,
          labelBackgroundColor: '#ffffff'
        }
      },
      timeScale: {
        borderColor: '#dddddd',
        borderVisible: true,
        timeVisible: true,
        secondsVisible: false
      },
      rightPriceScale: {
        borderColor: '#dddddd',
        borderVisible: true,
        scaleMargins: { top: 0.1, bottom: 0.1 }
      }
    });

    console.log('차트 생성 완료:', { priceChart, volumeChart });

    // 시리즈 생성
    candlestickSeriesRef.current = priceChart.addCandlestickSeries({
      upColor: '#ff3333',
      downColor: '#5050ff',
      borderVisible: false,
      wickUpColor: '#ff3333',
      wickDownColor: '#5050ff'
    });

    volumeSeriesRef.current = volumeChart.addHistogramSeries({
      color: '#26a69a',
      priceFormat: { type: 'volume' }
    });

    console.log('시리즈 생성 완료:', { 
      candlestick: candlestickSeriesRef.current, 
      volume: volumeSeriesRef.current 
    });

    chartRef.current = { priceChart, volumeChart };

    // 리사이즈 핸들러
    const handleResize = () => {
      if (priceChartContainerRef.current && volumeChartContainerRef.current) {
        const priceWidth = Math.max(priceChartContainerRef.current.clientWidth, 100);
        const priceHeight = Math.max(priceChartContainerRef.current.clientHeight, 100);
        const volumeWidth = Math.max(volumeChartContainerRef.current.clientWidth, 100);
        const volumeHeight = Math.max(volumeChartContainerRef.current.clientHeight, 100);
        
        console.log('차트 리사이즈:', { priceWidth, priceHeight, volumeWidth, volumeHeight });
        
        priceChart.resize(priceWidth, priceHeight);
        volumeChart.resize(volumeWidth, volumeHeight);
      }
    };

    window.addEventListener('resize', handleResize);
    
    // 초기 리사이즈 실행
    setTimeout(handleResize, 100);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        try {
          if (chartRef.current.priceChart) {
            chartRef.current.priceChart.remove();
          }
          if (chartRef.current.volumeChart) {
            chartRef.current.volumeChart.remove();
          }
        } catch (e) {
          console.log('차트 제거 중 오류:', e);
        }
        chartRef.current = null;
        candlestickSeriesRef.current = null;
        volumeSeriesRef.current = null;
      }
    };
  }, []);

  // 데이터 로딩 및 차트 업데이트 로직 (이전과 거의 동일)
  useEffect(() => {
    if (!candlestickSeriesRef.current || !volumeSeriesRef.current) {
      console.log('차트 시리즈가 아직 준비되지 않았습니다.');
      return;
    }

    const fetchChartData = async () => {
      console.log('차트 데이터 로딩 시작:', { stockCode, chartType });
      setStockInfo(null);
      setError(null);
      try {
        // chartType을 apiId로 변환
        let apiId;
        let requestData = { stk_cd: stockCode, upd_stkpc_tp: "1" };
        
        switch (chartType) {
          case '1분': apiId = 'KA10080'; requestData.tic_scope = '1'; break;
          case '일': apiId = 'KA10081'; break;
          case '주': apiId = 'KA10082'; break;
          case '월': apiId = 'KA10083'; break;
          case '년': apiId = 'KA10094'; break;
          default: apiId = 'KA10081';
        }

        console.log('API 요청:', { apiId, requestData });

        const response = await fetch(`/api/stock/daily-chart/${stockCode}?apiId=${apiId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestData)
        });
        
        console.log('API 응답 상태:', response.status, response.statusText);
        
        if (!response.ok) throw new Error('데이터를 불러오는데 실패했습니다.');
        const data = await response.json();
        
        console.log('API 응답 데이터:', data);
        
        // 차트 객체가 여전히 유효한지 확인
        if (!candlestickSeriesRef.current || !volumeSeriesRef.current) {
          console.log('차트가 이미 제거되었습니다.');
          return;
        }
        
        // 차트 데이터 처리 로직
        let chartData;
        switch (chartType) {
          case '월': chartData = data.stk_mth_pole_chart_qry; break;
          case '일': chartData = data.stk_dt_pole_chart_qry; break;
          case '주': chartData = data.stk_stk_pole_chart_qry; break;
          case '년': chartData = data.stk_yr_pole_chart_qry; break;
          case '1분': chartData = data.stk_min_pole_chart_qry || data.stk_stk_pole_chart_qry; break;
          default: chartData = data.stk_dt_pole_chart_qry;
        }

        console.log('차트 데이터:', chartData);

        if (chartData && chartData.length > 0) {
          const processedData = [];
          for (const item of chartData) {
            let dateStr = (chartType === '1분') ? item.cntr_tm : (item.dt || item.trd_dt);
            if (!dateStr) continue;
            
            let timestamp;
            try {
              if (chartType === '년' && dateStr.length === 4) {
                timestamp = new Date(parseInt(dateStr), 0, 1).getTime() / 1000;
              } else if (chartType === '1분' && dateStr.length === 14) {
                timestamp = new Date(
                  parseInt(dateStr.slice(0, 4)),
                  parseInt(dateStr.slice(4, 6)) - 1,
                  parseInt(dateStr.slice(6, 8)),
                  parseInt(dateStr.slice(8, 10)),
                  parseInt(dateStr.slice(10, 12))
                ).getTime() / 1000;
              } else if (dateStr.length === 8) {
                timestamp = new Date(
                  parseInt(dateStr.slice(0, 4)),
                  parseInt(dateStr.slice(4, 6)) - 1,
                  parseInt(dateStr.slice(6, 8))
                ).getTime() / 1000;
              } else {
                continue;
              }
            } catch (e) {
              continue;
            }
            
            if (isNaN(timestamp)) continue;

            let close = parseFloat(item.cur_prc || item.clos_prc);
            if (isNaN(close)) continue;
            let open = parseFloat(item.open_pric || item.open_prc);
            let high = parseFloat(item.high_pric || item.high_prc);
            let low = parseFloat(item.low_pric || item.low_prc);
            let volume = parseFloat(item.trde_qty || item.trd_qty) || 0;
            
            if (isNaN(open)) open = close;
            if (isNaN(high)) high = Math.max(close, open);
            if (isNaN(low)) low = Math.min(close, open);

            processedData.push({ time: timestamp, open, high, low, close, volume });
          }

          console.log('처리된 데이터:', processedData);

          if (processedData.length > 0) {
            processedData.sort((a, b) => a.time - b.time);
            const candlestickData = processedData.map(({ time, open, high, low, close }) => ({ time, open, high, low, close }));
            const volumeData = processedData.map(({ time, volume, open, close }) => ({
              time,
              value: volume,
              color: close >= open ? '#ff3333' : '#5050ff'
            }));

            console.log('차트에 설정할 데이터:', { candlestickData, volumeData });

            // 차트 객체가 여전히 유효한지 다시 확인하고 안전하게 데이터 설정
            try {
              if (candlestickSeriesRef.current) {
                candlestickSeriesRef.current.setData(candlestickData);
                console.log('캔들스틱 데이터 설정 완료');
              }
              if (volumeSeriesRef.current) {
                volumeSeriesRef.current.setData(volumeData);
                console.log('거래량 데이터 설정 완료');
              }
            } catch (e) {
              console.log('차트 데이터 설정 중 오류:', e);
              return;
            }
            
            // 차트 정보 업데이트
            const latestData = processedData[processedData.length - 1];
            setStockInfo({
              name: stockCode, // 종목 코드를 이름으로 사용
              price: latestData.close,
              changeAmount: latestData.close - latestData.open,
              changeRate: ((latestData.close - latestData.open) / latestData.open * 100).toFixed(2),
              changeType: latestData.close >= latestData.open ? 'up' : 'down'
            });
          }
        } else {
          console.log('차트 데이터가 없습니다.');
        }

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
            <div 
              ref={priceChartContainerRef} 
              className={styles['price-chart-container']} 
              style={{ 
                width: '100%', 
                height: '400px', 
                border: '1px solid #ddd',
                backgroundColor: '#f9f9f9'
              }} 
            />
            <div 
              ref={volumeChartContainerRef} 
              className={styles['volume-chart-container']} 
              style={{ 
                width: '100%', 
                height: '200px', 
                border: '1px solid #ddd',
                backgroundColor: '#f9f9f9'
              }} 
            />
          </>
        )}
      </div>
    </div>
  );
};

export default StockChart;
