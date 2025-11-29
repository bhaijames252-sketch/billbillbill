import { useState, useEffect } from 'react'
import { resourceAPI, priceAPI } from '../api/api'
import './ResourcePanel.css'

function FloatingIPPanel({ userId, onAction }) {
  const [floatingIPs, setFloatingIPs] = useState([])
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [prices, setPrices] = useState(null)

  useEffect(() => {
    if (userId) {
      fetchFloatingIPs()
    }
    fetchPrices()
  }, [userId])

  const fetchPrices = async () => {
    try {
      const res = await priceAPI.getPriceByCurrency('USD')
      setPrices(res.data)
    } catch (error) {
      console.error('Error fetching prices:', error)
    }
  };

  const fetchFloatingIPs = async () => {
    setLoading(true)
    try {
      const res = await resourceAPI.getFloatingIPs(userId)
      setFloatingIPs(res.data)
    } catch (error) {
      console.error('Error fetching floating IPs:', error)
    } finally {
      setLoading(false)
    }
  }

  const generateRandomIP = () => {
    return `${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}`
  }

  const handleCreate = async () => {
    const resourceId = `fip-${Date.now()}`
    const ipAddress = generateRandomIP()
    try {
      await resourceAPI.createFloatingIP(resourceId, userId, ipAddress)
      alert(`Floating IP created: ${ipAddress}`)
      setShowCreate(false)
      fetchFloatingIPs()
      onAction()
    } catch (error) {
      alert('Error: ' + (error.response?.data?.detail || error.message))
    }
  }

  const handleDelete = async (resourceId) => {
    if (confirm('Are you sure you want to release this floating IP?')) {
      try {
        await resourceAPI.deleteFloatingIP(resourceId)
        alert('Floating IP released!')
        fetchFloatingIPs()
        onAction()
      } catch (error) {
        alert('Error: ' + (error.response?.data?.detail || error.message))
      }
    }
  }

  return (
    <div className="resource-panel">
      <div className="panel-header">
        <h2>🌐 Floating IPs</h2>
        <button className="btn-create" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? 'Cancel' : '+ Allocate IP'}
        </button>
      </div>

      {showCreate && (
        <div className="create-form">
          <p>A random IP address will be allocated.</p>
          {prices?.floating_ip && (
            <div className="price-hint">
              Cost: ${prices.floating_ip.per_hour}/hour
            </div>
          )}
          <button className="btn-submit" onClick={handleCreate}>Allocate</button>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading...</div>
      ) : (
        <div className="resource-list">
          {floatingIPs.length > 0 ? (
            floatingIPs.map((fip) => (
              <div key={fip.resource_id} className={`resource-card ${fip.released_at ? 'released' : ''}`}>
                <div className="resource-header">
                  <div>
                    <h3>{fip.resource_id}</h3>
                    <span className={`status-badge ${fip.released_at ? 'released' : 'active'}`}>
                      {fip.released_at ? 'released' : 'active'}
                    </span>
                  </div>
                  <div className="resource-meta">
                    <div className="resource-ip">{fip.ip_address}</div>
                    {prices?.floating_ip && (
                      <div className="resource-cost">${prices.floating_ip.per_hour}/hr</div>
                    )}
                  </div>
                </div>
                
                <div className="resource-info">
                  <div className="info-item">
                    <span className="label">Created:</span>
                    <span>{new Date(fip.created_at).toLocaleString()}</span>
                  </div>
                  {fip.released_at && (
                    <div className="info-item">
                      <span className="label">Released:</span>
                      <span>{new Date(fip.released_at).toLocaleString()}</span>
                    </div>
                  )}
                  {fip.attached_to && (
                    <div className="info-item">
                      <span className="label">Attached to:</span>
                      <span>{fip.attached_to}</span>
                    </div>
                  )}
                </div>

                {fip.events && fip.events.length > 0 && (
                  <div className="resource-events">
                    <h4>📋 Event History</h4>
                    <div className="events-list">
                      {fip.events.slice().reverse().slice(0, 5).map((event) => (
                        <div key={event.event_id} className="event-item">
                          <span className="event-type">{event.type}</span>
                          <span className="event-meta">
                            {event.meta?.attached_to && `→ ${event.meta.attached_to}`}
                          </span>
                          <span className="event-time">
                            {new Date(event.time).toLocaleString()}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="resource-actions">
                  {!fip.released_at && (
                    <button className="btn-action btn-danger" onClick={() => handleDelete(fip.resource_id)}>
                      Release
                    </button>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className="no-resources">No floating IPs yet. Allocate one to get started!</div>
          )}
        </div>
      )}
    </div>
  )
}

export default FloatingIPPanel
