import React, { useEffect } from 'react'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import MapView from './components/MapView'
import SidePanel from './components/SidePanel'
import Footer from './components/Footer'
import { useMapStore } from './stores/mapStore'

function App() {
  const hydrate = useMapStore((s) => s.hydrate)

  useEffect(() => { hydrate() }, [hydrate])

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-4">
            <SearchBar />
            <MapView />
          </div>
          <div>
            <SidePanel />
          </div>
        </div>
      </main>

      <Footer />
    </div>
  )
}

export default App
