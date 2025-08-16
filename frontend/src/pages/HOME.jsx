// pages/Home/Home.jsx
import React, { useState } from 'react';

// 로직 분리
import { useTopStocks } from '../hooks/useTopStocks';

// 레이아웃 컴포넌트들
import StockChart from '../components/layout/StockChart/StockChart'
import Chat from '../components/layout/Chat/Chat';
import Rank from '../components/layout/Rank/Rank';
import Sidebar from '../components/layout/Sidebar/Sidebar';
import Topbar from '../components/layout/Topbar/Topbar';
import ChartRank from '../components/layout/Rank/Rank';
import AiResult from '../components/layout/Airesult/airesult';

// 페이지 전용 스타일
import styles from '../styles/main.module.css';

const Home = () => {
  //주식 데이터 로직 
  const { topStocks, loading, error } = useTopStocks();
  
  const [selectedStock, setSelectedStock] = useState(null);

  const handleStockSelect = (stockCode) => {
    setSelectedStock(stockCode);
  };

  const renderChartSection = () => {
    if (selectedStock) {
      return (
        <>
          <button className={styles.backButton} onClick={() => setSelectedStock(null)}>
            ← 랭킹으로 돌아가기
          </button>
          <StockChart stockCode={selectedStock} />
        </>
      );
    }
    if (loading) return <div>거래량 상위 종목을 불러오는 중...</div>;
    if (error) return <div>{error}</div>;
    return <Rank stocks={topStocks} onStockSelect={handleStockSelect} />;
  };

  return (
    // 페이지 전체 레이아웃
    <div className={styles.homeContainer}>
      {/*고정 컴포넌트 */}
      <Sidebar />
      <Topbar />
      {/* 메인 콘텐츠 */}
      <main className={styles.main_content}>
        <section className={styles.chart_section}>
          {renderChartSection()}
        </section>
        <div className={styles.divider}></div>
        <section className={styles.chat_section}>
          <Chat />
        </section>
        <section className={styles.ai_result_section}>
          <AiResult />
        </section>
      </main>
    </div>
  );
};

export default Home;
