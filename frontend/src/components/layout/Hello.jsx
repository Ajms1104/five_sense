import React, { useEffect, useState } from "react";
import axios from "axios";

function Hello() {
  const [message, setMessage] = useState("");

  useEffect(() => {
    axios.get("http://localhost:8080/hello")
      .then(res => {
        setMessage(res.data); // "Spring Boot 연결 성공!"
      })
      .catch(err => {
        console.error("연결 실패:", err);
        setMessage("연결 실패");
      });
  }, []);

  return (
    <div>
      <h1>React - Spring Boot 연결 테스트</h1>
      <p>{message}</p>
    </div>
  );
}

export default Hello;
