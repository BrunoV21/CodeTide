import React, { useState, useEffect } from 'react';

const LoadingMessage = ({ messages = ['Working...', 'Syncing CodeTide', 'Thinking...', 'Looking for context'], interval = 3000 }) => {
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentIndex((prevIndex) => (prevIndex + 1) % messages.length);
    }, interval);

    return () => clearInterval(timer);
  }, [messages.length, interval]);

  /* TODO update styles and fonts to match current - increase size a bit*/
  const loadingWaveStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 12px',
    background: 'rgba(255, 255, 255, 0.05)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '20px',
    backdropFilter: 'blur(10px)',
    color: '#e0e0e0',
    fontSize: '12px',
    fontWeight: '500',
    letterSpacing: '0.3px',
    minHeight: '20px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif'
  };

  const waveContainerStyle = {
    display: 'flex',
    gap: '2px'
  };

  const waveDotStyle = {
    width: '3px',
    height: '3px',
    background: '#00d4ff',
    borderRadius: '50%',
    animation: 'wave 1.2s ease-in-out infinite'
  };

  const loadingTextStyle = {
    minWidth: '120px',
    transition: 'opacity 0.3s ease-in-out'
  };

  return (
    <>
      <style>
        {`
          @keyframes wave {
            0%, 60%, 100% {
              transform: scaleY(1);
              opacity: 0.4;
            }
            30% {
              transform: scaleY(2.5);
              opacity: 1;
            }
          }
        `}
      </style>
      <div style={loadingWaveStyle}>
        <div style={waveContainerStyle}>
          <div style={{...waveDotStyle, animationDelay: '0s'}}></div>
          <div style={{...waveDotStyle, animationDelay: '0.15s'}}></div>
          <div style={{...waveDotStyle, animationDelay: '0.3s'}}></div>
          <div style={{...waveDotStyle, animationDelay: '0.45s'}}></div>
        </div>
        <div style={loadingTextStyle}>
          {messages[currentIndex]}
        </div>
      </div>
    </>
  );
};

export default LoadingMessage;