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
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    if (password !== confirmPw) {
      setError('비밀번호가 일치하지 않습니다.');
      return;
    }
    
    setLoading(true);
    
    try {
      const response = await fetch('http://localhost:8080/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          accountid: accountid,
          password: password,
          username: username
        })
      });

      const data = await response.json();

      if (data.success) {
        alert('회원가입이 완료되었습니다!');
        navigate('/login');
      } else {
        setError(data.message || '회원가입에 실패했습니다.');
      }
    } catch (error) {
      console.error('회원가입 오류:', error);
      setError('서버 연결에 실패했습니다.');
    } finally {
      setLoading(false);
    }
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
        <button className="join-home-btn" onClick={handleHome}>
          <img src={teamlogo} alt="팀 로고" className="join-logo-img" />
          <h1 className="join-logo-text">FIVE_SENSE</h1>
        </button>
      </div>

      <form className="join-form" onSubmit={handleSubmit}>
        {error && (
          <div className="error-message" style={{ color: 'red', marginBottom: '10px', textAlign: 'center' }}>
            {error}
          </div>
        )}
        
        <div className="join-form-group">
          <label htmlFor="accountid">아이디</label>
          <input
            type="text"
            id="accountid"
            required
            value={accountid}
            onChange={e => setAccountid(e.target.value)}
            disabled={loading}
          />
        </div>

        <div className="join-form-group">
          <label htmlFor="username">사용자명</label>
          <input
            type="text"
            id="username"
            required
            value={username}
            onChange={e => setUsername(e.target.value)}
            disabled={loading}
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
            disabled={loading}
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
            disabled={loading}
          />
        </div>

        <div className="join-login-link">
          <button type="button" className="to-login-btn" onClick={handleLogin}>
            <h3 className="to-login-text">이미 계정이 있으신가요? 로그인</h3>
          </button>
        </div>

        <button className="submit-join-btn" type="submit" disabled={loading}>
          {loading ? '회원가입 중...' : '회원가입'}
        </button>
      </form>
    </div>
  );
};

export default Join;
