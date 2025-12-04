import React from 'react';

type SlideOutPanelProps = {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
};

const SlideOutPanel: React.FC<SlideOutPanelProps> = ({ isOpen, onClose, children }) => {
  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 transition-opacity duration-300 z-40"
          onClick={onClose}
        />
      )}
      
      {/* Panel */}
      <div 
        className={`fixed top-0 right-0 h-full w-full md:w-[600px] lg:w-[700px] bg-gray-900 shadow-2xl transform transition-transform duration-300 ease-in-out z-50 ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="p-6 h-full overflow-hidden flex flex-col">
          {children}
        </div>
      </div>
    </>
  );
};

export default SlideOutPanel;