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
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showUserPopup, setShowUserPopup] = useState(false);
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);
  
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

  // 즐겨찾기 목록 가져오기
  const fetchFavorites = async (accountid) => {
    try {
      setLoading(true);
      const response = await fetch(`http://localhost:8080/api/favorites/${accountid}`);
      
      if (response.ok) {
        const data = await response.json();
        setFavorites(data);
      } else {
        setError('즐겨찾기 목록을 가져오는데 실패했습니다.');
      }
    } catch (error) {
      console.error('즐겨찾기 목록 로딩 에러:', error);
      setError('즐겨찾기 목록을 가져오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // 즐겨찾기 삭제
  const handleRemoveFavorite = async (stockCode) => {
    try {
      const userStr = localStorage.getItem('user');
      if (!userStr) {
        alert('로그인이 필요합니다.');
        return;
      }
      
      const user = JSON.parse(userStr);
      const accountid = user.accountid;
      
      const response = await fetch(`http://localhost:8080/api/favorites/${accountid}/${stockCode}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        alert('즐겨찾기에서 삭제되었습니다.');
        // 목록 새로고침
        fetchFavorites(accountid);
      } else {
        alert('즐겨찾기 삭제에 실패했습니다.');
      }
    } catch (error) {
      console.error('즐겨찾기 삭제 오류:', error);
      alert('즐겨찾기 삭제 중 오류가 발생했습니다.');
    }
  };

  // 컴포넌트 마운트 시 즐겨찾기 목록 가져오기
  React.useEffect(() => {
    const userStr = localStorage.getItem('user');
    if (userStr) {
      const user = JSON.parse(userStr);
      setCurrentUser(user);
      fetchFavorites(user.accountid);
    } else {
      setLoading(false);
      setError('로그인이 필요합니다.');
    }
  }, []);

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

        {/* 메인화면 / 즐겨찾기 */}
        <aside className="b-main-bar">
            <div className="bookmark-top">
                <h3 className="bookmark_name">즐겨찾기</h3>
                <p className="line_6"></p>
                <div className="bookmark-side">
                    <button className='mark_chart'>📈  주식</button>
                    <button className='mark_search'>🕜  검색 기록</button>
                    <p className='line_7'></p>
                </div>
                
                {/* 즐겨찾기 목록 */}
                <div className='bookmark-center'>
                    {loading ? (
                        <div className="loading">즐겨찾기 목록을 불러오는 중...</div>
                    ) : error ? (
                        <div className="error">{error}</div>
                    ) : favorites.length === 0 ? (
                        <div className="empty-favorites">
                            <p>즐겨찾기한 주식이 없습니다.</p>
                            <p>홈에서 주식을 선택하고 즐겨찾기에 추가해보세요!</p>
                        </div>
                    ) : (
                        <div className="favorites-list">
                            <h4>즐겨찾기한 주식 목록</h4>
                            {favorites.map((favorite, index) => (
                                <div key={index} className="favorite-item">
                                    <div className="favorite-info">
                                        <span className="stock-name">{favorite.stockName}</span>
                                        <span className="stock-code">({favorite.stockCode})</span>
                                    </div>
                                    <div className="favorite-actions">
                                        <button 
                                            className="view-chart-btn"
                                            onClick={() => navigate(`/?stock=${favorite.stockCode}`)}
                                        >
                                            📈 차트보기
                                        </button>
                                        <button 
                                            className="remove-favorite-btn"
                                            onClick={() => handleRemoveFavorite(favorite.stockCode)}
                                        >
                                            ❌ 삭제
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </aside>
    </section>
  );
};

export default Bookmark;
