import { useState, useEffect } from 'react'
import { priceAPI } from '../api/api'
import './PriceInfo.css'

function PriceInfo() {
  const [prices, setPrices] = useState(null)
  const [loading, setLoading] = useState(true)
  const [currency, setCurrency] = useState('USD')

  useEffect(() => {
    fetchPrices()
  }, [currency])

  const fetchPrices = async () => {
    setLoading(true)
    try {
      const res = await priceAPI.getPriceByCurrency(currency)
      setPrices(res.data)
    } catch (error) {
      console.error('Error fetching prices:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="price-info loading">Loading prices...</div>

  if (!prices) return null

  return (
    <div className="price-info">
      <div className="price-header">
        <h3>💰 Current Pricing</h3>
        <span className="price-version">v{prices.price_version}</span>
      </div>
      
      <div className="price-sections">
        <div className="price-section">
          <h4>💻 Compute Instances</h4>
          <div className="price-list">
            {prices.compute && Object.entries(prices.compute).map(([flavor, rate]) => (
              <div key={flavor} className="price-item">
                <span className="flavor-name">{flavor}</span>
                <span className="price-value">${rate.per_hour}/hour</span>
              </div>
            ))}
          </div>
        </div>

        <div className="price-section">
          <h4>💾 Disk Storage</h4>
          <div className="price-list">
            <div className="price-item">
              <span className="flavor-name">Per GB</span>
              <span className="price-value">${prices.disk?.per_gb_hour}/GB/hour</span>
            </div>
          </div>
        </div>

        <div className="price-section">
          <h4>🌐 Floating IP</h4>
          <div className="price-list">
            <div className="price-item">
              <span className="flavor-name">Per IP</span>
              <span className="price-value">${prices.floating_ip?.per_hour}/hour</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default PriceInfo
