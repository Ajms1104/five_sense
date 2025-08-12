// components/Rank/Rank.jsx (최종 추천 코드)
import React from 'react';
import styles from './rank.module.css';

// onStockSelect: 주식 행을 클릭했을 때 실행될 함수
// stocks: API로부터 받아온 주식 데이터 배열
const Rank = ({ stocks = [], onStockSelect }) => {
  return (
    <div className={styles['stock-ranking-container']}>
      {/* 1. 헤더 영역 (제목 + 업데이트 시간) */}
      <div className={styles['header']}>
        <h2 className={styles['title']}>실시간 주식 차트</h2>
        <span className={styles['update-time']}>오늘 13:20 기준</span>
      </div>

      {/* 2. 시간 필터 버튼 영역 */}
      <div className={styles['filter-buttons']}>
        {['실시간', '1일', '1주일', '1개월', '3개월', '6개월', '1년'].map((text, index) => (
          <button key={text} className={index === 0 ? styles['active'] : ''}>
            {text}
          </button>
        ))}
      </div>

      {/* 3. 랭킹 목록 테이블 */}
      <table className={styles['stocks-table']}>
        <thead>
          <tr>
            <th className={styles['th-rank']}>종목</th>
            <th className={styles['th-price']}>현재가</th>
            <th className={styles['th-change']}>등락률</th>
            <th className={styles['th-volume']}>거래대금 많은 순</th>
          </tr>
        </thead>
        <tbody>
          {stocks.length === 0 ? (
            <tr><td colSpan="4" className={styles['no-data']}>데이터가 없습니다</td></tr>
          ) : (
            stocks.map((stock, index) => (
              <tr key={stock.code} onClick={() => onStockSelect && onStockSelect(stock.code)}>
                {/* 종목명 (순위, 하트, 이름 포함) */}
                <td className={styles['td-name-cell']}>
                  <span className={styles['rank']}>{index + 1}</span>
                  <button className={styles['favorite-btn']}>♥</button>
                  <span className={styles['stock-name']}>{stock.name}</span>
                </td>
                {/* 현재가 */}
                <td className={styles['td-price']}>{stock.price?.toLocaleString()}원</td>
                {/* 등락률 */}
                <td className={`${styles['td-change']} ${stock.change >= 0 ? styles.up : styles.down}`}>
                  {stock.change >= 0 ? "▲" : "▼"} {Math.abs(stock.change)}%
                </td>
                {/* 거래량 */}
                <td className={styles['td-volume']}>{stock.volume?.toLocaleString()}주</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
};

export default Rank;
