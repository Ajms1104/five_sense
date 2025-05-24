// src/components/Home.jsx
import React from 'react';
import StockChart from './StockChart';
import Chat from './Chat';
import Profile from './Profile';
import '../styles/main.css';

const Home = () => {
  return (
    <div className="container">
      <header>
        <h1>FIVE-SENSE</h1>
        <Profile />
      </header>
      <main>
        <div className="chart-section">
          <StockChart stockCode="005930" chartType="daily" />
        </div>
        <div className="chat-section">
          <Chat />
        </div>
      </main>
    </div>
  );
};

export default Home;
