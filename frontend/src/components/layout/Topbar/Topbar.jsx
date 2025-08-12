import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../contexts/AuthContext.jsx';

import style from './topbar.module.css';
import UserIcon from '../../../assets/User.svg';
import popup from '../../../assets/popupbtn.svg';
import login from '../../../assets/login.svg';
import logout from '../../../assets/logout.svg';

function Topbar() {
  const navigate = useNavigate();
  const { isLoggedIn, logout } = useAuth(); 
  const [isPopupVisible, setIsPopupVisible] = useState(false);
  const [hideTimer, setHideTimer] = useState(null);

  const handleLogin = () => { navigate('/login'); };
  const handleLogout = () => {
    logout();
    setIsPopupVisible(false);
    navigate('/login');
  };

  const handleMouseEnter = () => {
    if (hideTimer) {
      clearTimeout(hideTimer);
    }
    setIsPopupVisible(true);
  };

  const handleMouseLeave = () => {
    const timer = setTimeout(() => {
      setIsPopupVisible(false);
    }, 200);
    setHideTimer(timer);
  };

  return (
    <aside className={style['top-bar']}>
      <div className={style['user-bar']}>
        <button className={style.user_btn}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}>
          <img src={UserIcon} alt="user" className={style.user}/>
          {isPopupVisible && (
            <div className={style.popupbar}>
              <img src={popup} className={style.popup_btn}/>
              {isLoggedIn ? (
                <button onClick={handleLogout} className={style.popup_txt}>
                  <img src={logout} className={style.loginout_btn}/>
                  로그아웃
                </button>
               ) : (
                <button onClick={handleLogin} className={style.popup_txt}>
                  <img src={login} className={style.loginout_btn} />
                  로그인
                </button>
              )}
            </div>
          )}
        </button>
      </div>
    </aside>
  );
}

export default Topbar;
