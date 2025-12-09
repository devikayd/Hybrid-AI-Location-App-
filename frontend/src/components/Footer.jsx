import React from 'react';

export default function Footer() {
  const currentYear = new Date().getFullYear();
  
  return (
    <footer className="w-full border-t border-gray-200 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-12 flex items-center justify-between text-sm text-gray-600">
        <span>© {currentYear} Hybrid AI Location App</span>
        <div className="flex items-center gap-1">
          <span className="text-gray-500">Created by</span>
          <a href="https://www.linkedin.com/in/devika-y-d-5a4a6b169/" target="_blank" rel="noreferrer" className="hover:underline style-italic">@devikayd</a>
        </div>
      </div>
    </footer>
  );
}





