import React, {useState} from 'react';
import { useNavigate, Link } from 'react-router-dom';


import StockChart from './StockChart.jsx';
import Chat from './Chat.jsx';
import '../styles/main.css';

/*이미지 모음 */
import teamlogo from '../assets/teamlogo.png';
import side_btn from '../assets/Vector_3.svg';
import UserIcon from "../assets/user.svg";

const Home = () => {
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);  // 추가
  const [showUserPopup, setShowUserPopup] = useState(false);  // 추가
  
  const toggleSidebar = () => {  // 추가
    setSidebarOpen(prev => !prev);
  };

  const toggleUserPopup = () => {  // 추가
    setShowUserPopup(prev => !prev);
  };
  
  const handleAiChat = () => {
    navigate('/');
  };

  const handleBookmark = () => {
    navigate('/bookmark'); 
  };

  return (
    <section className="app-container">
      
      {/* <button type='button' className={`side_btn_global ${sidebarOpen ? '' : 'collapsed'}`} onClick={toggleSidebar}>
        <img src={side_btn} className="side_btn_png" alt="toggle sidebar" />
      </button> */ }
      
      {/* 상단바 : 유저 (추후 로그인+회원가입) */}
      <aside className='top-bar'>
        <div className="user-bar">
            <button type='button' className="user_btn">
              <img src={UserIcon} alt="user" className="user" />
            </button>
          <p className='line_5'></p>
          {showUserPopup && (
            <div className="user-popup">
              <button onClick={() => alert("로그인")}>로그인</button>
              <button onClick={() => alert("회원가입")}>회원가입</button>
            </div>)}
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
            <Link to ="/"></Link>
            <button className="ai_chat" onClick={handleAiChat}>🔎 AI Chat</button>
          </nav>
          <nav>
            <Link to ="/bookmark"></Link>
            <button className="bookmark" onClick={handleBookmark}>⭐ 즐겨찾기</button>
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
          <div className="post_bg">{/* 뉴스 컨텐츠 */}</div>
        </div>
      </aside>


      {/* 메인 콘텐츠 */}
      <aside className="main-bar">
        <section className="chart-section">
          <StockChart stockCode="005930" chartType="daily" /> 
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
