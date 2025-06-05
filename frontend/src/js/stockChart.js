import { createChart, CrosshairMode } from 'lightweight-charts';

class StockChart {
    constructor() {
        this.chartContainer = document.getElementById('chartContainer');
        this.stockCode = '005930'; // 기본값
        this.chartType = 'daily';   // 기본값
        this.minuteType = '1';      // 분봉 타입
        this.stockInfo = '';
        this.dataMap = new Map();
        this.latestData = null;
        this.isSyncing = false;

        this.createChart();
        this.setupEventListeners();
        this.fetchChartData();
    }

    createChart() {
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

        const containerWidth = this.chartContainer.clientWidth;
        const priceChartHeight = Math.floor(this.chartContainer.clientHeight * 0.65);
        const volumeChartHeight = Math.floor(this.chartContainer.clientHeight * 0.35) - 2;

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
                secondsVisible: false,
                tickMarkFormatter: (time) => {
                    const date = new Date(time * 1000);
                    return this.formatDateForDisplay(date);
                }
            },
            handleScroll: true,
            handleScale: true
        };

        this.priceChart = createChart(document.getElementById('priceChartContainer'), {
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

        this.volumeChart = createChart(document.getElementById('volumeChartContainer'), {
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

        this.candlestickSeries = this.priceChart.addCandlestickSeries({
            upColor: '#ff3333',
            downColor: '#5050ff',
            borderVisible: false,
            wickUpColor: '#ff3333',
            wickDownColor: '#5050ff',
            priceFormat: { type: 'price', precision: 0 }
        });

        this.volumeSeries = this.volumeChart.addHistogramSeries({
            color: '#26a69a',
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume',
            scaleMargins: { top: 0.1, bottom: 0.1 }
        });

        this.syncCharts();
        this.setupCrosshairSync();
        window.addEventListener('resize', this.handleResize.bind(this));
    }

    syncCharts() {
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

    formatDateForDisplay(date) {
        switch (this.chartType) {
            case 'yearly': return date.getFullYear().toString();
            case 'monthly': return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}`;
            case 'weekly':
            case 'daily': return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
            case 'minute': return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
            default: return date.toLocaleDateString('ko-KR');
        }
    }

    setupEventListeners() {
        // 종목 선택
        const stockSelect = document.getElementById('stockSelector');
        if (stockSelect) {
            stockSelect.value = this.stockCode;
            stockSelect.addEventListener('change', (e) => {
                this.stockCode = e.target.value;
                const stockOption = stockSelect.options[stockSelect.selectedIndex];
                this.stockInfo = stockOption.textContent;
                this.fetchChartData();
            });
        }

        // 분봉 선택
        const minuteSelect = document.getElementById('minuteSelector');
        if (minuteSelect) {
            minuteSelect.addEventListener('change', (e) => {
                this.minuteType = e.target.value;
                this.fetchChartData();
            });
        }

        // 차트 타입 버튼
        const chartTypeBtns = document.querySelectorAll('.chart-type-btn');
        chartTypeBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const newType = e.target.dataset.type;
                chartTypeBtns.forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.chartType = newType;
                if (minuteSelect) minuteSelect.style.display = (newType === 'minute') ? 'block' : 'none';
                this.fetchChartData();
            });
        });

        window.addEventListener('resize', this.handleResize.bind(this));
        this.handleResize();
    }

    handleResize() {
        if (!this.priceChart || !this.volumeChart) return;
        const chartWidth = this.chartContainer.clientWidth;
        const totalHeight = this.chartContainer.clientHeight;
        const priceChartHeight = Math.floor(totalHeight * 0.65);
        const volumeChartHeight = Math.floor(totalHeight * 0.35) - 2;
        this.priceChart.resize(chartWidth, priceChartHeight);
        this.volumeChart.resize(chartWidth, volumeChartHeight);
    }

    async fetchChartData() {
        try {
            let apiId;
            let requestData = { stk_cd: this.stockCode, upd_stkpc_tp: "1" };
            switch (this.chartType) {
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
            let chartData;
            switch (this.chartType) {
                case 'monthly': chartData = data.stk_mth_pole_chart_qry; break;
                case 'daily': chartData = data.stk_dt_pole_chart_qry; break;
                case 'weekly': chartData = data.stk_stk_pole_chart_qry; break;
                case 'yearly': chartData = data.stk_yr_pole_chart_qry; break;
                case 'minute': chartData = data.stk_min_pole_chart_qry || data.stk_stk_pole_chart_qry; break;
                default: chartData = data.stk_dt_pole_chart_qry;
            }

            if (chartData && chartData.length > 0) {
                const processedData = [];
                for (const item of chartData) {
                    let dateStr = (this.chartType === 'minute') ? item.cntr_tm : (item.dt || item.trd_dt);
                    if (!dateStr) continue;
                    let timestamp;
                    try {
                        if (this.chartType === 'yearly' && dateStr.length === 4) {
                            timestamp = new Date(parseInt(dateStr), 0, 1).getTime() / 1000;
                        } else if (this.chartType === 'minute' && dateStr.length === 14) {
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

                if (processedData.length > 0) {
                    processedData.sort((a, b) => a.time - b.time);
                    const candlestickData = processedData.map(({ time, open, high, low, close }) => ({ time, open, high, low, close }));
                    const volumeData = processedData.map(({ time, volume, open, close }) => ({
                        time,
                        value: volume,
                        color: close >= open ? '#ff3333' : '#5050ff'
                    }));

                    // 여기서 setData로 차트 갱신!
                    this.candlestickSeries.setData(candlestickData);
                    this.volumeSeries.setData(volumeData);
                    this.updateChartOptionsForType();
                    this.priceChart.timeScale().fitContent();
                    this.volumeChart.timeScale().fitContent();
                    this.dataMap = new Map(processedData.map(d => [d.time, d]));
                    this.latestData = processedData[processedData.length - 1];
                    this.updateInfoPanel(null);
                    return;
                }
            }
            // 데이터 없음
            this.candlestickSeries.setData([]);
            this.volumeSeries.setData([]);
            this.dataMap.clear();
            this.latestData = null;
        } catch (error) {
            this.candlestickSeries.setData([]);
            this.volumeSeries.setData([]);
            this.dataMap.clear();
            this.latestData = null;
        }
    }

    updateChartOptionsForType() {
        const timeScaleOptions = {
            timeVisible: this.chartType === 'minute',
            secondsVisible: false
        };
        this.priceChart.applyOptions({ timeScale: timeScaleOptions });
        this.volumeChart.applyOptions({ timeScale: timeScaleOptions });
    }

    updateInfoPanel = (time) => {
        let displayTime = time;
        let dataPoint = null;
        if (displayTime === null && this.latestData) displayTime = this.latestData.time;
        if (displayTime !== null) dataPoint = this.dataMap.get(displayTime);
        if (!dataPoint) {
            document.getElementById('stockInfoPanel').style.display = 'none';
            document.getElementById('volumeInfoPanel').style.display = 'none';
            return;
        }

        const date = new Date(dataPoint.time * 1000);
        let dateStr = this.formatDateForDisplay(date);
        const volumeValue = dataPoint.volume ?? 0;
        if (isNaN(dataPoint.open) || isNaN(dataPoint.high) || isNaN(dataPoint.low) || isNaN(dataPoint.close) || isNaN(volumeValue)) {
            document.getElementById('stockInfoPanel').style.display = 'none';
            document.getElementById('volumeInfoPanel').style.display = 'none';
            return;
        }

        const priceChange = dataPoint.close - dataPoint.open;
        const priceChangePercent = dataPoint.open === 0 ? 0 : (priceChange / dataPoint.open * 100);
        const priceDirection = priceChange >= 0 ? 'up' : 'down';
        const sign = priceChange >= 0 ? '+' : '';
        const color = priceDirection === 'up' ? '#ff3333' : '#5050ff';
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

    setupCrosshairSync() {
        this.priceChart.subscribeCrosshairMove(param => {
            if (!param.point || !param.time) {
                this.volumeChart.clearCrosshairPosition();
                if (!param.point) this.updateInfoPanel(null);
                return;
            }
            this.volumeChart.setCrosshairPosition(param.point, param.time);
            this.updateInfoPanel(param.time);
        });

        this.volumeChart.subscribeCrosshairMove(param => {
            if (!param.point || !param.time) {
                this.priceChart.clearCrosshairPosition();
                return;
            }
            this.priceChart.setCrosshairPosition(param.point, param.time);
            this.updateInfoPanel(param.time);
        });

        this.chartContainer.addEventListener('mouseleave', () => {
            this.updateInfoPanel(null);
        });
    }

    formatNumber(num) {
        return num?.toLocaleString('ko-KR') ?? '-';
    }

    formatVolume(vol) {
        if (vol >= 1e8) return (vol / 1e8).toFixed(2) + '억';
        if (vol >= 1e4) return (vol / 1e4).toFixed(2) + '만';
        return vol?.toLocaleString('ko-KR') ?? '-';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new StockChart();
});
