import { useState, useEffect } from 'react';

export function useTopStocks() {
  const [topStocks, setTopStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTopStocks = async () => {
      try {
        const response = await fetch('http://localhost:8080/api/stock/top-volume');
        if (!response.ok) {
          throw new Error('거래량 상위 종목을 가져오는데 실패했습니다');
        }
        const data = await response.json();
        const stocks = data.tdy_trde_qty_upper || [];
        setTopStocks(stocks.map(stock => ({
          code: stock.stk_cd?.replace('_AL', '') ?? '',
          name: stock.stk_nm ?? '',
          volume: parseInt(stock.trde_qty) || 0,
          price: parseInt(stock.cur_prc) || 0,
          change: parseFloat(stock.flu_rt) || 0
        })));
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchTopStocks();
  }, []); // 이 훅은 처음 한 번만 실행됩니다.

  // 필요한 값과 상태를 return 해줍니다.
  return { topStocks, loading, error };
}
