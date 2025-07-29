// App.jsx
import React from 'react';
import { Routes, Route } from 'react-router-dom';
import HOME from './components/HOME.jsx';
import Bookmark from './components/Bookmark.jsx';
import Login from './components/Login.jsx'; 
import Join from './components/Join.jsx' 

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
