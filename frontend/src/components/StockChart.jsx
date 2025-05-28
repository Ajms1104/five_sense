import React, { useEffect, useRef } from 'react';
import { createChart, CrosshairMode } from 'lightweight-charts';
import '../styles/StockChart.css';

const StockChart = ({ stockCode = '005930', chartType = 'daily', minuteType = '1' }) => {
  const chartContainerRef = useRef(null);
  const priceChartContainerRef = useRef(null);
  const volumeChartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candlestickSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const dataMapRef = useRef(new Map());
  const latestDataRef = useRef(null);
  const isSyncingRef = useRef(false);

  useEffect(() => {
    if (!chartContainerRef.current || !priceChartContainerRef.current || !volumeChartContainerRef.current) return;

    const containerWidth = chartContainerRef.current.clientWidth;
    const priceChartHeight = Math.floor(chartContainerRef.current.clientHeight * 0.65);
    const volumeChartHeight = Math.floor(chartContainerRef.current.clientHeight * 0.35) - 2;

    const commonOptions = {
      width: containerWidth,
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
          labelBackgroundColor: '#ffffff',
          labelVisible: false
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
      handleScroll: true,
      handleScale: true
    };

    try {
      // 차트 인스턴스 생성
      const priceChart = createChart(priceChartContainerRef.current, {
        ...commonOptions,
        height: priceChartHeight,
        rightPriceScale: {
          borderColor: '#dddddd',
          borderVisible: true,
          scaleMargins: { top: 0.1, bottom: 0.1 },
          visible: true,
          autoScale: true
        }
      });

      const volumeChart = createChart(volumeChartContainerRef.current, {
        ...commonOptions,
        height: volumeChartHeight,
        rightPriceScale: {
          borderColor: '#dddddd',
          borderVisible: true,
          scaleMargins: { top: 0.1, bottom: 0.1 },
          visible: true,
          autoScale: true
        }
      });

      // 차트 시리즈 생성
      const candlestickSeries = priceChart.addCandlestickSeries({
        upColor: '#ff3333',
        downColor: '#5050ff',
        borderVisible: false,
        wickUpColor: '#ff3333',
        wickDownColor: '#5050ff',
        priceFormat: { type: 'price', precision: 0 }
      });

      const volumeSeries = volumeChart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
        scaleMargins: { top: 0.1, bottom: 0.1 }
      });

      // 차트 동기화
      priceChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
        if (timeRange && !isSyncingRef.current) {
          isSyncingRef.current = true;
          volumeChart.timeScale().setVisibleLogicalRange(timeRange);
          isSyncingRef.current = false;
        }
      });

      volumeChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
        if (timeRange && !isSyncingRef.current) {
          isSyncingRef.current = true;
          priceChart.timeScale().setVisibleLogicalRange(timeRange);
          isSyncingRef.current = false;
        }
      });

      // 크로스헤어 동기화
      priceChart.subscribeCrosshairMove(param => {
        if (!param.point || !param.time) {
          volumeChart.clearCrosshairPosition();
          return;
        }
        volumeChart.setCrosshairPosition(param.point, param.time);
      });

      volumeChart.subscribeCrosshairMove(param => {
        if (!param.point || !param.time) {
          priceChart.clearCrosshairPosition();
          return;
        }
        priceChart.setCrosshairPosition(param.point, param.time);
      });

      // 리사이즈 이벤트 처리
      const handleResize = () => {
        if (!chartRef.current) return;
        const { priceChart, volumeChart } = chartRef.current;
        const chartWidth = chartContainerRef.current.clientWidth;
        const totalHeight = chartContainerRef.current.clientHeight;
        const priceChartHeight = Math.floor(totalHeight * 0.65);
        const volumeChartHeight = Math.floor(totalHeight * 0.35) - 2;
        priceChart.resize(chartWidth, priceChartHeight);
        volumeChart.resize(chartWidth, volumeChartHeight);
      };

      window.addEventListener('resize', handleResize);
      handleResize();

      // ref 업데이트
      chartRef.current = { priceChart, volumeChart };
      candlestickSeriesRef.current = candlestickSeries;
      volumeSeriesRef.current = volumeSeries;

      return () => {
        window.removeEventListener('resize', handleResize);
        if (chartRef.current) {
          chartRef.current.priceChart.remove();
          chartRef.current.volumeChart.remove();
        }
      };
    } catch (error) {
      console.error('차트 초기화 중 오류:', error);
    }
  }, []);

  useEffect(() => {
    const fetchChartData = async () => {
      try {
        let apiId;
        let requestData = { stk_cd: stockCode, upd_stkpc_tp: "1" };
        switch (chartType) {
          case 'minute': apiId = 'KA10080'; requestData.tic_scope = minuteType; break;
          case 'daily': apiId = 'KA10081'; break;
          case 'weekly': apiId = 'KA10082'; break;
          case 'monthly': apiId = 'KA10083'; break;
          case 'yearly': apiId = 'KA10094'; break;
          default: apiId = 'KA10081';
        }

        const response = await fetch(`/api/stock/daily-chart/${stockCode}?apiId=${apiId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestData)
        });

        const data = await response.json();
        let chartData;
        switch (chartType) {
          case 'monthly': chartData = data.stk_mth_pole_chart_qry; break;
          case 'daily': chartData = data.stk_dt_pole_chart_qry; break;
          case 'weekly': chartData = data.stk_stk_pole_chart_qry; break;
          case 'yearly': chartData = data.stk_yr_pole_chart_qry; break;
          case 'minute': chartData = data.stk_min_pole_chart_qry || data.stk_stk_pole_chart_qry; break;
          default: chartData = data.stk_dt_pole_chart_qry;
        }

        if (chartData && chartData.length > 0) {
          const processedData = chartData.map(item => {
            let dateStr = (chartType === 'minute') ? item.cntr_tm : (item.dt || item.trd_dt);
            if (!dateStr) return null;

            let timestamp;
            try {
              if (chartType === 'yearly' && dateStr.length === 4) {
                timestamp = new Date(parseInt(dateStr), 0, 1).getTime() / 1000;
              } else if (chartType === 'minute' && dateStr.length === 14) {
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
                return null;
              }
            } catch (e) {
              return null;
            }

            let close = parseFloat(item.cur_prc || item.clos_prc);
            if (isNaN(close)) return null;
            let open = parseFloat(item.open_pric || item.open_prc);
            let high = parseFloat(item.high_pric || item.high_prc);
            let low = parseFloat(item.low_pric || item.low_prc);
            let volume = parseFloat(item.trde_qty || item.trd_qty) || 0;
            if (isNaN(open)) open = close;
            if (isNaN(high)) high = Math.max(close, open);
            if (isNaN(low)) low = Math.min(close, open);

            return { time: timestamp, open, high, low, close, volume };
          }).filter(Boolean);

          if (processedData.length > 0) {
            processedData.sort((a, b) => a.time - b.time);
            const candlestickData = processedData.map(({ time, open, high, low, close }) => ({ time, open, high, low, close }));
            const volumeData = processedData.map(({ time, volume, open, close }) => ({
              time,
              value: volume,
              color: close >= open ? '#ff3333' : '#5050ff'
            }));

            if (candlestickSeriesRef.current && volumeSeriesRef.current) {
              candlestickSeriesRef.current.setData(candlestickData);
              volumeSeriesRef.current.setData(volumeData);
              if (chartRef.current) {
                chartRef.current.priceChart.timeScale().fitContent();
                chartRef.current.volumeChart.timeScale().fitContent();
              }
            }
            dataMapRef.current = new Map(processedData.map(d => [d.time, d]));
            latestDataRef.current = processedData[processedData.length - 1];
          }
        }
      } catch (error) {
        console.error('차트 데이터 로딩 중 오류:', error);
      }
    };

    fetchChartData();
  }, [stockCode, chartType, minuteType]);

  return (
    <div ref={chartContainerRef} className="chart-container" >
      <div className="chart-separator">
        <div ref={priceChartContainerRef} className='price-chart-container'>
          <div id="stockInfoPanel" className='stock-info-panel'></div>
        </div>
        <div className="divider"></div>
        <div ref={volumeChartContainerRef} className='volume-chart-container' >
          <div id="volumeInfoPanel" className='volume-info'></div>
        </div>
      </div>
    </div>
  );
};

export default StockChart; 
