import React from 'react';

import styles from './rank.module.css'; // rank 컴포넌트 전용 스타일


const Rank = ({ stocks = [], onStockSelect }) => {
  return (
    <div className={styles['top-stocks-container']}>
      <h2>거래량 상위 종목</h2>
      <table className={styles['stocks-table']}>
        <thead>
          <tr>
            <th>순위</th>
            <th>종목</th>
            <th>현재가</th>
            <th>등락률</th>
            <th>거래량</th>
          </tr>
        </thead>
        <tbody>
          {stocks.length === 0 ? (
            <tr><td colSpan="5" style={{textAlign:'center'}}>데이터가 없습니다</td></tr>
          ) : (
            stocks.map((stock, index) => (
              <tr key={stock.code} className={styles['stock-row']} onClick={() => onStockSelect && onStockSelect(stock.code)}>
                <td>{index + 1}</td>
                <td className={styles['stock-name']}>{stock.name}</td>
                <td>{stock.price?.toLocaleString()}원</td>
                <td className={stock.change >= 0 ? styles.up : styles.down}>
                  {stock.change >= 0 ? "+" : ""}{stock.change}%
                </td>
                <td>{stock.volume?.toLocaleString()}주</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
};

export default Rank;
