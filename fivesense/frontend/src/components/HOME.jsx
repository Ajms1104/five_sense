// src/components/Home.jsx
import React, { useState } from 'react';
import '../styles/main.css';
import '../styles/profile.css';

// JS 모듈 import (경로는 파일구조에 맞게 조정)
import '../js/profile.js';
import '../js/stockChart.js';
import '../js/chat.js';

const userMock = null; // 실제 유저 정보는 props 또는 context로 주입 필요

const Home = ({ user = userMock }) => {
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);

  const handleProfileBtnClick = () => {
    setProfileMenuOpen((prev) => !prev);
  };

  return (
    <div style={{ width: '100%', height: '100vh', display: 'flex' }}>

      {/* 왼쪽 사이드바 */}
      <section className="sidebar">
        <span className="name">FIVE-SENSE</span>
        <button>개인설정</button>
        <button>즐겨찾기</button>
        <button>포토폴리오</button>
        <nav>
          <p style={{ color: 'black' }}>라이브러리</p>
          <div className="history"></div>
        </nav>
      </section>

      {/* 메인 섹션 */}
      <section className="main">
        <div className="chart">
          <div className="chart-header">
            <p className="chart-title">주식 차트</p>
            <div className="chart-controls">
              <div className="chart-type-btn" data-type="minute">분</div>
              <select id="minuteSelector" className="stock-select" style={{ display: 'none' }}>
                <option value="1">1분</option>
                <option value="3">3분</option>
                <option value="5">5분</option>
                <option value="10">10분</option>
                <option value="15">15분</option>
                <option value="30">30분</option>
                <option value="45">45분</option>
                <option value="60">60분</option>
              </select>
              <div className="chart-type-btn active" data-type="daily">일</div>
              <div className="chart-type-btn" data-type="weekly">주</div>
              <div className="chart-type-btn" data-type="monthly">월</div>
              <div className="chart-type-btn" data-type="yearly">년</div>
              <select id="stockSelector" className="stock-select">
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
            <div className="chart-container">
              {/* 차트는 stockChart.js에서 동적으로 생성 */}
            </div>
          </div>
        </div>
        <div className="chat-section">
          <div className="chat-history"></div>
          <div className="bottom-section">
            <div className="input-container">
              <input placeholder="AI 입력칸" />
              <div id="submit">➢</div>
            </div>
          </div>
          <p className="info">
            주식 투자시 원금 손실에 대한 책임은 투자자 본인에게 있으며
            FIVE-SENSE는 책임지지 않습니다.
          </p>
        </div>
      </section>
    </div>
  );
};

export default Home;
