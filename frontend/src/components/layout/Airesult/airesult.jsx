import React, { useState, useEffect } from 'react';
import style from './airesult.module.css';

// 오늘의 날짜를 YYYY.MM.DD 형식으로 가져오는 함수
const getFormattedDate = () => {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  return `${year}.${month}.${day}`;
};

// 숫자 포맷팅 함수 (예: 60600 -> 60,600)
const formatNumber = (num) => {
  return new Intl.NumberFormat('ko-KR').format(num);
};

// 백엔드에서 받아올 데이터에 대한 더미(dummy) 데이터
const dummyData = {
  totalPrediction: {
    price: 60600,
    changeRate: 1.17,
  },
  modelPredictions: {
    lstm: {
      accuracy: 72,
      predictedPrice: 60000,
      changeRate: 0.17,
    },
    finbert: {
      accuracy: 87,
      predictedPrice: 60500,
      changeRate: 1.00,
    },
    tft: {
      accuracy: 70,
      predictedPrice: 60000,
      changeRate: 1.35,
    },
  },
};

const AiResultCard = ({ modelName, dataType, accuracy, predictedPrice, changeRate, cardColor }) => (
  // AI 개별 결과
  <div className={style.modelCard}>
    <div className={style.modelHeader}>
      <h3 className={style.modelTitle}>{modelName}</h3>
      <span className={style.dataType}>{dataType}</span>
    </div>

    <div className={style.accuracySection}>
      <span>정확도</span>
      <span>{accuracy}%</span>
    </div>

    <div className={style.progressBarContainer}>
      <div className={style.progressBar}></div>
    </div>

    <div className={style.predictionResult} style={{ backgroundColor: `${cardColor}20` /* 20은 투명도 */ }}>
      <p>{getFormattedDate()} '주식이름' 주가 예측</p>
      <p className={style.predictedPrice}>{formatNumber(predictedPrice)} 원</p>
      <p className={style.changeRate}>+{changeRate.toFixed(2)}%</p>
    </div>
  </div>
);

// 메인 AI 예측 결과 컴포넌트
const AiResult = () => {
  const [data, setData] = useState(dummyData); // 실제로는 API 호출로 데이터 설정
  const [activeTab, setActiveTab] = useState('total');

  // useEffect(() => {
  //   // 백엔드에서 데이터를 받아오는 로직
  //   const fetchData = async () => {
  //     // const response = await fetch('your-api-endpoint');
  //     // const result = await response.json();
  //     // setData(result);
  //   };
  //   fetchData();
  // }, []);

  return (
    <div className={style.container}>
        {/*메인 주식 BOX*/}
      <div className={style.content}>
        <div className={style.summaryHeader}>
          <p className={style.togletxt}>3가지의 AI가 종합 예측한</p>
          <select className={style.stockSelect}>
            <option>삼성전자</option>
            {/* 다른 주식 옵션들 */}
          </select>
          <p className={style.togletxt}>의 오늘 주가 변화 예측이에요</p>
        </div>

        {/* 설정 button*/}
        <div className={style.tabContainer}>
        <button
          className={`${style.tabButton} ${activeTab === 'total' ? style.active : ''}`}
          onClick={() => setActiveTab('total')}
        > AI 주가 예측
        </button>
      </div>

        {/* AI total 평가예측 */}
        <div className={style.totalPredictionSection}>
          <div className={style.totalPriceInfo}>
            <p className={style.totalTitle}>주가 변화 예측</p>
            <p className={style.totalPrice}>{formatNumber(data.totalPrediction.price)} 원</p>
            <p className={style.totalChangeRate}>+{data.totalPrediction.changeRate.toFixed(2)}%</p>
          </div>
          <div className={style.priceRangeBar}>
            {/* 이 부분은 각 모델의 예측 가격 위치를 계산하여 동적으로 렌더링해야 합니다. */}
          </div>
        </div>

        <div className={style.modelCardsContainer}>
          <AiResultCard
            modelName="LSTM"
            dataType="주가 Data 학습"
            accuracy={data.modelPredictions.lstm.accuracy}
            predictedPrice={data.modelPredictions.lstm.predictedPrice}
            changeRate={data.modelPredictions.lstm.changeRate}
            cardColor="#00c49f"
          />
          <AiResultCard
            modelName="FinBERT"
            dataType="뉴스 Data 학습"
            accuracy={data.modelPredictions.finbert.accuracy}
            predictedPrice={data.modelPredictions.finbert.predictedPrice}
            changeRate={data.modelPredictions.finbert.changeRate}
            cardColor="#8c54ff"
          />
          <AiResultCard
            modelName="TFT"
            dataType="재무재표 Data 학습"
            accuracy={data.modelPredictions.tft.accuracy}
            predictedPrice={data.modelPredictions.tft.predictedPrice}
            changeRate={data.modelPredictions.tft.changeRate}
            cardColor="#f0c419"
          />
        </div>
      </div>
    </div>
  );
};

export default AiResult;
