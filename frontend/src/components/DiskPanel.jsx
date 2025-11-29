import { useState, useEffect } from 'react'
import { resourceAPI, priceAPI } from '../api/api'
import './ResourcePanel.css'

function DiskPanel({ userId, onAction }) {
  const [disks, setDisks] = useState([])
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [sizeGb, setSizeGb] = useState('100')
  const [prices, setPrices] = useState(null)

  useEffect(() => {
    if (userId) {
      fetchDisks()
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

  const fetchDisks = async () => {
    setLoading(true)
    try {
      const res = await resourceAPI.getDisks(userId)
      setDisks(res.data)
    } catch (error) {
      console.error('Error fetching disks:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async () => {
    const resourceId = `disk-${Date.now()}`
    try {
      await resourceAPI.createDisk(resourceId, userId, parseInt(sizeGb))
      alert('Disk created!')
      setShowCreate(false)
      setSizeGb('100')
      fetchDisks()
      onAction()
    } catch (error) {
      alert('Error: ' + (error.response?.data?.detail || error.message))
    }
  }

  const handleResize = async (resourceId, currentSize) => {
    const newSize = prompt(`Current size: ${currentSize}GB\nEnter new size (GB):`, currentSize)
    if (newSize && parseInt(newSize) !== currentSize) {
      try {
        await resourceAPI.updateDisk(resourceId, null, parseInt(newSize), null)
        alert('Disk resized!')
        fetchDisks()
        onAction()
      } catch (error) {
        alert('Error: ' + (error.response?.data?.detail || error.message))
      }
    }
  }

  const handleDelete = async (resourceId) => {
    if (confirm('Are you sure you want to delete this disk?')) {
      try {
        await resourceAPI.deleteDisk(resourceId)
        alert('Disk deleted!')
        fetchDisks()
        onAction()
      } catch (error) {
        alert('Error: ' + (error.response?.data?.detail || error.message))
      }
    }
  }

  return (
    <div className="resource-panel">
      <div className="panel-header">
        <h2>💾 Disk Volumes</h2>
        <button className="btn-create" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? 'Cancel' : '+ Create Disk'}
        </button>
      </div>

      {showCreate && (
        <div className="create-form">
          <div className="form-group">
            <label>Size (GB):</label>
            <input
              type="number"
              value={sizeGb}
              onChange={(e) => setSizeGb(e.target.value)}
              min="10"
              step="10"
            />
            {prices?.disk && (
              <div className="price-hint">
                Cost: ${parseFloat(sizeGb) * prices.disk.per_gb_hour}/hour
              </div>
            )}
          </div>
          <button className="btn-submit" onClick={handleCreate}>Create</button>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading...</div>
      ) : (
        <div className="resource-list">
          {disks.length > 0 ? (
            disks.map((disk) => (
              <div key={disk.resource_id} className={`resource-card ${disk.deleted_at ? 'deleted' : disk.state}`}>
                <div className="resource-header">
                  <div>
                    <h3>{disk.resource_id}</h3>
                    <span className={`status-badge ${disk.deleted_at ? 'deleted' : disk.state}`}>
                      {disk.deleted_at ? 'deleted' : disk.state}
                    </span>
                  </div>
                  <div className="resource-meta">
                    <div className="resource-size">{disk.size_gb} GB</div>
                    {prices?.disk && (
                      <div className="resource-cost">${disk.size_gb * prices.disk.per_gb_hour}/hr</div>
                    )}
                  </div>
                </div>
                
                <div className="resource-info">
                  <div className="info-item">
                    <span className="label">Created:</span>
                    <span>{new Date(disk.created_at).toLocaleString()}</span>
                  </div>
                  {disk.deleted_at && (
                    <div className="info-item">
                      <span className="label">Deleted:</span>
                      <span>{new Date(disk.deleted_at).toLocaleString()}</span>
                    </div>
                  )}
                  {disk.attached_to && (
                    <div className="info-item">
                      <span className="label">Attached to:</span>
                      <span>{disk.attached_to}</span>
                    </div>
                  )}
                </div>

                {disk.events && disk.events.length > 0 && (
                  <div className="resource-events">
                    <h4>📋 Event History</h4>
                    <div className="events-list">
                      {disk.events.slice().reverse().slice(0, 5).map((event) => (
                        <div key={event.event_id} className="event-item">
                          <span className="event-type">{event.type}</span>
                          <span className="event-meta">
                            {event.meta?.size_gb && `→ ${event.meta.size_gb}GB`}
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
                  {!disk.deleted_at && (disk.state === 'attached' || disk.state === 'detached') && (
                    <>
                      <button className="btn-action btn-info" onClick={() => handleResize(disk.resource_id, disk.size_gb)}>
                        Resize
                      </button>
                      <button className="btn-action btn-danger" onClick={() => handleDelete(disk.resource_id)}>
                        Delete
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className="no-resources">No disk volumes yet. Create one to get started!</div>
          )}
        </div>
      )}
    </div>
  )
}

export default DiskPanel
