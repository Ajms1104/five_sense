//사이드바 컴포넌트

import React, { useState, useEffect } from 'react'; 
import { useNavigate, Link } from 'react-router-dom';

import style from './sidebar.module.css';

// 사용하는 모든 이미지를 import 합니다.
import teamlogo from '../../../assets/teamlogo.png';
import side_btn from '../../../assets/Vector_3.svg';
import aichat from '../../../assets/serch.svg';
import star from '../../../assets/star.svg';
import down_btn from '../../../assets/down_btn.svg';


{/* */}
function Sidebar() {
  const navigate = useNavigate();
  const [isTodayOpen, setIsTodayOpen] = useState(false);
  const [is7DaysOpen, setIs7DaysOpen] = useState(false);

  const handleTodayToggle = () => {
    setIsTodayOpen(prev => !prev);
  };
  
  const handle7DaysToggle = () => {
    setIs7DaysOpen(prev => !prev);
  };
  const handleDropdownToggle = () => {
    setIsDropdownOpen(prev => !prev);
  };
  
  const toggleSidebar = () => {}; 
  const handleAiChat = () => navigate('/');
  const handleBookmark = () => navigate('/bookmark');

  const [news, setNews] = useState([]);
  const [newsError, setNewsError] = useState(null);

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

  {/* 페이지 구성 */}
  return (
    <aside className={style.sidebar}> 
    {/* 사이드바 : 로고 */}
      <div className={style['sidebar-top']}>
        <div className={style['logo-top']}>
          <img src={teamlogo} className={style['logo_png']}/>
          <Link to ="/" className={style.logoandhome}> {/* 검은 밑줄 편집하기 */}
          <h1 className={style['logo-txt']}>FIVE_SENSE</h1>
          </Link>
          <button type='button' className={style['side_btn']}  onClick={toggleSidebar}>
            <img src={side_btn} className={style['side_btn_png']}/>
          </button>
        </div>
      </div>

      {/* 사이드바 : 메뉴 모음(ai chat, 즐겨찾기) */}
      <div className={style['sidebar-menu-top']}> 
        <h2 className={style['menu-txt']}>메뉴</h2>
        <nav>
          <Link to ="/">
            <img src={aichat} className={style['ai_chat_img']}/>
            <button className={style.ai_chat} onClick={handleAiChat}>AI Chat</button>
          </Link>
        </nav>
        <nav>
          <Link to ="/bookmark">
            <img src={star} className={style['bookmark_img']}/>
            <button className={style.bookmark} onClick={handleBookmark}>즐겨찾기</button>
          </Link>         
        </nav>
        <p className={style.line_1}></p>
      </div>

      {/* 사이드바 : 검색기록 (오늘, 7일전) */}
      <div className={style['sidebar-menu-mid']}>
        <h2 className={style.history_font}>검색 기록</h2>
        <button type="button" className={style.today_btn} onClick={handleTodayToggle}>
          <span>오늘</span>
          <img src={down_btn} className={style.down_icon}/>
        </button>
        {isTodayOpen && ( /* 오늘 검색기록 폴드 */
          <div className={style.dropdownMenu}>
            <p className={style.line_2}>
              <button className={style.dropdownItem}>ex. 엔비디아 전망</button>
              <button className={style.dropdownItem}>ex. 애플 주가 변화</button>
              <button className={style.dropdownItem}>ex. 삼성 재무재표 분석</button>
              <button className={style.dropdownItem}>ex. 테슬라 최신 뉴스 요약</button>
            </p>
          </div>
        )}

        <button type="button" className={style.day_7_btn} onClick={handle7DaysToggle}>
          <span>7일 전</span>
          <img src={down_btn} className={style.down_icon}/>
        </button>
        {is7DaysOpen && ( /* 7일전 검색기록 폴드 */
          <div className={style.dropdownMenu}>
            <p className={style.line_2}>
              <button className={style.dropdownItem}>ex. 카카오 전망</button>
              <button className={style.dropdownItem}>ex. 애플 주가 변화</button>
              <button className={style.dropdownItem}>ex. 삼성 재무재표 분석</button>
            </p>
          </div>
        )}
          <p className={style.line_3}></p>

      {/* 사이드바 : 뉴스 기록 */}
          <div className={style['sidebar-menu-bottom']}>
            <h2 className={style.post}>최신 뉴스</h2>
            <div className={style.post_bg}>
              {newsError ? (
                <div className={style.news_error}>뉴스를 불러오는데 실패했습니다</div>
              ) : news.length > 0 ? (
                news.map((item, index) => (
                  <div key={index} className={style['news-item']}>
                    <a href={item.link} target="_blank" rel="noopener noreferrer">
                      {item.title}
                    </a>
                  </div>
                ))
              ) : (
                <div className={style['news-loading']}>뉴스를 불러오는 중...</div>
              )}
          </div>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
