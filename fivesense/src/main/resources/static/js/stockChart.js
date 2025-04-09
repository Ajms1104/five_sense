document.addEventListener('DOMContentLoaded', function() {
    // 차트 초기화
    const ctx = document.getElementById('stockChart').getContext('2d');
    const stockChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '주가',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1,
                borderWidth: 2,
                fill: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: {
                    top: 10,
                    right: 10,
                    bottom: 10,
                    left: 10
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: '시간'
                    },
                    grid: {
                        display: false
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: '가격'
                    },
                    grid: {
                        display: true
                    },
                    ticks: {
                        callback: function(value) {
                            return value.toLocaleString() + '원';
                        }
                    }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.parsed.y.toLocaleString() + '원';
                        }
                    }
                }
            }
        }
    });

    let stompClient = null;
    let currentStockCode = '005930'; // 기본값: 삼성전자
    const maxDataPoints = 30; // 차트에 표시할 최대 데이터 포인트 수
    let priceHistory = []; // 가격 기록을 저장하는 배열

    // TR ID 입력값 가져오기
    function getTrIds() {
        return {
            realtime: document.getElementById('realtimeTrId').value,
            price: document.getElementById('priceTrId').value
        };
    }

    // 웹소켓 연결 함수
    function connect() {
        const socket = new SockJS('/stock-websocket');
        stompClient = Stomp.over(socket);
        stompClient.connect({}, function() {
            subscribeToStock(currentStockCode);
            console.log('웹소켓 연결 성공!');
        }, function(error) {
            console.error('웹소켓 연결 실패:', error);
            setTimeout(connect, 5000); // 5초 후 재연결 시도
        });
    }

    // 특정 주식 구독 함수
    function subscribeToStock(stockCode) {
        if (stompClient) {
            const trIds = getTrIds();
            
            // 새 주식 구독
            stompClient.subscribe('/topic/stock/' + stockCode, function(message) {
                updateChart(JSON.parse(message.body));
            });
            
            currentStockCode = stockCode;
            
            // 차트 초기화
            stockChart.data.labels = [];
            stockChart.data.datasets[0].data = [];
            stockChart.update();
            
            // 서버에 구독 요청 전송 (TR ID 포함)
            fetch('/api/stock/subscribe/' + stockCode, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    trId: trIds.realtime
                })
            });
            
            // 초기 데이터 로드
            fetchInitialData(stockCode);
        }
    }

    // 초기 데이터 가져오기
    function fetchInitialData(stockCode) {
        const trIds = getTrIds();
        fetch('/api/stock/price/' + stockCode + '?trId=' + trIds.price)
            .then(response => response.json())
            .then(data => {
                console.log('Initial data:', data);
                if (data.output && data.output.현재가) {
                    const now = new Date();
                    stockChart.data.labels.push(now.toLocaleTimeString());
                    stockChart.data.datasets[0].data.push(parseFloat(data.output.현재가));
                    stockChart.update();
                }
            })
            .catch(error => console.error('데이터 로드 실패:', error));
    }

    // 차트 업데이트 함수
    function updateChart(data) {
        if (!data || !data.data || !data.data[0] || !data.data[0].values) {
            console.log('Invalid data received:', data);
            return;
        }

        const now = new Date();
        const timeStr = now.toLocaleTimeString();
        
        // 키움 API 응답 데이터에서 현재가 추출
        const currentPrice = parseFloat(data.data[0].values["20"]);
        if (isNaN(currentPrice)) {
            console.log('Invalid price data:', data.data[0].values["20"]);
            return;
        }
        
        // 가격 기록에 추가
        priceHistory.push(currentPrice);
        
        // 새 데이터 추가
        stockChart.data.labels.push(timeStr);
        stockChart.data.datasets[0].data.push(currentPrice);
        
        // 최대 포인트 수를 초과하면 오래된 데이터 제거
        if (stockChart.data.labels.length > maxDataPoints) {
            stockChart.data.labels.shift();
            stockChart.data.datasets[0].data.shift();
            priceHistory.shift();
        }
        
        // y축 범위 동적 조정
        const minPrice = Math.min(...priceHistory);
        const maxPrice = Math.max(...priceHistory);
        const priceRange = maxPrice - minPrice;
        const padding = priceRange * 0.1; // 10% 패딩
        
        stockChart.options.scales.y.min = minPrice - padding;
        stockChart.options.scales.y.max = maxPrice + padding;
        
        stockChart.update();
    }

    // 주식 선택 변경 이벤트 처리
    document.getElementById('stockSelect').addEventListener('change', function() {
        const selectedStock = this.value;
        subscribeToStock(selectedStock);
    });

    // 웹소켓 연결 시작
    connect();
}); 