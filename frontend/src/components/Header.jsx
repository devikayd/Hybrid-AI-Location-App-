import React from 'react';

export default function Header() {
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';
  const isLocal = apiBase.includes('localhost');

  return (
    <header className="w-full border-b border-gray-200 bg-white sticky top-0 z-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-primary-600" />
          <h1 className="text-lg font-semibold text-gray-900">Hybrid AI Location App (UK)</h1>
        </div>
        <div className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-700 border border-gray-200">
          {isLocal ? 'Local Dev' : 'Remote API'}
        </div>
      </div>
    </header>
  );
}





