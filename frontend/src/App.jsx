import { useState } from 'react'
import Sidebar from './components/Sidebar'
import ComputePanel from './components/ComputePanel'
import DiskPanel from './components/DiskPanel'
import FloatingIPPanel from './components/FloatingIPPanel'
import PriceInfo from './components/PriceInfo'
import './App.css'

function App() {
  const [userId, setUserId] = useState('user-001')
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const handleRefresh = () => {
    setRefreshTrigger(prev => prev + 1)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>🌩️ BillingCloud Test UI</h1>
        <div className="user-selector">
          <label>User ID:</label>
          <input
            type="text"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="Enter user ID"
          />
        </div>
      </header>
      
      <div className="app-content">
        <main className="main-content">
          <PriceInfo />
          <ComputePanel userId={userId} onAction={handleRefresh} />
          <DiskPanel userId={userId} onAction={handleRefresh} />
          <FloatingIPPanel userId={userId} onAction={handleRefresh} />
        </main>
        
        <Sidebar userId={userId} refreshTrigger={refreshTrigger} />
      </div>
    </div>
  )
}

export default App
