// components/Bookmark.jsx
import React, {useState} from 'react';
import { useNavigate, Link } from 'react-router-dom';

import '../styles/bookmark.css';

/*이미지 모음 */
import teamlogo from '../assets/teamlogo.png';
import side_btn from '../assets/Vector_3.svg';
import UserIcon from "../assets/user.svg";

const Bookmark = () => {
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);  // 추가
  const [showUserPopup, setShowUserPopup] = useState(false);  // 추가
  
  const toggleSidebar = () => {  // 추가
    setSidebarOpen(prev => !prev);
  };

  const toggleUserPopup = () => {  // 추가
    setShowUserPopup(prev => !prev);
  };
  
  const handlehome = () => { //AI-Chat 버튼 누르면 이어질 곳
    navigate('/');
  };

  const handleBookmark = () => { //즐겨찾기 버튼 누르면 이어질 곳
    navigate('/bookmark'); 
  };

  const handleLogin = () => {   //User 버튼 누르면 이어질 곳 (로그인, 회원가입)
    navigate('/login');   
  }

  return (
    <section className="bookmark-container">
      
      {/* <button type='button' className={`side_btn_global ${sidebarOpen ? '' : 'collapsed'}`} onClick={toggleSidebar}>
        <img src={side_btn} className="side_btn_png" alt="toggle sidebar" />
      </button> */ }
      
      {/* 상단바 : 로그인+회원가입*/}
      <aside className='top-bar'>
        <div className="user-bar">
            <nav>
              <Link to ="/login">
                <button className="user_btn" onClick={handleLogin}>
                  <img src={UserIcon} alt="user" className="user" />
                </button>
              </Link>
            </nav>
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
                    <button className="ai_chat" onClick={handlehome}>🔎 AI Chat</button>
                  </Link>
                </nav>
                <nav>
                  <Link to ="/bookmark">
                    <button className="b_bookmark" onClick={handleBookmark}>⭐ 즐겨찾기</button>
                  </Link>
                </nav>
                <p className='b_line_1'></p>
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

        {/* 메인화면 / 즐겨찾기 (이미지들은 추후에..)  */}
        <aside className="b-main-bar">
            <div className="bookmark-top">
                <h3 className="bookmark_name">즐겨찾기</h3>
                <p className="line_6"></p>
                 <div className="bookmark-side">
                    <button className='mark_chart'>📈  주식</button>
                    <button className='mark_search'>🕜  검색 기록</button>
                    <p className='line_7'></p>
                 </div>
                 <div className='bookmark-center'>
                    <button className='mark_check'>⭐즐겨찾기 한 주식</button>
                 </div>
            </div>
        </aside>
    </section>
  );
};

export default Bookmark;
