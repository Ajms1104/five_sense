class StockChart {
    constructor() {
        this.stockCode = '005930';
        this.chartWrapper = document.querySelector('.chart-wrapper');
        this.chartContainer = document.querySelector('.chart-container');
        this.chart = null;          // 가격 차트
        this.volumeChart = null;    // 거래량 차트
        this.candlestickSeries = null;
        this.volumeSeries = null;
        this.chartType = 'daily';
        this.minuteType = '1'; // 기본 1분봉
        this.resizeHandle = null;
        this.startHeight = 0;
        this.startY = 0;
        this.stockInfo = null;      // 종목명
        this.latestData = null;     // 최신 데이터 저장용
        this.movingAverageSeries = {}; // 이동평균선 시리즈 저장용
        this.init();
    }

    init() {
        console.log('Initializing StockChart...');
        this.createChart();
        this.setupEventListeners();
        this.fetchChartData();
        this.initResizeHandle();
    }

    initResizeHandle() {
        this.resizeHandle = document.createElement('div');
        this.resizeHandle.className = 'resize-handle';
        this.chartWrapper.appendChild(this.resizeHandle);

        this.resizeHandle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            this.startHeight = this.chartWrapper.offsetHeight;
            this.startY = e.clientY;
            document.addEventListener('mousemove', this.handleResize);
            document.addEventListener('mouseup', this.stopResize);
        });
    }

    handleResize = (e) => {
        const diff = e.clientY - this.startY;
        const newHeight = Math.max(400, this.startHeight + diff);
        this.chartWrapper.style.height = `${newHeight}px`;
        if (this.chart && this.volumeChart) {
             const chartWidth = this.chartContainer.clientWidth;
             const priceHeight = this.chartContainer.clientHeight * 0.7;
             const volumeHeight = this.chartContainer.clientHeight * 0.3;
             this.chart.resize(chartWidth, priceHeight);
             this.volumeChart.resize(chartWidth, volumeHeight);
        }
    }

    stopResize = () => {
        document.removeEventListener('mousemove', this.handleResize);
        document.removeEventListener('mouseup', this.stopResize);
    }

    // 숫자 포맷 (콤마, M/K 단위)
    formatNumber(num, precision = 0) {
        if (num === null || num === undefined || isNaN(num)) return 'N/A';
        if (Math.abs(num) >= 1_000_000_000) {
            return (num / 1_000_000_000).toFixed(2) + 'B';
        } else if (Math.abs(num) >= 1_000_000) {
            return (num / 1_000_000).toFixed(2) + 'M';
        } else if (Math.abs(num) >= 1_000) {
             // 거래량 외에는 K 단위 사용 안 함
             return num.toLocaleString(undefined, { minimumFractionDigits: precision, maximumFractionDigits: precision });
            // return (num / 1_000).toFixed(precision) + 'K';
        }
        return num.toLocaleString(undefined, { minimumFractionDigits: precision, maximumFractionDigits: precision });
    }

    // 거래량 포맷 (M/K 단위 특화)
    formatVolume(num) {
        if (num === null || num === undefined || isNaN(num)) return 'N/A';
        if (Math.abs(num) >= 1_000_000) {
            return (num / 1_000_000).toFixed(2) + 'M';
        } else if (Math.abs(num) >= 1_000) {
             return (num / 1_000).toFixed(2) + 'K';
        }
        return num.toString();
    }


    createChart() {
        console.log('Creating chart...');

        // 메인 차트 컨테이너에 가격차트와 거래량 차트를 위한 두 개의 div 생성
        // chartInfo 패널 ID 변경 및 스타일 조정
         this.chartContainer.innerHTML = `
            <div id="priceChart" style="width: 100%; height: 70%;"></div>
            <div id="volumeChart" style="width: 100%; height: 30%; position: relative;"></div>
            <div id="stockInfoPanel" style="position: absolute; top: 5px; left: 5px; background: rgba(255,255,255,0.85); padding: 5px 8px; border-radius: 4px; font-size: 11px; color: black; z-index: 10; pointer-events: none; line-height: 1.4;"></div>
            <div id="volumeInfoPanel" style="position: absolute; bottom: 5px; left: 5px; background: rgba(255,255,255,0.85); padding: 3px 6px; border-radius: 4px; font-size: 11px; color: black; z-index: 10; pointer-events: none;"></div>
        `;

        const chartOptions = {
            layout: {
                background: { color: '#ffffff' },
                textColor: '#333333',
            },
            grid: { // 그리드 점선
                vertLines: { color: '#e0e0e0', style: LightweightCharts.LineStyle.Dashed },
                horzLines: { color: '#e0e0e0', style: LightweightCharts.LineStyle.Dashed },
            },
            crosshair: { // 크로스헤어 점선
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: {
                    width: 1,
                    color: '#888888',
                    style: LightweightCharts.LineStyle.Dashed,
                    labelVisible: true,
                },
                horzLine: {
                    width: 1,
                    color: '#888888',
                    style: LightweightCharts.LineStyle.Dashed,
                    labelVisible: true,
                },
            },
            timeScale: {
                borderColor: '#cccccc',
                timeVisible: true,
                secondsVisible: false,
                borderVisible: true,
                fixLeftEdge: true,
                fixRightEdge: true,
                tickMarkFormatter: (time, tickMarkType, locale) => {
                    const date = new Date(time * 1000);
                    switch(this.chartType) {
                        case 'yearly': return date.getFullYear().toString();
                        case 'monthly': return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}`;
                        case 'daily':
                        case 'weekly': return `${date.getFullYear().toString().slice(-2)}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
                        case 'minute': return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
                        default: return `${date.getFullYear().toString().slice(-2)}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
                    }
                },
                localization: {
                     timeFormatter: (time) => {
                         const date = new Date(time * 1000);
                         switch(this.chartType) {
                             case 'yearly': return date.getFullYear().toString();
                             case 'monthly': return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}`;
                             case 'daily':
                             case 'weekly': return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
                             case 'minute': return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
                             default: return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
                         }
                     }
                 }
            }
        };

        // 가격 차트 생성
        this.chart = LightweightCharts.createChart(document.getElementById('priceChart'), {
            ...chartOptions,
             rightPriceScale: { // 가격 축 설정
                 borderColor: '#cccccc',
                 borderVisible: true,
                 scaleMargins: { top: 0.08, bottom: 0.05 },
             },
             // 거래량 차트와 X축 공유하므로 여기서는 숨김
             timeScale: { ...chartOptions.timeScale, borderVisible: false },
        });

        // 거래량 차트 생성
        this.volumeChart = LightweightCharts.createChart(document.getElementById('volumeChart'), {
             ...chartOptions,
             crosshair: { // 거래량 차트는 세로 크로스헤어 라벨 숨김
                 ...chartOptions.crosshair,
                 vertLine: { ...chartOptions.crosshair.vertLine, labelVisible: false },
             },
             rightPriceScale: { // 거래량 축 설정
                 borderColor: '#cccccc',
                 borderVisible: true,
                 scaleMargins: { top: 0.2, bottom: 0 }, // 상단 여백 늘림
                 // 거래량 포맷터
                 priceFormatter: (price) => this.formatVolume(price),
             },
             timeScale: { // 거래량 차트의 timeScale은 숨김
                 visible: false,
                 borderVisible: false,
                 fixLeftEdge: true,
                 fixRightEdge: true,
             }
        });

        // 두 차트의 timeScale 동기화
        this.chart.timeScale().subscribeVisibleTimeRangeChange((timeRange) => {
            if (timeRange && this.volumeChart) {
                try { this.volumeChart.timeScale().setVisibleRange(timeRange); }
                catch (error) { console.log('Error syncing price chart to volume chart:', error.message); }
            }
        });
        this.volumeChart.timeScale().subscribeVisibleTimeRangeChange((timeRange) => {
            if (timeRange && this.chart) {
                try { this.chart.timeScale().setVisibleRange(timeRange); }
                catch (error) { console.log('Error syncing volume chart to price chart:', error.message); }
            }
        });

        // 캔들스틱 차트 시리즈 추가 (색상 변경: 상승=빨강, 하락=파랑)
        this.candlestickSeries = this.chart.addCandlestickSeries({
            upColor: '#ff0000', // 상승: 빨강
            downColor: '#0000ff', // 하락: 파랑
            borderVisible: false,
            wickUpColor: '#ff0000',
            wickDownColor: '#0000ff',
            priceFormat: { type: 'price', precision: 0, minMove: 1 },
        });

        // 거래량 차트 시리즈 추가 (색상 변경 없음, 기본값 사용 또는 데이터 매핑 시 적용)
        this.volumeSeries = this.volumeChart.addHistogramSeries({
           // color: '#26a69a', // 기본 색상 사용 또는 데이터에서 정의
            priceFormat: { type: 'volume' },
            priceScaleId: 'right',
            scaleMargins: { top: 0.2, bottom: 0 },
        });

        // 마우스 이벤트 구독하여 상세 정보 표시
        const updateInfoPanel = (param) => {
            let candleData = null;
            let volumeDataPoint = null;
            let time = null;

            // Get data based on hover or latest available
            if (param.time && param.seriesData) {
                candleData = param.seriesData.get(this.candlestickSeries);
                volumeDataPoint = param.seriesData.get(this.volumeSeries);
                time = param.time;
                // console.log("Hovering:", time, candleData, volumeDataPoint);
            } else if (!param.time && this.latestData) { // Mouse left or initial load
                candleData = this.latestData; // latestData includes ohlc + volume
                volumeDataPoint = this.latestData; // Use latestData for volume too
                time = this.latestData.time;
                // console.log("Mouse Left / Initial:", time, candleData, volumeDataPoint);
            }

            // Ensure we have valid data to display
            if (!candleData || !time) {
               //  console.log("Hiding panel - No data or time");
                document.getElementById('stockInfoPanel').style.display = 'none';
                document.getElementById('volumeInfoPanel').style.display = 'none';
                return;
            }

            const date = new Date(time * 1000);
            let dateStr = this.formatDateForDisplay(date);
            const volumeValue = volumeDataPoint?.value ?? volumeDataPoint?.volume ?? 0; // Handles both seriesData and latestData structure

            // Check for NaN or invalid numbers (more robust)
            if (isNaN(candleData.open) || isNaN(candleData.high) || isNaN(candleData.low) || isNaN(candleData.close) || isNaN(volumeValue)) {
               //  console.log("Hiding panel - Invalid data found", candleData, volumeValue);
                 document.getElementById('stockInfoPanel').style.display = 'none';
                 document.getElementById('volumeInfoPanel').style.display = 'none';
                 return;
            }


            const priceChange = candleData.close - candleData.open;
            const priceChangePercent = candleData.open === 0 ? 0 : (priceChange / candleData.open * 100);
            const priceDirection = priceChange >= 0 ? 'up' : 'down';
            const sign = priceChange >= 0 ? '+' : '';
            const color = priceDirection === 'up' ? '#ff0000' : '#0000ff'; // 빨강/파랑

            // Update panels (using candleData for prices)
            let stockCodeName = this.stockInfo || this.stockCode;
            document.getElementById('stockInfoPanel').innerHTML = `
                <span style="font-weight: bold;">${stockCodeName}</span> <span style="font-size: 10px;">${dateStr}</span><br>
                <span>시가 <span style="color: ${color};">${this.formatNumber(candleData.open)}</span></span>
                <span style="margin-left: 5px;">고가 <span style="color: ${color};">${this.formatNumber(candleData.high)}</span></span>
                <span style="margin-left: 5px;">저가 <span style="color: ${color};">${this.formatNumber(candleData.low)}</span></span>
                <span style="margin-left: 5px;">종가 <span style="color: ${color};">${this.formatNumber(candleData.close)}</span></span>
                <span style="color: ${color}; margin-left: 5px;">(${sign}${this.formatNumber(priceChange)} ${sign}${priceChangePercent.toFixed(2)}%)</span>
            `;

            document.getElementById('volumeInfoPanel').innerHTML = `
                거래량 <span style="color: ${color};">${this.formatVolume(volumeValue)}</span>
               `;

            document.getElementById('stockInfoPanel').style.display = 'block';
            document.getElementById('volumeInfoPanel').style.display = 'block';
        };

        this.chart.subscribeCrosshairMove(updateInfoPanel);
        // 마우스가 차트 밖으로 나갈 때 최신 정보 표시
        this.chart.unsubscribeCrosshairMove((param) => { // 이벤트 리스너 이름 변경 또는 새 리스너
            if (!param.point) { // 마우스가 차트 영역 밖으로 나감
                updateInfoPanel({}); // 빈 객체를 전달하여 latestData 사용 유도
             }
         });


        // 차트 생성 후 스타일 추가 - 차트 간격 조정
        document.querySelector('#priceChart').style.marginBottom = '0';
        document.querySelector('#volumeChart').style.marginTop = '-1px'; // 약간 겹치게
    }

    // 날짜 포맷 함수 분리
    formatDateForDisplay(date) {
        switch(this.chartType) {
            case 'yearly': return date.getFullYear().toString();
            case 'monthly': return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}`;
            case 'daily':
            case 'weekly': return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
            case 'minute': return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
            default: return date.toLocaleDateString('ko-KR');
        }
    }


    setupEventListeners() {
        const stockSelect = document.getElementById('stockSelector');
        stockSelect.value = this.stockCode;
        stockSelect.addEventListener('change', (e) => {
            this.stockCode = e.target.value;
            const stockOption = stockSelect.options[stockSelect.selectedIndex];
            this.stockInfo = stockOption.textContent;
            this.fetchChartData();
        });

        const minuteSelect = document.getElementById('minuteSelector');
        minuteSelect.addEventListener('change', (e) => {
            this.minuteType = e.target.value;
            this.fetchChartData();
        });

        const chartTypeBtns = document.querySelectorAll('.chart-type-btn');
        chartTypeBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const newType = e.target.dataset.type;
                chartTypeBtns.forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.chartType = newType;
                const minuteSelector = document.getElementById('minuteSelector');
                minuteSelector.style.display = (newType === 'minute') ? 'block' : 'none';
                this.fetchChartData();
            });
        });

        window.addEventListener('resize', () => {
            if (this.chart && this.volumeChart) {
                 this.handleResize({ clientY: this.startY + (this.chartWrapper.offsetHeight - this.startHeight) }); // 가상 이벤트 전달
             }
        });

        const stockOption = stockSelect.options[stockSelect.selectedIndex];
        this.stockInfo = stockOption.textContent;
    }

    async fetchChartData() {
        try {
            console.log(`Fetching ${this.chartType} chart data for stock ${this.stockCode}...`);

            let apiId;
            let requestData = { stk_cd: this.stockCode, upd_stkpc_tp: "1" };

            switch(this.chartType) {
                case 'minute': apiId = 'KA10080'; requestData.tic_scope = this.minuteType; break;
                case 'daily': apiId = 'KA10081'; break;
                case 'weekly': apiId = 'KA10082'; break;
                case 'monthly': apiId = 'KA10083'; break;
                case 'yearly': apiId = 'KA10094'; break;
                default: apiId = 'KA10081';
            }

            const response = await fetch(`/api/stock/daily-chart/${this.stockCode}?apiId=${apiId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData)
            });

            const data = await response.json();
            console.log('Received data:', data);

            let chartData;
            switch(this.chartType) {
                case 'monthly': chartData = data.stk_mth_pole_chart_qry; break;
                case 'daily': chartData = data.stk_dt_pole_chart_qry; break;
                case 'weekly': chartData = data.stk_stk_pole_chart_qry; break; // API 응답 키 확인 필요
                case 'yearly': chartData = data.stk_yr_pole_chart_qry; break;
                case 'minute': chartData = data.stk_min_pole_chart_qry || data.stk_stk_pole_chart_qry; break;
                default: chartData = data.stk_dt_pole_chart_qry;
            }

            if (chartData) {
                console.log('Processing chart data:', chartData);

                const processedData = chartData.map(item => {
                    let dateStr = (this.chartType === 'minute') ? item.cntr_tm : (item.dt || item.trd_dt);
                    if (!dateStr) return null;

                    let date;
                    if (this.chartType === 'yearly' && dateStr.length === 4) {
                        date = new Date(parseInt(dateStr), 0, 1); // 연도 시작일
                    } else if (this.chartType === 'minute' && dateStr.length === 14) {
                        const formattedDate = `${dateStr.slice(0,4)}-${dateStr.slice(4,6)}-${dateStr.slice(6,8)}T${dateStr.slice(8,10)}:${dateStr.slice(10,12)}:${dateStr.slice(12,14)}`;
                        date = new Date(formattedDate);
                    } else if (dateStr.length === 8) {
                         const formattedDate = `${dateStr.slice(0,4)}-${dateStr.slice(4,6)}-${dateStr.slice(6,8)}`;
                         date = new Date(formattedDate);
                     } else { return null; }

                    if (isNaN(date.getTime())) {
                        console.log('Invalid date:', dateStr);
                        return null;
                    }

                    let close, open, high, low, volume;
                    if (this.chartType === 'minute') {
                        close = parseFloat(item.cur_prc);
                        open = parseFloat(item.open_pric) || close;
                        high = parseFloat(item.high_pric) || close;
                        low = parseFloat(item.low_pric) || close;
                        volume = parseFloat(item.trde_qty) || 0;
                    } else {
                        close = parseFloat(item.cur_prc || item.clos_prc);
                        open = parseFloat(item.open_pric || item.open_prc) || close;
                        high = parseFloat(item.high_pric || item.high_prc) || close;
                        low = parseFloat(item.low_pric || item.low_prc) || close;
                        volume = parseFloat(item.trde_qty || item.trd_qty) || 0;
                    }

                    if (isNaN(close)) return null;

                    return {
                        time: Math.floor(date.getTime() / 1000),
                        open, high, low, close, volume
                    };
                }).filter(item => item !== null);

                console.log('Processed data:', processedData);

                if (processedData.length === 0) {
                    console.error('No valid data to display');
                     this.candlestickSeries.setData([]);
                     this.volumeSeries.setData([]);
                     this.latestData = null; // 최신 데이터 초기화
                     this.updateInfoPanel({}); // 정보 패널 숨김
                    return;
                }

                processedData.sort((a, b) => a.time - b.time);

                // 최신 데이터 저장
                this.latestData = processedData[processedData.length - 1];

                const candlestickData = processedData.map(({ time, open, high, low, close }) => ({
                    time, open, high, low, close
                }));

                // 거래량 데이터 (색상 적용)
                 const volumeData = processedData.map(({ time, volume, open, close }) => ({
                     time,
                     value: volume,
                     color: close >= open ? '#ff0000' : '#0000ff' // 상승(빨강), 하락(파랑)
                 }));


                console.log('Setting candlestick data:', candlestickData);
                console.log('Setting volume data:', volumeData);

                // 데이터 설정 전에 초기화할 필요 없음 (setData가 덮어씀)
                this.candlestickSeries.setData(candlestickData);
                this.volumeSeries.setData(volumeData);

                // 차트 설정 업데이트 (applyOptions 사용)
                 this.updateChartOptionsForType();


                // 개별적으로 fitContent 호출
                try { this.chart.timeScale().fitContent(); }
                catch (error) { console.log('Error fitting price chart content:', error.message); }

                try { this.volumeChart.timeScale().fitContent(); }
                catch (error) { console.log('Error fitting volume chart content:', error.message); }

                // 초기 정보 패널 업데이트 (최신 데이터 사용)
                this.updateInfoPanel({});


            } else {
                console.error('No chart data found in response');
                 this.candlestickSeries.setData([]);
                 this.volumeSeries.setData([]);
                 this.latestData = null;
                 this.updateInfoPanel({});
            }
        } catch (error) {
            console.error('Error fetching chart data:', error);
            document.getElementById('stockInfoPanel').innerHTML = `<div style="color: red;">차트 데이터 오류: ${error.message}</div>`;
            document.getElementById('stockInfoPanel').style.display = 'block';
             document.getElementById('volumeInfoPanel').style.display = 'none';
        }
    }

    // 차트 타입에 따른 옵션 업데이트 함수
    updateChartOptionsForType() {
        const commonTimeScaleOptions = {
            localization: {
                 timeFormatter: (time) => {
                     const date = new Date(time * 1000);
                     switch(this.chartType) {
                         case 'yearly': return date.getFullYear().toString();
                         case 'monthly': return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}`;
                         case 'daily':
                         case 'weekly': return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
                         case 'minute': return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
                         default: return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
                     }
                 }
             }
        };

        let priceTimeScaleOptions = {};
        let volumeTimeScaleOptions = { visible: false, borderVisible: false }; // 거래량 X축은 항상 숨김

        switch(this.chartType) {
            case 'yearly':
            case 'monthly':
            case 'daily':
            case 'weekly':
                 priceTimeScaleOptions = { ...commonTimeScaleOptions, timeVisible: false, secondsVisible: false };
                 break;
            case 'minute':
                 priceTimeScaleOptions = { ...commonTimeScaleOptions, timeVisible: true, secondsVisible: false };
                 break;
            default:
                 priceTimeScaleOptions = { ...commonTimeScaleOptions, timeVisible: false, secondsVisible: false };
        }

        this.chart.applyOptions({ timeScale: priceTimeScaleOptions });
        // 거래량 차트의 timeScale 옵션은 숨겨져 있으므로 applyOptions 불필요
        // this.volumeChart.applyOptions({ timeScale: volumeTimeScaleOptions }); // 필요 시 활성화
    }
}

// 차트 초기화
document.addEventListener('DOMContentLoaded', () => {
    new StockChart();
}); 