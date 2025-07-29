import React, { useState, useEffect, useRef } from 'react';
import '../styles/main.css';

// 이미지 import
import LogoImg from '../assets/TEST5_high.png';
import SlideIcon from '../assets/Vector_3.svg';
import UserIcon from '../assets/user.svg';

// JS 함수 import
import { btcPriceFeed, ethPriceFeed, lrcPriceFeed } from './Profile.jsx';
import initStockChart from './StockChart.jsx';
import initChat from './Chat.jsx';

const Sidebar = () => {
  return (
    <section className="sidebar">
      <div className="sidebar_top">
        <div className="logo_top">
          <h1 className="logo_txt">FIVE_SENSE</h1>
          <img src={LogoImg} alt="logo" className="logo_png" />
          <img src={SlideIcon} alt="toggle" className="slide" />
        </div>
        <div className="menu">
          <h2 className="menu_font">메뉴</h2>
          <button className="ai_chat">🔎 AI Chat</button>
          <button className="bookmark">⭐ 즐겨찾기</button>
        </div>
      </div>
      <div className="sidebar_mid">
        <div className="history">
          <h2 className="history_font">검색 기록</h2>
          <button className="today_btn">오늘 ▼</button>
          <h3 className="line_1"></h3>
          <button className="dplus7_btn">7일 전 ▽</button>
        </div>
      </div>
      <div className="sidebar_bottom">
        <h2 className="post">최신 뉴스</h2>
        <div className="post_bg">{/* 뉴스 컨텐츠 */}</div>
      </div>
    </section>
  );
};

const TopBar = () => (
  <div className="top_bar">
    <img src={UserIcon} alt="user" className="user" />
  </div>
);

const StockChart = () => {
  const [chartType, setChartType] = useState('daily');
  const [minuteInterval, setMinuteInterval] = useState('1');
  const [stockCode, setStockCode] = useState('005930');
  const chartContainerRef = useRef(null);

  // 차트 초기화 / 업데이트
  useEffect(() => {
    initStockChart({
      type: chartType,
      minute: minuteInterval,
      stock: stockCode,
      container: chartContainerRef.current
    });
  }, [chartType, minuteInterval, stockCode]);

  const types = [
    { key: 'minute', label: '분' },
    { key: 'daily', label: '일' },
    { key: 'weekly', label: '주' },
    { key: 'monthly', label: '월' },
    { key: 'yearly', label: '년' }
  ];

  return (
    <section className="stockChart">
      <div className="chart">
        <div className="chart-header">
          <p className="chart-title">주식 차트</p>
          <div className="chart-controls">
            {types.map((t) => (
              <React.Fragment key={t.key}>
                <div
                  className={
                    'chart-type-btn' + (chartType === t.key ? ' active' : '')
                  }
                  data-type={t.key}
                  onClick={() => setChartType(t.key)}
                >
                  {t.label}
                </div>
                {t.key === 'minute' && chartType === 'minute' && (
                  <select
                    className="stock-select"
                    value={minuteInterval}
                    onChange={(e) => setMinuteInterval(e.target.value)}
                  >
                    {['1','3','5','10','15','30','45','60'].map((m) => (
                      <option key={m} value={m}>
                        {m}분
                      </option>
                    ))}
                  </select>
                )}
              </React.Fragment>
            ))}
            <select
              id="stockSelector"
              className="stock-select"
              value={stockCode}
              onChange={(e) => setStockCode(e.target.value)}
            >
              <option value="005930">삼성전자</option>
              <option value="000660">SK하이닉스</option>
              <option value="035720">카카오</option>
              <option value="323410">카카오뱅크</option>
              <option value="207940">삼성바이오로직스</option>
              <option value="035420">NAVER</option>
              <option value="051910">LG화학</option>
              <option value="005380">현대자동차</option>
            </select>
          </div>
        </div>
        <div className="chart-wrapper">
          <div className="chart-container" ref={chartContainerRef}></div>
        </div>
      </div>
    </section>
  );
};

const ChatWrapper = () => {
  const chatContainerRef = useRef(null);
  const [input, setInput] = useState('');

  // useEffect(() => {
  //   initChat(chatContainerRef.current);
  // }, []);

  const handleSend = () => {
    // chat.js 의 함수 호출 또는 직접 처리
    if (window.sendMessage) window.sendMessage(input);
    setInput('');
  };

  return (
    <section className="chat_wrapper">
      <div className="main_chat" ref={chatContainerRef}>
        <h3 className="line_2"></h3>
        <h2 className="title">오늘은 어떤 주식이 궁금하신가요?</h2>
        <input
          className="chat_input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="입력하세요…"
        />
        <button className="chat_btn" onClick={handleSend}>
          전송
        </button>
      </div>
    </section>
  );
};

const ChatMain = () => (
  <section className="chat_main">
    <StockChart />
    <ChatWrapper />
  </section>
);

const App = () => {
  // 페이지 로드시 암호화폐 시세 피드 시작
  useEffect(() => {
    btcPriceFeed?.();
    ethPriceFeed?.();
    lrcPriceFeed?.();
  }, []);

  return (
    <div className="App">
      <Sidebar />
      <TopBar />
      <ChatMain />
    </div>
  );
};

export default App;
