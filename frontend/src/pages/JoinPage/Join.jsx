// components/Join.jsx
// 회원가입
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import style from './join.module.css';

import teamlogo from '../../assets/teamlogo.png';

const Join = () => {
  const navigate = useNavigate();
  const [accountid, setAccountid] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [email, setEmail] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // 입력 검증
    if (password !== confirmPw) {
      alert('비밀번호가 일치하지 않습니다.');
      return;
    }
    
    console.log('회원가입 시도:', { accountid, username, password, email });
    
    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          accountid: accountid,
          username: username,
          password: password,
          email: email
        })
      });

      const data = await response.json();
      
      if (data.success) {
        console.log('회원가입 성공:', data.message);
        alert('회원가입이 완료되었습니다. 로그인해주세요.');
        navigate('/login');
      } else {
        console.log('회원가입 실패:', data.message);
        alert(data.message || '회원가입에 실패했습니다.');
      }
    } catch (error) {
      console.error('회원가입 요청 중 오류:', error);
      alert('회원가입 처리 중 오류가 발생했습니다.');
    }
  };

  const handleHome = () => {
    navigate('/');
  };

  const handleLogin = () => {
    navigate('/login');
  };

  return (
    <div className={style['join-container']}>
      <form className={style['join-form']} onSubmit={handleSubmit}>
        <div className={style['join-header']}>
          <img src={teamlogo} alt="팀 로고" className={style['join-logo-img']} />
          <h1 className={style['join-logo-text']}>FIVE_SENSE</h1>
        </div>

        <div className={style['join-form-group']}>
          <label htmlFor="accountid">아이디</label>
          <input
            type="text"
            id="accountid"
            required
            value={accountid}
            onChange={e => setAccountid(e.target.value)}
          />
        </div>

        <div className={style['join-form-group']}>
          <label htmlFor="username">닉네임</label>
          <input
            type="text"
            id="username"
            required
            value={username}
            onChange={e => setUsername(e.target.value)}
          />
        </div>

        <div className={style['join-form-group']}>
          <label htmlFor="email">이메일</label>
          <input
            type="email"
            id="email"
            required
            value={email}
            onChange={e => setEmail(e.target.value)}
          />
        </div>

        <div className={style['join-form-group']}>
          <label htmlFor="password">비밀번호</label>
          <input
            type="password"
            id="password"
            required
            value={password}
            onChange={e => setPassword(e.target.value)}
          />
        </div>

        <div className={style['join-form-group']}>
          <label htmlFor="confirmPw">비밀번호 확인</label>
          <input
            type="password"
            id="confirmPw"
            required
            value={confirmPw}
            onChange={e => setConfirmPw(e.target.value)}
          />
        </div>

        <div className={style['join-login-link']}>
          <button type="button" className={style['to-login-btn']} onClick={handleLogin}>
            <h3 className={style['to-login-text']}>이미 계정이 있으신가요? 로그인</h3>
          </button>
        </div>
        <button className={style['submit-join-btn']} type="submit">회원가입
        </button>
      </form>
    </div>
  );
};

export default Join;
