import React, { useState, useEffect } from 'react';
import styles from './rank.module.css';

const Rank = ({ stocks = [], onStockSelect }) => {
  const [currentTime, setCurrentTime] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;
  const [activeTab, setActiveTab] = useState('realtime');

  useEffect(() => {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    setCurrentTime(`${hours}:${minutes}`);
  }, []);

  const totalPages = Math.ceil(stocks.length / itemsPerPage);
  const currentStocks = stocks.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );
  const goToNextPage = () => setCurrentPage((prev) => Math.min(prev + 1, totalPages));
  const goToPrevPage = () => setCurrentPage((prev) => Math.max(prev - 1, 1));

  return (
    <div className={styles['rank-component-wrapper']}>
      {/* 3. 탭 버튼 UI 영역 */}
      <div className={styles['tab-container']}>
        <button
          className={`${styles['tab-button']} ${activeTab === 'realtime' ? styles['active'] : ''}`}
          onClick={() => setActiveTab('realtime')}
        > 실시간 주식 차트 </button>
        <button
          className={`${styles['tab-button']} ${activeTab === 'watchlist' ? styles['active'] : ''}`}
          onClick={() => setActiveTab('watchlist')}
        > 관심 종목 주식 차트 </button>
      </div>

      <div className={styles['stock-ranking-container']}>
        {/* '실시간 주식 차트' 탭이 활성화되었을 때 보여줄 내용 */}
        {activeTab === 'realtime' && (
          <>
            <div className={styles['header']}>
              <h2 className={styles['title']}>실시간 주식 차트</h2>
              <span className={styles['update-time']}>현재 {currentTime} 기준</span>
            </div>
            
            <table className={styles['stocks-table']}>
              <thead>
                <tr>
                  <th className={styles['th-rank']}>종목</th>
                  <th className={styles['th-price']}>현재가</th>
                  <th className={styles['th-change']}>등락률</th>
                </tr>
              </thead>
              <tbody>
                {currentStocks.length === 0 ? (
                  <tr><td colSpan="3" className={styles['no-data']}>데이터가 없습니다</td></tr>
                ) : (
                  currentStocks.map((stock, index) => {
                    const actualRank = (currentPage - 1) * itemsPerPage + index + 1;
                    return (
                      <tr key={stock.code} onClick={() => onStockSelect && onStockSelect(stock.code)}>
                        <td className={styles['td-name-cell']}>
                          <span className={styles['rank']}>{actualRank}</span>
                          <button className={styles['favorite-btn']}>♥</button>
                          <span className={styles['stock-name']}>{stock.name}</span>
                        </td>
                        <td className={styles['td-price']}>{stock.price?.toLocaleString()}원</td>
                        <td className={`${styles['td-change']} ${stock.change >= 0 ? styles.up : styles.down}`}>
                          {stock.change >= 0 ? "▲" : "▼"} {Math.abs(stock.change)}%
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>

            <div className={styles['pagination-controls']}>
              <button onClick={goToPrevPage} disabled={currentPage === 1}>
                이전
              </button>
              <span className={styles['page-info']}>
                {currentPage} / {totalPages || 1}
              </span>
              <button onClick={goToNextPage} disabled={currentPage === totalPages || totalPages === 0}>
                다음
              </button>
            </div>
          </>
        )}
        
      {/* '관심 종목' 탭이 활성화되었을 때 보여줄 내용 */}
      {activeTab === 'watchlist' && (
          <div className={styles['no-data']}> 관심 종목 기능은 준비 중입니다.</div>
      )}
      </div>
    </div>
  );
};

export default Rank;
