// components/Login.jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/login.css';

/* 이미지 모음 */
import teamlogo from '../assets/teamlogo.png';

const Login = () => {
  const navigate = useNavigate();
  const [accountid, setAccountid] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    // 로그인 처리 로직 (실제 API 호출로 대체하세요; 여기서는 성공 가정)
    console.log('로그인 시도:', accountid, password);
    
    // 로그인 성공 시 localStorage 설정 (실제로는 API 응답 후 설정)
    localStorage.setItem('isLoggedIn', 'true');
    navigate('/');  // 성공 시 홈으로 이동
  };

  const handleHome = () => {
    navigate('/');
  };

  const handleJoin = () => {
    navigate('/join');
  };

  return (
    <div className="login-container">
      <form className='login-input-form' onSubmit={handleSubmit}>
        <div className="title">
            <img src={teamlogo} alt="팀 로고" className="login_logo_png" />
            <h1 className="login-logo-txt">FIVE_SENSE</h1>
        </div>
        <div className="form-group">
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

        <div className="form-group">
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
        <div className="join-group">
          <button className="join_btn" type="button" onClick={handleJoin}>
            <h3 className='Join-txt'> 회원가입 </h3>
          </button>
        </div>
        <button className="login_btn" type="submit">로그인</button>
      </form>
    </div>
  );
};

export default Login;
