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
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: '시간'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: '가격'
                    }
                }
            }
        }
    });

    let stompClient = null;
    let currentStockCode = '005930'; // 기본값: 삼성전자
    const maxDataPoints = 20; // 차트에 표시할 최대 데이터 포인트 수

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
                if (data.price) {
                    const now = new Date();
                    stockChart.data.labels.push(now.toLocaleTimeString());
                    stockChart.data.datasets[0].data.push(data.price);
                    stockChart.update();
                }
            })
            .catch(error => console.error('데이터 로드 실패:', error));
    }

    // 차트 업데이트 함수
    function updateChart(data) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString();
        
        // 새 데이터 추가
        stockChart.data.labels.push(timeStr);
        stockChart.data.datasets[0].data.push(data.price);
        
        // 최대 포인트 수를 초과하면 오래된 데이터 제거
        if (stockChart.data.labels.length > maxDataPoints) {
            stockChart.data.labels.shift();
            stockChart.data.datasets[0].data.shift();
        }
        
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