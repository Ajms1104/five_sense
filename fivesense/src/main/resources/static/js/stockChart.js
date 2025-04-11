class StockChart {
    constructor() {
        this.stockCode = '005930';
        this.chart = null;
        this.fullData = []; // 전체 데이터 저장
        this.visibleDataCount = 60; // 처음에 표시할 데이터 수
        this.currentStartIndex = 0; // 현재 보여지는 데이터의 시작 인덱스
        this.init();
    }

    init() {
        this.createChart();
        this.setupEventListeners();
        this.fetchDailyChart(this.stockCode);
    }

    createChart() {
        const ctx = document.getElementById('stockChart').getContext('2d');
        this.chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: '주가',
                    data: [],
                    backgroundColor: 'rgba(53, 162, 235, 0.5)',
                    borderColor: 'rgb(53, 162, 235)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: false,
                maintainAspectRatio: false,
                animation: false,
                layout: {
                    padding: {
                        left: 10,
                        right: 10,
                        top: 20,
                        bottom: 10
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        },
                        ticks: {
                            callback: function(value) {
                                return value.toLocaleString() + '원';
                            },
                            font: {
                                size: 10
                            }
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                            autoSkip: true,
                            maxTicksLimit: 20,
                            font: {
                                size: 9
                            }
                        },
                        barPercentage: 0.8,
                        categoryPercentage: 0.9
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.parsed.y.toLocaleString() + '원';
                            }
                        }
                    },
                    legend: {
                        display: false
                    },
                    zoom: {
                        pan: {
                            enabled: true,
                            mode: 'x',
                            onPanComplete: (ctx) => {
                                this.handlePanComplete(ctx);
                            }
                        },
                        zoom: {
                            wheel: {
                                enabled: true
                            },
                            pinch: {
                                enabled: true
                            },
                            mode: 'x'
                        }
                    }
                }
            }
        });

        // 차트 리셋 버튼 추가
        const resetButton = document.createElement('button');
        resetButton.textContent = '차트 초기화';
        resetButton.style.position = 'absolute';
        resetButton.style.top = '10px';
        resetButton.style.left = '10px';
        resetButton.style.padding = '5px 10px';
        resetButton.style.fontSize = '12px';
        resetButton.style.backgroundColor = '#f0f0f0';
        resetButton.style.border = '1px solid #ddd';
        resetButton.style.borderRadius = '4px';
        resetButton.style.cursor = 'pointer';
        resetButton.style.zIndex = '10';
        resetButton.addEventListener('click', () => {
            this.chart.resetZoom();
            this.currentStartIndex = Math.max(0, this.fullData.length - this.visibleDataCount);
            this.updateChartWithVisibleData();
        });
        
        const chartWrapper = document.querySelector('.chart-wrapper');
        chartWrapper.appendChild(resetButton);
    }

    setupEventListeners() {
        // HTML의 주식 선택 드롭다운을 연결
        const stockSelect = document.getElementById('stockSelector');
        stockSelect.value = this.stockCode;
        stockSelect.addEventListener('change', (e) => {
            this.stockCode = e.target.value;
            this.fetchDailyChart(this.stockCode);
        });
    }

    handlePanComplete(ctx) {
        // 차트의 X축 시작과 끝 인덱스 확인
        const chartArea = this.chart.chartArea;
        const xAxis = this.chart.scales.x;
        
        // 차트 왼쪽 끝의 데이터 인덱스 (가장 과거 데이터)
        const leftEdgeIndex = Math.floor(xAxis.getValueForPixel(chartArea.left) || 0);
        
        // 차트 오른쪽 끝의 데이터 인덱스 (가장 최근 데이터)
        const rightEdgeIndex = Math.ceil(xAxis.getValueForPixel(chartArea.right) || this.visibleDataCount - 1);
        
        // 왼쪽으로 드래그하여 과거 데이터를 요청하는 경우
        if (leftEdgeIndex <= 2) {  // 왼쪽 여백 거의 없을 때
            this.loadMorePastData();
        }
        
        // 오른쪽으로 드래그하여 최신 데이터를 요청하는 경우
        if (rightEdgeIndex >= this.chart.data.labels.length - 3) {  // 오른쪽 여백 거의 없을 때
            this.loadMoreRecentData();
        }
    }

    loadMorePastData() {
        if (this.currentStartIndex > 0) {
            // 더 많은 과거 데이터를 보여줌 (최대 30개 추가)
            const addCount = Math.min(30, this.currentStartIndex);
            this.currentStartIndex = Math.max(0, this.currentStartIndex - addCount);
            this.updateChartWithVisibleData();
        }
    }

    loadMoreRecentData() {
        const maxEndIndex = this.fullData.length;
        const currentEndIndex = this.currentStartIndex + this.visibleDataCount;
        
        if (currentEndIndex < maxEndIndex) {
            // 더 많은 최신 데이터를 보여줌 (최대 30개 추가)
            this.currentStartIndex = Math.min(this.currentStartIndex + 30, maxEndIndex - this.visibleDataCount);
            this.updateChartWithVisibleData();
        }
    }

    updateChartWithVisibleData() {
        if (this.fullData.length === 0) return;
        
        // 현재 보여질 데이터의 범위 계산
        const endIndex = Math.min(this.currentStartIndex + this.visibleDataCount, this.fullData.length);
        const visibleData = this.fullData.slice(this.currentStartIndex, endIndex);
        
        this.chart.data.labels = visibleData.map(item => item.label);
        this.chart.data.datasets[0].data = visibleData.map(item => item.price);
        
        // 모든 데이터의 최소/최대값을 기준으로 y축 설정 (전체 데이터셋 기준)
        const allPrices = this.fullData.map(item => item.price);
        const minPrice = Math.min(...allPrices);
        const maxPrice = Math.max(...allPrices);
        const priceRange = maxPrice - minPrice;
        const padding = priceRange * 0.1;
        
        this.chart.options.scales.y.min = minPrice - padding;
        this.chart.options.scales.y.max = maxPrice + padding;
        
        this.chart.update('none');
    }

    async fetchDailyChart(code) {
        try {
            const response = await fetch(`/api/stock/daily-chart/${code}`);
            const data = await response.json();
            
            if (data.stk_dt_pole_chart_qry) {
                const chartData = data.stk_dt_pole_chart_qry;
                // 데이터를 날짜순으로 정렬
                chartData.sort((a, b) => a.dt.localeCompare(b.dt));
                
                // 전체 데이터 저장
                this.fullData = chartData.map(item => {
                    // YYYYMMDD 형식을 MM/DD로 변환
                    const dateStr = item.dt;
                    const label = dateStr.substring(4, 6) + '/' + dateStr.substring(6, 8);
                    const price = parseFloat(item.cur_prc);
                    return { label, price, originalDate: item.dt };
                });
                
                // 처음에는 최신 데이터 60개만 표시 (시작 인덱스 계산)
                this.currentStartIndex = Math.max(0, this.fullData.length - this.visibleDataCount);
                this.updateChartWithVisibleData();
            }
        } catch (error) {
            console.error('일봉 차트 데이터 로드 실패:', error);
        }
    }
}

// 차트 초기화
document.addEventListener('DOMContentLoaded', () => {
    new StockChart();
}); 