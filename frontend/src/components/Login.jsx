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
    // 로그인 처리 로직
    console.log('로그인 시도:', accountid, password);
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
          <button className="main_btn" onClick={handleHome}>
            <img src={teamlogo} alt="팀 로고" className="login_logo_png" />
            <h1 className="login-logo-txt">FIVE_SENSE</h1>
          </button>
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
