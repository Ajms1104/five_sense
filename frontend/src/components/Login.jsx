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
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch('http://localhost:8080/api/auth/login', {
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
        // 로그인 성공
        console.log('로그인 성공:', data.user);
        // 사용자 정보를 localStorage에 저장
        localStorage.setItem('user', JSON.stringify(data.user));
        // 메인 페이지로 이동
        navigate('/');
      } else {
        // 로그인 실패
        setError(data.message || '로그인에 실패했습니다.');
      }
    } catch (error) {
      console.error('로그인 오류:', error);
      setError('서버 연결에 실패했습니다.');
    } finally {
      setLoading(false);
    }
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
        
        {error && (
          <div className="error-message" style={{ color: 'red', marginBottom: '10px' }}>
            {error}
          </div>
        )}
        
        <div className="form-group">
          <label htmlFor="accountid">아이디</label>
          <input
            type="text"
            id="accountid"
            name="accountid"
            required
            value={accountid}
            onChange={e => setAccountid(e.target.value)}
            disabled={loading}
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
            disabled={loading}
          />
        </div>
        
        <div className="join-group">
          <button className="join_btn" type="button" onClick={handleJoin} disabled={loading}>
            <h3 className='Join-txt'> 회원가입 </h3>
          </button>
        </div>
        
        <button className="login_btn" type="submit" disabled={loading}>
          {loading ? '로그인 중...' : '로그인'}
        </button>
      </form>
    </div>
  );
};

export default Login;
