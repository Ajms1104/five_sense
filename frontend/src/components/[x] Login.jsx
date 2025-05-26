// src/components/Login.jsx
import React, { useState } from 'react';
import '../styles/login.css';

const Login = () => {
  const [accountid, setAccountid] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    // 로그인 처리 로직
  };

  return (
    <div className="container">
      <h2>로그인</h2>
      <form action="/login" method="post" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="accountid">아이디:</label>
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
          <label htmlFor="password">비밀번호:</label>
          <input
            type="password"
            id="password"
            name="password"
            required
            value={password}
            onChange={e => setPassword(e.target.value)}
          />
        </div>
        <button type="submit">로그인</button>
      </form>
      <div className="register-link">
        <a href="/register">회원가입</a>
      </div>
    </div>
  );
};

export default Login;
