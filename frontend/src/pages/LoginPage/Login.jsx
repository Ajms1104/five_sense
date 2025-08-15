// components/Login.jsx
// 로그인
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext.jsx';

import style from './login.module.css';

/* 이미지 모음 */
import teamlogo from '../../assets/teamlogo.png';

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [accountid, setAccountid] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    console.log('로그인 시도:', accountid, password);
    
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          accountid: accountid,
          password: password
        })
      });

      const data = await response.json();
      
      if (data.success) {
        console.log('로그인 성공:', data.message);
        localStorage.setItem('isLoggedIn', 'true');
        localStorage.setItem('user', JSON.stringify(data.user));
        login(); // AuthContext의 login 함수 호출
        navigate('/');
      } else {
        console.log('로그인 실패:', data.message);
        alert(data.message || '로그인에 실패했습니다.');
      }
    } catch (error) {
      console.error('로그인 요청 중 오류:', error);
      alert('로그인 처리 중 오류가 발생했습니다.');
    }
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
