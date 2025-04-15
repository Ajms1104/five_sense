class StockChart {
    constructor() {
        this.stockCode = '005930';
        this.chart = null;
        this.fullData = [];
        this.visibleDataCount = 60;
        this.currentStartIndex = 0;
        this.chartType = 'daily';
        this.init();
    }

    init() {
        console.log('Initializing StockChart...');
        this.createChart();
        this.setupEventListeners();
        this.fetchChartData();
    }

    createChart() {
        console.log('Creating chart...');
        const ctx = document.getElementById('stockChart').getContext('2d');
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: '주가',
                    data: [],
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1,
                    fill: false,
                    pointRadius: 2,
                    pointHoverRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: false,
                        ticks: {
                            callback: function(value) {
                                return value.toLocaleString() + '원';
                            }
                        }
                    },
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                            maxTicksLimit: 20
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.parsed.y.toLocaleString() + '원';
                            },
                            title: (context) => {
                                const dateStr = context[0].label;
                                switch(this.chartType) {
                                    case 'yearly':
                                        return dateStr.substring(0, 4) + '년';
                                    case 'monthly':
                                        return dateStr.substring(0, 4) + '년 ' + dateStr.substring(4, 6) + '월';
                                    default:
                                        return dateStr.substring(0, 4) + '년 ' + 
                                               dateStr.substring(4, 6) + '월 ' + 
                                               dateStr.substring(6, 8) + '일';
                                }
                            }
                        }
                    },
                    zoom: {
                        pan: {
                            enabled: true,
                            mode: 'x'
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
    }

    setupEventListeners() {
        console.log('Setting up event listeners...');
        
        // 주식 선택 이벤트 리스너
        const stockSelect = document.getElementById('stockSelector');
        if (!stockSelect) {
            console.error('stockSelector element not found');
            return;
        }
        
        stockSelect.value = this.stockCode;
        stockSelect.addEventListener('change', (e) => {
            console.log('Stock changed to:', e.target.value);
            this.stockCode = e.target.value;
            this.fetchChartData();
        });

        // 차트 타입 버튼 이벤트 리스너
        const chartTypeBtns = document.querySelectorAll('.chart-type-btn');
        if (chartTypeBtns.length === 0) {
            console.error('chart-type-btn elements not found');
            return;
        }

        chartTypeBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const newType = e.target.dataset.type;
                console.log('Chart type changed to:', newType);
                
                // 모든 버튼에서 active 클래스 제거
                chartTypeBtns.forEach(b => b.classList.remove('active'));
                // 클릭된 버튼에 active 클래스 추가
                e.target.classList.add('active');
                
                this.chartType = newType;
                this.fetchChartData();
            });
        });
    }

    async fetchChartData() {
        try {
            let apiId;
            let dataField;
            switch(this.chartType) {
                case 'minute':
                    apiId = 'KA10080';
                    dataField = 'stk_min_pole_chart_qry';
                    break;
                case 'daily':
                    apiId = 'KA10081';
                    dataField = 'stk_dt_pole_chart_qry';
                    break;
                case 'weekly':
                    apiId = 'KA10082';
                    dataField = 'stk_wk_pole_chart_qry';
                    break;
                case 'monthly':
                    apiId = 'KA10083';
                    dataField = 'stk_mth_pole_chart_qry';
                    break;
                case 'yearly':
                    apiId = 'KA10094';
                    dataField = 'stk_yr_pole_chart_qry';
                    break;
                default:
                    apiId = 'KA10081';
                    dataField = 'stk_dt_pole_chart_qry';
            }

            console.log('Fetching chart data...', {
                stockCode: this.stockCode,
                chartType: this.chartType,
                apiId: apiId,
                dataField: dataField
            });

            const response = await fetch(`/api/stock/daily-chart/${this.stockCode}?apiId=${apiId}`);
            const data = await response.json();
            console.log('Received data:', data);
            
            if (data[dataField]) {
                const chartData = data[dataField];
                console.log('Chart data length:', chartData.length);
                
                chartData.sort((a, b) => a.dt.localeCompare(b.dt));
                
                const labels = chartData.map(item => item.dt);
                const prices = chartData.map(item => parseFloat(item.cur_prc));
                console.log('Processed data:', {
                    labels: labels,
                    prices: prices
                });
                
                // 차트 데이터 업데이트
                this.chart.data.labels = labels;
                this.chart.data.datasets[0].data = prices;
                
                // y축 범위 설정
                const minPrice = Math.min(...prices);
                const maxPrice = Math.max(...prices);
                const padding = (maxPrice - minPrice) * 0.1;
                
                this.chart.options.scales.y.min = minPrice - padding;
                this.chart.options.scales.y.max = maxPrice + padding;
                
                // 차트 업데이트
                this.chart.resize();
                this.chart.update();
                console.log('Chart updated successfully');
            } else {
                console.error('No chart data found in response for field:', dataField);
            }
        } catch (error) {
            console.error('Error fetching chart data:', error);
        }
    }
}

// 차트 초기화
console.log('DOM Content Loaded');
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing StockChart...');
    new StockChart();
}); 