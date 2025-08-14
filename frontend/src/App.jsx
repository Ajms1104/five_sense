// App.jsx
import React from 'react';
import { Routes, Route } from 'react-router-dom';
import HOME from './pages/HOME.jsx';
import Bookmark from './pages/BookmarkPage/Bookmark.jsx';
import Login from './pages/LoginPage/Login.jsx'; 
import Join from './pages/JoinPage/Join.jsx';

function App() {
  return (
    <Routes>
      <Route path="/" element={<HOME />} />
      <Route path="/bookmark" element={<Bookmark />} />
      <Route path="/login" element={<Login />} />
      <Route path="/join" element={<Join />} />
    </Routes>
  );
}

export default App;
