import React, { useEffect } from 'react'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import MapView from './components/MapView'
import SidePanel from './components/SidePanel'
import Footer from './components/Footer'
import ChatPanel from './components/ChatPanel'
import { useMapStore } from './stores/mapStore'

function App() {
  const hydrate = useMapStore((s) => s.hydrate)

  useEffect(() => { hydrate() }, [hydrate])

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1">
        <div className="max-w-[95vw] mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-col lg:flex-row gap-4">
          <div className="flex-1 space-y-4">
            <SearchBar />
            <MapView />
          </div>
          <div className="w-full lg:w-80 flex-shrink-0">
            <SidePanel />
          </div>
        </div>
      </main>

      <Footer />

      {/* Chat Panel - floating bottom-right */}
      <ChatPanel />
    </div>
  )
}

export default App
