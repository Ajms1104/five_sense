// components/Login.jsx
// 로그인
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import style from './login.module.css';

/* 이미지 모음 */
import teamlogo from '../../assets/teamlogo.png';

const Login = () => {
  const navigate = useNavigate();
  const [accountid, setAccountid] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log('로그인 시도:', accountid, password);
    localStorage.setItem('isLoggedIn', 'true');
    navigate('/');
  };

  const handleHome = () => {
    navigate('/');
  };

  const handleJoin = () => {
    navigate('/join');
  };

  return (
    <div className={style['login-container']}>
      <form className={style['login-input-form']} onSubmit={handleSubmit}>
        <div className={style.title}>
          <img src={teamlogo} alt="팀 로고" className={style['login_logo_png']} />
          <h1 className={style['login-logo-txt']}>FIVE_SENSE</h1>
        </div>
        
        <div className={style['form-group']}>
          <label htmlFor="accountid">아이디</label>
          <input
            type="text"
            id="accountid"
            name="accountid"
            required
            value={accountid}
            onChange={e => setAccountid(e.target.value)}
          />
        </div>

        <div className={style['form-group']}>
          <label htmlFor="password">비밀번호</label>
          <input
            type="password"
            id="password"
            name="password"
            required
            value={password}
            onChange={e => setPassword(e.target.value)}
          />
        </div>
        <button className={style.login_btn} type="submit">로그인</button>
        <button className={style.join_btn} type="button" onClick={handleJoin}> 회원가입 </button>
      </form>
    </div>
  );
};

export default Login;
