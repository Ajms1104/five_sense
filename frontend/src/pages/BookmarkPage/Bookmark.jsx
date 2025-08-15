// pages/BookmarkPage.jsx (이 파일은 components보다 pages에 있는 게 더 어울려요!)
// 즐겨찾기

import React, {useState} from 'react';
import { useNavigate, Link } from 'react-router-dom';

// 꿀팁: 이 페이지에서 필요한 레이아웃 컴포넌트들을 불러옵니다.
import Sidebar from '../../components/layout/Sidebar/Sidebar';
import Topbar from '../../components/layout/Topbar/Topbar';

import style from './bookmark.module.css';

const BookmarkPage = () => {
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showUserPopup, setShowUserPopup] = useState(false);
  
  const toggleSidebar = () => {
    setSidebarOpen(prev => !prev);
  };

  const toggleUserPopup = () => {
    setShowUserPopup(prev => !prev);
  };
  
  return (
    // 수정: 일반 문자열 -> CSS 모듈 사용
    <section className={style['bookmark-container']}>
      <Topbar />
      <Sidebar />
  
      {/* 메인화면 / 즐겨찾기 */}
      <aside className={style['b-main-bar']}>
        <div className={style['bookmark-top']}>
          <h3 className={style.bookmark_name}>즐겨찾기</h3>
          <p className={style.line_6}></p>
          <div className={style['bookmark-side']}>
            <button className={style.mark_chart}>📈 주식</button>
            <button className={style.mark_search}>🕜 검색 기록</button>
            <p className={style.line_7}></p>
          </div>
          <div className={style['bookmark-center']}>
            <button className={style.mark_check}>⭐즐겨찾기 한 주식</button>
          </div>
        </div>
      </aside>
    </section>
  );
};

export default BookmarkPage;
