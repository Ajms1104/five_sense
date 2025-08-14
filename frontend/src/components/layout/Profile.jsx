import React, { useEffect, useRef } from 'react';

const Profile = () => {
  const profileRef = useRef(null);

  useEffect(() => {
    if (!profileRef.current) return;

    const handleProfileClick = () => {
      const profileMenu = document.getElementById('profileMenu');
      if (profileMenu) {
        profileMenu.classList.toggle('show');
      }
    };

    profileRef.current.addEventListener('click', handleProfileClick);

    return () => {
      if (profileRef.current) {
        profileRef.current.removeEventListener('click', handleProfileClick);
      }
    };
  }, []);

  return (
    <div className="profile-container">
      <div ref={profileRef} className="profile">
        <img src="/images/profile.png" alt="Profile" />
      </div>
      <div id="profileMenu" className="profile-menu">
        <ul>
          <li><a href="#settings">설정</a></li>
          <li><a href="#logout">로그아웃</a></li>
        </ul>
      </div>
    </div>
  );
};

export default Profile; 