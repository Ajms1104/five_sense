class StockChart {
    constructor(stockCode = '005930') {
        this.stockCode = stockCode;
        this.chartWrapper = document.querySelector('.chart-wrapper');
        this.chartContainer = document.querySelector('.chart-container');
        this.priceChart = null;        // 가격 차트
        this.volumeChart = null;       // 거래량 차트
        this.candlestickSeries = null; // 캔들스틱 시리즈
        this.volumeSeries = null;      // 거래량 시리즈
        this.chartType = 'daily';
        this.minuteType = '1';         // 기본 1분봉
        this.resizeHandle = null;
        this.startHeight = 0;
        this.startY = 0;
        this.stockInfo = null;         // 종목명
        this.latestData = null;        // 최신 데이터 저장용
        this.movingAverageSeries = {}; // 이동평균선 시리즈 저장용
        this.dataMap = new Map();      // 시간 기반 데이터 조회를 위한 Map
        this.isSyncing = false;        // 동기화 중복 방지 플래그
        
        // 차트 컨테이너가 없으면 생성
        if (!this.chartContainer) {
            this.chartContainer = document.createElement('div');
            this.chartContainer.className = 'chart-container';
            this.chartWrapper.appendChild(this.chartContainer);
        }
        
        this.init();
    }

    init() {
        console.log('Initializing StockChart...');
        this.createChart();
        this.setupEventListeners();
        this.fetchChartData();
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

        // 차트 컨테이너 초기화
        this.chartContainer.innerHTML = `
            <div class="chart-separator">
                <div id="priceChartContainer" style="width: 100%; height: 65%; position: relative;">
                    <div id="stockInfoPanel" style="position: absolute; top: 5px; left: 5px; background: rgba(255,255,255,0.85); padding: 5px 8px; border-radius: 4px; font-size: 11px; color: black; z-index: 10; pointer-events: none; line-height: 1.4;"></div>
                </div>
                <div class="divider" style="width: 100%; height: 2px; background-color: #dddddd;"></div>
                <div id="volumeChartContainer" style="width: 100%; height: 35%; position: relative;">
                    <div id="volumeInfoPanel" style="position: absolute; top: 5px; left: 5px; background: rgba(255,255,255,0.85); padding: 3px 6px; border-radius: 4px; font-size: 11px; color: black; z-index: 10; pointer-events: none;"></div>
                </div>
            </div>
        `;

        // 차트 컨테이너 크기
        const containerWidth = this.chartContainer.clientWidth;
        const priceChartHeight = Math.floor(this.chartContainer.clientHeight * 0.65);
        const volumeChartHeight = Math.floor(this.chartContainer.clientHeight * 0.35) - 2; // 구분선 높이 2px 고려

        // 공통 차트 옵션
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
                mode: LightweightCharts.CrosshairMode.Normal,
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

        // 1. 가격 차트 생성 (상단 65%)
        this.priceChart = LightweightCharts.createChart(document.getElementById('priceChartContainer'), {
            ...commonOptions,
            height: priceChartHeight,
            rightPriceScale: {
                borderColor: '#dddddd',
                borderVisible: true,
                scaleMargins: {
                    top: 0.1,
                    bottom: 0.1
                },
                visible: true,
                autoScale: true
            }
        });

        // 2. 거래량 차트 생성 (하단 35%)
        this.volumeChart = LightweightCharts.createChart(document.getElementById('volumeChartContainer'), {
            ...commonOptions,
            height: volumeChartHeight,
            rightPriceScale: {
                borderColor: '#dddddd',
                borderVisible: true,
                scaleMargins: {
                    top: 0.1,
                    bottom: 0.1
                },
                visible: true,
                autoScale: true
            }
        });

        // 캔들스틱 시리즈 추가 (가격 차트)
        this.candlestickSeries = this.priceChart.addCandlestickSeries({
            upColor: '#ff3333', 
            downColor: '#5050ff',
            borderVisible: false, 
            wickUpColor: '#ff3333', 
            wickDownColor: '#5050ff',
            priceFormat: { type: 'price', precision: 0, minMove: 1 }
        });

        // 거래량 시리즈 추가 (거래량 차트)
        this.volumeSeries = this.volumeChart.addHistogramSeries({
            color: '#26a69a',
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume',
            scaleMargins: {
                top: 0.1,
                bottom: 0.1
            }
        });

        // 차트 싱크 설정
        this.syncCharts();
        this.setupCrosshairSync();
    }

    // 차트 동기화 설정
    syncCharts() {
        // 시간 스케일(가로축) 동기화
        this.priceChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
            if (timeRange && !this.isSyncing) {
                this.isSyncing = true;
                this.volumeChart.timeScale().setVisibleLogicalRange(timeRange);
                this.isSyncing = false;
            }
        });

        this.volumeChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
            if (timeRange && !this.isSyncing) {
                this.isSyncing = true;
                this.priceChart.timeScale().setVisibleLogicalRange(timeRange);
                this.isSyncing = false;
            }
        });
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

        // 윈도우 리사이즈 시 차트 크기 조정
        window.addEventListener('resize', this.handleResize.bind(this));
        
        // 초기 리사이즈 실행
        this.handleResize();

        const stockOption = stockSelect.options[stockSelect.selectedIndex];
        this.stockInfo = stockOption.textContent;
    }

    // 차트 크기 조정 처리
    handleResize() {
        if (!this.priceChart || !this.volumeChart) return;
        
        const chartWidth = this.chartContainer.clientWidth;
        const totalHeight = this.chartContainer.clientHeight;
        const priceChartHeight = Math.floor(totalHeight * 0.65);
        const volumeChartHeight = Math.floor(totalHeight * 0.35) - 2; // 구분선 높이 2px 고려
        
        // 차트 크기 조정
        this.priceChart.resize(chartWidth, priceChartHeight);
        this.volumeChart.resize(chartWidth, volumeChartHeight);
        
        console.log(`차트 크기 조정: ${chartWidth}x${totalHeight} (가격: ${priceChartHeight}, 거래량: ${volumeChartHeight})`);
    }

    async fetchChartData() {
        console.log('차트 데이터 요청 시도:', this.stockCode);
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

            if (!response.ok) {
                console.error('차트 데이터 fetch 실패:', response.status, response.statusText);
                this.candlestickSeries.setData([]);
                this.volumeSeries.setData([]);
                this.dataMap.clear();
                this.latestData = null;
                return;
            }

            const data = await response.json();
            console.log('Received data:', data);

            let chartData;
            switch(this.chartType) {
                case 'monthly': chartData = data.stk_mth_pole_chart_qry; break;
                case 'daily': chartData = data.stk_dt_pole_chart_qry; break;
                case 'weekly': chartData = data.stk_stk_pole_chart_qry; break;
                case 'yearly': chartData = data.stk_yr_pole_chart_qry; break;
                case 'minute': chartData = data.stk_min_pole_chart_qry || data.stk_stk_pole_chart_qry; break;
                default: chartData = data.stk_dt_pole_chart_qry;
            }

            if (chartData && chartData.length > 0) {
                const processedData = [];
                
                // 데이터 처리
                for (const item of chartData) {
                    // 날짜/시간 처리
                    let dateStr = (this.chartType === 'minute') ? item.cntr_tm : (item.dt || item.trd_dt);
                    if (!dateStr) continue;

                    // 날짜 생성
                    let timestamp;
                    try {
                        if (this.chartType === 'yearly' && dateStr.length === 4) {
                            timestamp = new Date(parseInt(dateStr), 0, 1).getTime() / 1000;
                        } else if (this.chartType === 'minute' && dateStr.length === 14) {
                            timestamp = new Date(
                                parseInt(dateStr.slice(0,4)),
                                parseInt(dateStr.slice(4,6))-1,
                                parseInt(dateStr.slice(6,8)),
                                parseInt(dateStr.slice(8,10)),
                                parseInt(dateStr.slice(10,12))
                            ).getTime() / 1000;
                        } else if (dateStr.length === 8) {
                            timestamp = new Date(
                                parseInt(dateStr.slice(0,4)),
                                parseInt(dateStr.slice(4,6))-1,
                                parseInt(dateStr.slice(6,8))
                            ).getTime() / 1000;
                        } else {
                            console.log('Invalid date format:', dateStr);
                            continue;
                        }
                    } catch (e) {
                        console.log('Date parsing error:', e, dateStr);
                        continue;
                    }

                    if (isNaN(timestamp)) {
                        console.log('Invalid timestamp for date:', dateStr);
                        continue;
                    }

                    // 가격 데이터 처리 (분봉일 때만 절대값 적용)
                    let close = parseFloat(item.cur_prc || item.clos_prc);
                    let open = parseFloat(item.open_pric || item.open_prc);
                    let high = parseFloat(item.high_pric || item.high_prc);
                    let low = parseFloat(item.low_pric || item.low_prc);
                    let volume = parseFloat(item.trde_qty || item.trd_qty) || 0;

                    if (this.chartType === 'minute') {
                        close = Math.abs(close);
                        open = Math.abs(open);
                        high = Math.abs(high);
                        low = Math.abs(low);
                        volume = Math.abs(volume);
                    }

                    // NaN 값 처리
                    if (isNaN(close)) continue;
                    if (isNaN(open)) open = close;
                    if (isNaN(high)) high = Math.max(close, open);
                    if (isNaN(low)) low = Math.min(close, open);

                    processedData.push({
                        time: timestamp,
                        open, high, low, close, volume
                    });
                }

                if (processedData.length > 0) {
                    // 시간순 정렬
                    processedData.sort((a, b) => a.time - b.time);
                    
                    // 캔들스틱 데이터
                    const candlestickData = processedData.map(({ time, open, high, low, close }) => ({
                        time, open, high, low, close
                    }));
                    
                    // 거래량 데이터 - 색상 설정 (상승 빨강, 하락 파랑)
                    const volumeData = processedData.map(({ time, volume, open, close }) => ({
                        time,
                        value: volume,
                        color: close >= open ? '#ff3333' : '#5050ff'  // 상승(빨강), 하락(파랑)
                    }));
                    
                    // 데이터 설정
                    this.candlestickSeries.setData(candlestickData);
                    this.volumeSeries.setData(volumeData);
                    
                    // 차트 타입에 맞게 옵션 업데이트
                    this.updateChartOptionsForType();
                    
                    // 차트 스케일 조정 (두 차트 모두)
                    this.priceChart.timeScale().fitContent();
                    this.volumeChart.timeScale().fitContent();
                    
                    // 데이터 맵 저장 (정보 패널용)
                    this.dataMap = new Map(processedData.map(d => [d.time, d]));
                    this.latestData = processedData[processedData.length - 1];
                    
                    // 정보 패널 업데이트
                    this.updateInfoPanel(null);
                    
                    return;
                }
            }
            
            // 유효한 데이터가 없는 경우
            console.error('No valid chart data found');
            this.candlestickSeries.setData([]);
            this.volumeSeries.setData([]);
            this.dataMap.clear();
            this.latestData = null;
            
        } catch (error) {
            console.error('차트 데이터 fetch 에러:', error);
            this.candlestickSeries.setData([]);
            this.volumeSeries.setData([]);
            this.dataMap.clear();
            this.latestData = null;
        }
    }

    // 차트 타입에 따른 옵션 업데이트 함수 
    updateChartOptionsForType() {
        const timeScaleOptions = {
            timeVisible: this.chartType === 'minute',
            secondsVisible: false
        };

        // 두 차트 모두 옵션 업데이트
        this.priceChart.applyOptions({ 
            timeScale: timeScaleOptions
        });
        this.volumeChart.applyOptions({ 
            timeScale: timeScaleOptions
        });
    }

    // 정보 패널 업데이트 로직
    updateInfoPanel = (time) => {
        let displayTime = time;
        let dataPoint = null;

        if (displayTime === null && this.latestData) { // 마우스 벗어남 -> 최신 데이터 사용
            displayTime = this.latestData.time;
        }

        if (displayTime !== null) {
            dataPoint = this.dataMap.get(displayTime); // Map에서 데이터 조회
        }

        // 데이터 없으면 패널 숨김
        if (!dataPoint) {
            document.getElementById('stockInfoPanel').style.display = 'none';
            document.getElementById('volumeInfoPanel').style.display = 'none';
            return;
        }

        const date = new Date(dataPoint.time * 1000);
        let dateStr = this.formatDateForDisplay(date);
        const volumeValue = dataPoint.volume ?? 0;

        // 유효성 검사
        if (isNaN(dataPoint.open) || isNaN(dataPoint.high) || isNaN(dataPoint.low) || isNaN(dataPoint.close) || isNaN(volumeValue)) {
            document.getElementById('stockInfoPanel').style.display = 'none';
            document.getElementById('volumeInfoPanel').style.display = 'none';
            return;
        }

        const priceChange = dataPoint.close - dataPoint.open;
        const priceChangePercent = dataPoint.open === 0 ? 0 : (priceChange / dataPoint.open * 100);
        const priceDirection = priceChange >= 0 ? 'up' : 'down';
        const sign = priceChange >= 0 ? '+' : '';
        const color = priceDirection === 'up' ? '#ff3333' : '#5050ff'; // 빨강/파랑

        // 패널 업데이트
        let stockCodeName = this.stockInfo || this.stockCode;
        document.getElementById('stockInfoPanel').innerHTML = `
            <span style="font-weight: bold;">${stockCodeName}</span> <span style="font-size: 10px;">${dateStr}</span><br>
            <span>시가 <span style="color: ${color};">${this.formatNumber(dataPoint.open)}</span></span>
            <span style="margin-left: 5px;">고가 <span style="color: ${color};">${this.formatNumber(dataPoint.high)}</span></span>
            <span style="margin-left: 5px;">저가 <span style="color: ${color};">${this.formatNumber(dataPoint.low)}</span></span>
            <span style="margin-left: 5px;">종가 <span style="color: ${color};">${this.formatNumber(dataPoint.close)}</span></span>
            <span style="color: ${color}; margin-left: 5px;">(${sign}${this.formatNumber(priceChange)} ${sign}${priceChangePercent.toFixed(2)}%)</span>
        `;
        document.getElementById('volumeInfoPanel').innerHTML = `
            거래량 <span style="color: ${color};">${this.formatVolume(volumeValue)}</span>
        `;

        document.getElementById('stockInfoPanel').style.display = 'block';
        document.getElementById('volumeInfoPanel').style.display = 'block';
    };

    // 크로스헤어 동기화 및 정보 패널 업데이트 로직
    setupCrosshairSync() {
        // 크로스헤어 동기화 (두 차트 간)
        this.priceChart.subscribeCrosshairMove(param => {
            if (!param.point || !param.time) {
                this.volumeChart.clearCrosshairPosition();
                
                if (!param.point) {
                    // 마우스가 차트 영역을 벗어나면 최신 데이터 표시
                    this.updateInfoPanel(null);
                }
                return;
            }
            
            // 거래량 차트 크로스헤어 동기화
            this.volumeChart.setCrosshairPosition(param.point, param.time);
            
            // 정보 패널 업데이트
            this.updateInfoPanel(param.time);
        });
        
        this.volumeChart.subscribeCrosshairMove(param => {
            if (!param.point || !param.time) {
                this.priceChart.clearCrosshairPosition();
                return;
            }
            
            // 가격 차트 크로스헤어 동기화
            this.priceChart.setCrosshairPosition(param.point, param.time);
            
            // 정보 패널 업데이트
            this.updateInfoPanel(param.time);
        });
        
        // 마우스가 차트 컨테이너를 벗어날 때 처리
        this.chartContainer.addEventListener('mouseleave', () => {
            this.updateInfoPanel(null);
        });
    }
}

let topVolumeData = [];
let currentPage = 1;
const pageSize = 10;

async function loadTopVolumeStocks() {
    try {
        const response = await fetch('/api/stock/top-volume');
        const data = await response.json();
        topVolumeData = data.tdy_trde_qty_upper || [];
        currentPage = 1;
        renderTopVolumeTable();
        renderPagination();
    } catch (error) {
        console.error('거래량 상위 종목 조회 실패:', error);
    }
}

function renderTopVolumeTable() {
    const tableBody = document.querySelector('#topVolumeTable tbody');
    tableBody.innerHTML = '';
    const startIdx = (currentPage - 1) * pageSize;
    const pageData = topVolumeData.slice(startIdx, startIdx + pageSize);

    pageData.forEach((stock, idx) => {
        const tr = document.createElement('tr');
        const currentPrice = Math.abs(Number(stock.cur_prc)).toLocaleString();
        tr.innerHTML = `
            <td>${startIdx + idx + 1}</td>
            <td>${stock.stk_nm}</td>
            <td>${currentPrice}</td>
            <td class="${parseFloat(stock.flu_rt) >= 0 ? 'up' : 'down'}">
                ${stock.flu_rt}%
            </td>
        `;
        tr.addEventListener('click', () => {
            console.log('종목 클릭:', stock.stk_cd);
            document.querySelector('.top-volume-section').style.display = 'none';
            document.querySelector('.chart').style.display = 'block';
            document.getElementById('stockSelector').value = stock.stk_cd;
            if (!window.stockChart) {
                window.stockChart = new StockChart(stock.stk_cd);
            } else {
                window.stockChart.stockCode = stock.stk_cd;
                window.stockChart.fetchChartData();
            }
            addBackButton();
        });
        tableBody.appendChild(tr);
    });
}

function renderPagination() {
    const pagination = document.getElementById('topVolumePagination');
    pagination.innerHTML = '';
    const totalPages = Math.max(1, Math.ceil(topVolumeData.length / pageSize)); // 최소 1페이지

    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + 4);
    if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
    }

    // 이전 페이지 버튼
    const prevBtn = document.createElement('button');
    prevBtn.textContent = '◀';
    prevBtn.className = 'page-btn';
    prevBtn.disabled = currentPage === 1;
    prevBtn.onclick = () => {
        if (currentPage > 1) {
            currentPage--;
            renderTopVolumeTable();
            renderPagination();
        }
    };
    pagination.appendChild(prevBtn);

    // 페이지 번호 버튼
    for (let i = startPage; i <= endPage; i++) {
        const pageBtn = document.createElement('button');
        pageBtn.textContent = i;
        pageBtn.className = 'page-btn';
        if (i === currentPage) pageBtn.classList.add('active');
        pageBtn.onclick = () => {
            currentPage = i;
            renderTopVolumeTable();
            renderPagination();
        };
        pagination.appendChild(pageBtn);
    }

    // 다음 페이지 버튼
    const nextBtn = document.createElement('button');
    nextBtn.textContent = '▶';
    nextBtn.className = 'page-btn';
    nextBtn.disabled = currentPage === totalPages;
    nextBtn.onclick = () => {
        if (currentPage < totalPages) {
            currentPage++;
            renderTopVolumeTable();
            renderPagination();
        }
    };
    pagination.appendChild(nextBtn);
}

// 페이지 로드 시 거래량 상위 종목만 로드 (차트 인스턴스 생성 X)
document.addEventListener('DOMContentLoaded', () => {
    loadTopVolumeStocks();
    // 1분마다 거래량 상위 종목 갱신
    setInterval(loadTopVolumeStocks, 60000);
    // window.stockChart = new StockChart(); // 이 부분 삭제 또는 주석처리
});

// 차트 상단에 뒤로가기 버튼 추가 함수
function addBackButton() {
    const chartHeader = document.querySelector('.chart-header');
    if (!chartHeader) return;
    if (document.getElementById('backToTableBtn')) return; // 중복 방지
    const backBtn = document.createElement('button');
    backBtn.id = 'backToTableBtn';
    backBtn.textContent = '← 뒤로가기';
    backBtn.style.marginRight = '10px';
    backBtn.style.padding = '4px 10px';
    backBtn.style.border = '1px solid #ddd';
    backBtn.style.background = '#fff';
    backBtn.style.borderRadius = '4px';
    backBtn.style.cursor = 'pointer';
    backBtn.onclick = () => {
        document.querySelector('.top-volume-section').style.display = 'block';
        document.querySelector('.chart').style.display = 'none';
    };
    chartHeader.insertBefore(backBtn, chartHeader.firstChild);
} 