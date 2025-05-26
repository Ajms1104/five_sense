// src/components/Join.jsx
import React, { useState } from 'react';
import '../styles/join.css';


const Join = () => {
  const [form, setForm] = useState({
    accountid: '',
    password: '',
    username: '',
  });

  const handleChange = (e) => {
    setForm({
      ...form,
      [e.target.id]: e.target.value,
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // 실제 회원가입 처리 로직 (fetch/axios 등)
    // 예시:
    // fetch('/register', { method: 'POST', body: JSON.stringify(form), ... })
    alert('회원가입 정보: ' + JSON.stringify(form, null, 2));
  };

  return (
    <div className="container">
      <h2>회원가입</h2>
      <form action="/register" method="post" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="accountid">아이디:</label>
          <input
            type="text"
            id="accountid"
            value={form.accountid}
            onChange={handleChange}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="password">비밀번호:</label>
          <input
            type="password"
            id="password"
            value={form.password}
            onChange={handleChange}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="username">이름:</label>
          <input
            type="text"
            id="username"
            value={form.username}
            onChange={handleChange}
            required
          />
        </div>
        <button type="submit">가입하기</button>
      </form>
      <div className="login-link">
        <a href="/login">로그인으로 돌아가기</a>
      </div>
    </div>
  );
};

export default Join;