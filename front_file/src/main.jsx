import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';

function App() {
  const [currentPage, setCurrentPage] = useState('home');
  const [aiInput, setAiInput] = useState('');
  const [aiOutput, setAiOutput] = useState('');

  const renderMainContent = () => {
    switch (currentPage) {
      case '개인설정':
      case '즐겨찾기':
      case '포토폴리오':
        return (
          <div className="page-content" style={{ padding: '20px' }}>
            <h2 style={{ color: 'black' }}>{currentPage} 페이지</h2>
            <p style={{ color: 'black' }}>(내용은 아직 없어요!)</p>
            <button
              onClick={() => setCurrentPage('home')}
              style={{ marginTop: '30px', padding: '10px' }}
            >
              홈으로 돌아가기
            </button>
          </div>
        );
      default:
        return (
          <>
            <div className="chart">
              <p style={{ color: 'black' }}>실시간 주식 차트</p>
              <img width="100%" height="50%" src="./public/sample_chart_.png" alt="샘플 차트" />
            </div>
            <p id="output">{aiOutput}</p>
            <div className="bottom-section">
              <div className="input-container">
                <input
                  placeholder="AI 입력칸"
                  value={aiInput}
                  onChange={(e) => setAiInput(e.target.value)}
                />
                <div id="submit" onClick={() => setAiOutput(`AI 응답 예시: "${aiInput}"`)}>
                  ➢
                </div>
              </div>
            </div>
            <p className="info">
              주식 투자시 원금 손실에 대한 책임은 투자자 본인에게 있으며 FIVE-SENSE는 책임지지 않습니다.
            </p>
          </>
        );
    }
  };

  return (
    <>
      <section className="sidebar">
        <span className="name">FIVE-SENSE</span>
        <button onClick={() => setCurrentPage('개인설정')}>개인설정</button>
        <button onClick={() => setCurrentPage('즐겨찾기')}>즐겨찾기</button>
        <button onClick={() => setCurrentPage('포토폴리오')}>포토폴리오</button>

        <nav>
          <p style={{ color: 'black' }}>라이브러리</p>
          <div className="history"></div>
        </nav>
      </section>

      <section className="main">{renderMainContent()}</section>
    </>
  );
}

const root = createRoot(document.body); 
root.render(<App />);
