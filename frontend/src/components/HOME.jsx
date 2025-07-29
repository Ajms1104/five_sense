import React, {useState, useEffect, cloneElement} from 'react';
import { useNavigate, Link } from 'react-router-dom';

import StockChart from './StockChart.jsx';
import Chat from './Chat.jsx';
import Rank from './Rank.jsx';
import '../styles/main.css';

/*이미지 모음 */
import teamlogo from '../assets/teamlogo.png';
import side_btn from '../assets/Vector_3.svg';
import UserIcon from "../assets/user.svg";

const Home = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showUserPopup, setShowUserPopup] = useState(false);
  const [news, setNews] = useState([]);
  const [newsError, setNewsError] = useState(null);
  const [topStocks, setTopStocks] = useState([]);
  const [selectedStock, setSelectedStock] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // 추가: 로그인 상태 관리 (기존 변수명 건들지 않음)
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const navigate = useNavigate();

  // 추가: useEffect로 localStorage 체크 (로그인 상태 유지)
  useEffect(() => {
    const loggedIn = localStorage.getItem('isLoggedIn') === 'true';
    setIsLoggedIn(loggedIn);
  }, []);

  const toggleSidebar = () => {
    setSidebarOpen(prev => !prev);
  };

  const toggleUserPopup = () => {  // 기존 함수 유지
    setShowUserPopup(prev => !prev);
  };

  // 추가: 로그아웃 핸들러 (새로 만듦)
  const handleLogout = () => {
    localStorage.removeItem('isLoggedIn');
    setIsLoggedIn(false);
    setShowUserPopup(false);  // 팝업 닫기
    navigate('/login');  // 로그인 페이지로 이동
  };
  
  const handleAiChat = () => {
    navigate('/');
  };

  const handleBookmark = () => {
    navigate('/bookmark'); 
  };

  const handleLogin = () => {
    navigate('/login');
  }

  // 추가: user_btn 클릭 핸들러 (로그인 상태에 따라 분기; 기존 handleLogin 활용)
  const handleUserButtonClick = () => {
    if (isLoggedIn) {
      toggleUserPopup();  // 로그인 시 팝업 토글
    } else {
      handleLogin();  // 미로그인 시 기존 로그인 페이지로
    }
  };

  const handleStockSelect = (stockCode) => {
    setSelectedStock(stockCode);
  };

  useEffect(() => {
    const fetchTopStocks = async () => {
      try {
        const response = await fetch('http://localhost:8080/api/stock/top-volume');
        if (!response.ok) {
          throw new Error('거래량 상위 종목을 가져오는데 실패했습니다');
        }
        const data = await response.json();
        console.log('API 응답:', data); // 실제 응답 확인

        // 여기서 키를 바꿔줍니다!
        const stocks = data.tdy_trde_qty_upper || [];
        console.log('파싱된 stocks:', stocks);

        setTopStocks(stocks.map(stock => ({
          code: stock.stk_cd?.replace('_AL', '') ?? '',
          name: stock.stk_nm ?? '',
          volume: parseInt(stock.trde_qty) || 0,
          price: parseInt(stock.cur_prc) || 0,
          change: parseFloat(stock.flu_rt) || 0
        })));
        setLoading(false);
      } catch (error) {
        console.error('거래량 상위 종목 로딩 에러:', error);
        setError(error.message);
        setLoading(false);
      }
    };

    fetchTopStocks();
  }, []);

  useEffect(() => {
    const fetchNews = async () => {
      try {
        const response = await fetch('http://localhost:8080/api/stock/news');
        if (!response.ok) {
          throw new Error('뉴스를 가져오는데 실패했습니다');
        }
        const data = await response.json();
        if (Array.isArray(data)) {
          setNews(data);
        } else {
          setNews([]);
        }
      } catch (error) {
        console.error('뉴스 로딩 에러:', error);
        setNewsError(error.message);
        setNews([]);
      }
    };

    fetchNews();
  }, []);

  const renderChartSection = () => {
    if (selectedStock) {
      return (
        <div className="chart-container">
          <button className="back-button" onClick={() => setSelectedStock(null)}>
            ← 랭킹으로 돌아가기
          </button>
          <StockChart stockCode={selectedStock} chartType="daily" />
        </div>
      );
    }

    if (loading) {
      return <div className="loading">거래량 상위 종목을 불러오는 중...</div>;
    }

    if (error) {
      return <div className="error">거래량 상위 종목을 불러오는데 실패했습니다</div>;
    }

    return (
      <Rank stocks={topStocks} onStockSelect={handleStockSelect} />
    );
  };

  return (
    <section className="app-container">
      
      {/* <button type='button' className={`side_btn_global ${sidebarOpen ? '' : 'collapsed'}`} onClick={toggleSidebar}>
        <img src={side_btn} className="side_btn_png" alt="toggle sidebar" />
      </button> */ }
      
      {/* 상단바 : 로그인+회원가입*/}
      <aside className='top-bar'>
        <div className="user-bar">
            <nav>
              {/* 기존 Link 유지, onClick을 handleUserButtonClick으로 변경 */}
              <button className="user_btn" onClick={handleUserButtonClick}>
                <img src={UserIcon} alt="user" className="user" />
              </button>
            </nav>
            {/* 추가: 팝업 (user_btn 아래에 위치; position: absolute로 배치) */}
            {/* showUserPopup && isLoggedIn && 
            (<div className='user_login_logout_check'>
                <p>로그인 중</p>
                <button onClick={handleLogout} style={{ marginTop: '10px' }}>로그아웃</button>
              </div>
            )*/}
          <p className='line_5'></p>
        </div>
      </aside>

      {/* 사이드바 : 로고  */}
      <aside className= 'sidebar'> {/*{`sidebar ${sidebarOpen ? '' : 'collapsed'}`} */}
        <div className="sidebar-top">
          <div className="logo-top">
            <img src={teamlogo} className="logo_png"/>
            <h1 className="logo-txt">FIVE_SENSE</h1>
            <button type='button' className="side_btn"  onClick={toggleSidebar}>
              <img src={side_btn} className="side_btn_png" />
            </button>
          </div>
        </div>

        {/* 사이드바 : 메뉴영역(ai chat, 즐겨찾기)  */}
        <div className='sidebar-menu-top'>
          <h2 className="menu-txt">메뉴</h2>
          <nav>
            <Link to ="/">
             <button className="ai_chat" onClick={handleAiChat}>🔎 AI Chat</button>
            </Link>
          </nav>
          <nav>
            <Link to ="/bookmark">
             <button className="bookmark" onClick={handleBookmark}>⭐ 즐겨찾기</button>
            </Link>         
          </nav>
          <p className='line_1'></p>
        </div>

        {/* 사이드바 : 검색 기록 */}
        <div className='sidebar-menu-mid'>
          <h2 className="history_font">검색 기록</h2>
          <button className="today_btn">오늘 ▼</button>
          <p className="line_2"></p>
          <button className='dplus-7-btn'>7일 전▲</button>
          <p className='line_3'></p>
        </div>
        {/* 사이드바 : 최신 뉴스 */}
        <div className="sidebar-menu-bottom">
          <h2 className="post">최신 뉴스</h2>
          <div className="post_bg">
            {newsError ? (
              <div className="news-error">뉴스를 불러오는데 실패했습니다</div>
            ) : news.length > 0 ? (
              news.map((item, index) => (
                <div key={index} className="news-item">
                  <a href={item.link} target="_blank" rel="noopener noreferrer">
                    {item.title}
                  </a>
                </div>
              ))
            ) : (
              <div className="news-loading">뉴스를 불러오는 중...</div>
            )}
          </div>
        </div>
      </aside>


      {/* 메인 콘텐츠 */}
      <aside className="main-bar">
        <section className="chart-section">
          {renderChartSection()}
        </section>
         <p className="line_4"></p>
        <section className="chat-section">
          <Chat />
        </section>
      </aside>
    </section>
  );
};

export default Home;
