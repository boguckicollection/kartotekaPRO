import React, { useEffect } from 'react';

type ToastProps = {
  message: string;
  onClose: () => void;
  duration?: number;
  type?: 'info' | 'success' | 'error';
};

const Toast: React.FC<ToastProps> = ({ message, onClose, duration = 5000, type = 'info' }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose();
    }, duration);

    return () => {
      clearTimeout(timer);
    };
  }, [onClose, duration]);

  const colorClasses = {
    info: 'bg-blue-500',
    success: 'bg-green-600',
    error: 'bg-red-600',
  };

  return (
    <div className={`fixed top-4 right-4 text-white p-4 rounded-lg shadow-lg animate-fade-in-right ${colorClasses[type]}`}>
      <div className="flex justify-between items-center">
        <span>{message}</span>
        <button onClick={onClose} className="ml-4 text-white font-bold">X</button>
      </div>
    </div>
  );
};

export default Toast;