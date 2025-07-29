// components/Join.jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/join.css';
import teamlogo from '../assets/teamlogo.png';

const Join = () => {
  const navigate = useNavigate();
  const [accountid, setAccountid] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [email, setEmail] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (password !== confirmPw) {
      alert('비밀번호가 일치하지 않습니다.');
      return;
    }
    console.log('회원가입 시도:', { accountid, password, email });
    // 회원가입 처리 로직
  };

  const handleHome = () => {
    navigate('/');
  };

  const handleLogin = () => {
    navigate('/login');
  };

  return (
    <div className="join-container">
      <div className="join-header">
          <img src={teamlogo} alt="팀 로고" className="join-logo-img" />
          <h1 className="join-logo-text">FIVE_SENSE</h1>
      </div>

      <form className="join-form" onSubmit={handleSubmit}>
        <div className="join-form-group">
          <label htmlFor="accountid">아이디</label>
          <input
            type="text"
            id="accountid"
            required
            value={accountid}
            onChange={e => setAccountid(e.target.value)}
          />
        </div>

        <div className="join-form-group">
          <label htmlFor="email">이메일</label>
          <input
            type="email"
            id="email"
            required
            value={email}
            onChange={e => setEmail(e.target.value)}
          />
        </div>

        <div className="join-form-group">
          <label htmlFor="password">비밀번호</label>
          <input
            type="password"
            id="password"
            required
            value={password}
            onChange={e => setPassword(e.target.value)}
          />
        </div>

        <div className="join-form-group">
          <label htmlFor="confirmPw">비밀번호 확인</label>
          <input
            type="password"
            id="confirmPw"
            required
            value={confirmPw}
            onChange={e => setConfirmPw(e.target.value)}
          />
        </div>

        <div className="join-login-link">
          <button type="button" className="to-login-btn" onClick={handleLogin}>
            <h3 className="to-login-text">이미 계정이 있으신가요? 로그인</h3>
          </button>
        </div>
        <button className="submit-join-btn" type="submit">회원가입</button>
      </form>
    </div>
  );
};

export default Join;
