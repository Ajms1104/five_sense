// pages/BookmarkPage.jsx
// 즐겨찾기
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';

// 컴포넌트
import Sidebar from '../../components/layout/Sidebar/Sidebar';
import Topbar from '../../components/layout/Topbar/Topbar';

import style from './bookmark.module.css';

const BookmarkPage = () => {
    // --- 기존 로직 ---
    const navigate = useNavigate();
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [showUserPopup, setShowUserPopup] = useState(false);
    
    const toggleSidebar = () => setSidebarOpen(prev => !prev);
    const toggleUserPopup = () => setShowUserPopup(prev => !prev);

    // --- 데이터 및 상태 관리 로직 ---
    const [activeTab, setActiveTab] = useState('stock');

    const [stockBookmarks, setStockBookmarks] = useState([
        { id: 1, name: '즐겨찾기 한 주식 1' }, // isFavorite 속성 제거
        { id: 2, name: '즐겨찾기 한 주식 2' },
        { id: 3, name: '즐겨찾기 한 주식 3' },
    ]);
    
    const [searchHistory, setSearchHistory] = useState([
        { id: 1, query: '삼성전자 재무재표 분석' },
        { id: 2, query: '테슬라 최신 뉴스 요약' },
        { id: 3, query: '카카오 전망' },
    ]);

    // ⭐ 1. 주식 즐겨찾기 삭제 함수 추가 (기존 토글 함수는 제거)
    const handleDeleteStockBookmark = (stockId) => {
        setStockBookmarks(prevStocks => 
            prevStocks.filter(stock => stock.id !== stockId)
        );
    };

    // 검색 기록 삭제 함수
    const handleDeleteSearchHistory = (historyId) => {
        setSearchHistory(prevHistory => 
            prevHistory.filter(item => item.id !== historyId)
        );
    };
    
    return (
        <section className={style['bookmark-container']}>
            <Sidebar />
            <Topbar />
    
            <aside className={style['b-main-bar']}>
                <div className={style['bookmark-top']}>
                    <h3 className={style.bookmark_name}>즐겨찾기</h3>
                    <p className={style.line_6}></p>
                    
                    <div className={style['bookmark-side']}>
                        <button 
                            className={`${style.mark_chart} ${activeTab === 'stock' ? style.active : ''}`}
                            onClick={() => setActiveTab('stock')}
                        >
                            📈 주식
                        </button>
                        <button 
                            className={`${style.mark_search} ${activeTab === 'search' ? style.active : ''}`}
                            onClick={() => setActiveTab('search')}
                        >
                            🕜 검색 기록
                        </button>
                        <p className={style.line_7}></p>
                    </div>
                    
                    <div className={style['bookmark-center']}>
                        {/* '주식' 탭 렌더링 수정 */}
                        {activeTab === 'stock' && (
                            <ul className={style['bookmark-list']}>
                                {stockBookmarks.map(item => (
                                    <li key={item.id} className={style['bookmark-item']}>
                                        {/* ⭐ 2. 별 아이콘을 고정된 span으로 변경 */}
                                        <span className={style['favorite-icon']}>⭐</span>
                                        <span className={style['item-name']}>{item.name}</span>
                                        {/* ⭐ 3. 주식 목록에 삭제 버튼 추가 */}
                                        <button 
                                            className={style['delete-btn']}
                                            onClick={() => handleDeleteStockBookmark(item.id)}
                                        >
                                            ✕
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        )}

                        {/* '검색 기록' 탭 렌더링 (기존과 동일) */}
                        {activeTab === 'search' && (
                            <ul className={style['bookmark-list']}>
                                {searchHistory.map(item => (
                                    <li key={item.id} className={style['bookmark-item']}>
                                        <span className={style['favorite-icon']}>⭐</span>
                                        <span className={style['item-name']}>{item.query}</span>
                                        <button 
                                            className={style['delete-btn']}
                                            onClick={() => handleDeleteSearchHistory(item.id)}
                                        >
                                            ✕
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                </div>
            </aside>
        </section>
    );
};

export default BookmarkPage;
