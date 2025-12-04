import React from 'react';

export default function Footer() {
  return (
    <footer className="w-full border-t border-gray-200 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-12 flex items-center justify-between text-sm text-gray-600">
        <span>© 2024 Hybrid AI Location App</span>
        <div className="flex items-center gap-4">
          <a href="/docs" className="hover:underline">Docs</a>
          <a href="https://openstreetmap.org" target="_blank" rel="noreferrer" className="hover:underline">OSM</a>
        </div>
      </div>
    </footer>
  );
}





