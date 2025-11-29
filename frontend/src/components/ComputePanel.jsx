import { useState, useEffect } from 'react'
import { resourceAPI, priceAPI } from '../api/api'
import './ResourcePanel.css'

function ComputePanel({ userId, onAction }) {
  const [computes, setComputes] = useState([])
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [flavor, setFlavor] = useState('small')
  const [prices, setPrices] = useState(null)

  useEffect(() => {
    if (userId) {
      fetchComputes()
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

  const fetchComputes = async () => {
    setLoading(true)
    try {
      const res = await resourceAPI.getComputes(userId)
      setComputes(res.data)
    } catch (error) {
      console.error('Error fetching computes:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async () => {
    const resourceId = `compute-${Date.now()}`
    try {
      await resourceAPI.createCompute(resourceId, userId, flavor)
      alert('Compute instance created!')
      setShowCreate(false)
      fetchComputes()
      onAction()
    } catch (error) {
      alert('Error: ' + (error.response?.data?.detail || error.message))
    }
  }

  const handleStateChange = async (resourceId, newState) => {
    try {
      await resourceAPI.updateCompute(resourceId, newState)
      alert(`Instance ${newState}!`)
      fetchComputes()
      onAction()
    } catch (error) {
      alert('Error: ' + (error.response?.data?.detail || error.message))
    }
  }

  const handleResize = async (resourceId, currentFlavor) => {
    const newFlavor = prompt(`Current flavor: ${currentFlavor}\nEnter new flavor (small/medium/large):`, currentFlavor)
    if (newFlavor && newFlavor !== currentFlavor) {
      try {
        await resourceAPI.updateCompute(resourceId, null, newFlavor)
        alert('Instance resized!')
        fetchComputes()
        onAction()
      } catch (error) {
        alert('Error: ' + (error.response?.data?.detail || error.message))
      }
    }
  }

  const handleDelete = async (resourceId) => {
    if (confirm('Are you sure you want to delete this instance?')) {
      try {
        await resourceAPI.deleteCompute(resourceId)
        alert('Instance deleted!')
        fetchComputes()
        onAction()
      } catch (error) {
        alert('Error: ' + (error.response?.data?.detail || error.message))
      }
    }
  }

  return (
    <div className="resource-panel">
      <div className="panel-header">
        <h2>💻 Compute Instances</h2>
        <button className="btn-create" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? 'Cancel' : '+ Create Instance'}
        </button>
      </div>

      {showCreate && (
        <div className="create-form">
          <div className="form-group">
            <label>Flavor:</label>
            <select value={flavor} onChange={(e) => setFlavor(e.target.value)}>
              <option value="small">
                Small (1 vCPU, 2GB RAM) {prices?.compute?.small ? `- $${prices.compute.small.per_hour}/hr` : ''}
              </option>
              <option value="medium">
                Medium (2 vCPU, 4GB RAM) {prices?.compute?.medium ? `- $${prices.compute.medium.per_hour}/hr` : ''}
              </option>
              <option value="large">
                Large (4 vCPU, 8GB RAM) {prices?.compute?.large ? `- $${prices.compute.large.per_hour}/hr` : ''}
              </option>
            </select>
          </div>
          <button className="btn-submit" onClick={handleCreate}>Create</button>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading...</div>
      ) : (
        <div className="resource-list">
          {computes.length > 0 ? (
            computes.map((compute) => (
              <div key={compute.resource_id} className={`resource-card ${compute.deleted_at ? 'deleted' : compute.state}`}>
                <div className="resource-header">
                  <div>
                    <h3>{compute.resource_id}</h3>
                    <span className={`status-badge ${compute.deleted_at ? 'deleted' : compute.state}`}>
                      {compute.deleted_at ? 'deleted' : compute.state}
                    </span>
                  </div>
                  <div className="resource-meta">
                    <div className="resource-flavor">{compute.flavor}</div>
                    {prices?.compute?.[compute.flavor] && (
                      <div className="resource-cost">${prices.compute[compute.flavor].per_hour}/hr</div>
                    )}
                  </div>
                </div>
                
                <div className="resource-info">
                  <div className="info-item">
                    <span className="label">Created:</span>
                    <span>{new Date(compute.created_at).toLocaleString()}</span>
                  </div>
                  {compute.deleted_at && (
                    <div className="info-item">
                      <span className="label">Deleted:</span>
                      <span>{new Date(compute.deleted_at).toLocaleString()}</span>
                    </div>
                  )}
                  {compute.last_state_change && (
                    <div className="info-item">
                      <span className="label">Last Updated:</span>
                      <span>{new Date(compute.last_state_change).toLocaleString()}</span>
                    </div>
                  )}
                </div>

                {compute.events && compute.events.length > 0 && (
                  <div className="resource-events">
                    <h4>📋 Event History</h4>
                    <div className="events-list">
                      {compute.events.slice().reverse().slice(0, 5).map((event) => (
                        <div key={event.event_id} className="event-item">
                          <span className="event-type">{event.type}</span>
                          <span className="event-meta">
                            {event.meta?.flavor && `→ ${event.meta.flavor}`}
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
                  {!compute.deleted_at && compute.state === 'running' && (
                    <button className="btn-action btn-warning" onClick={() => handleStateChange(compute.resource_id, 'stopped')}>
                      Stop
                    </button>
                  )}
                  {!compute.deleted_at && compute.state === 'stopped' && (
                    <button className="btn-action btn-success" onClick={() => handleStateChange(compute.resource_id, 'running')}>
                      Start
                    </button>
                  )}
                  {!compute.deleted_at && (compute.state === 'running' || compute.state === 'stopped') && (
                    <>
                      <button className="btn-action btn-info" onClick={() => handleResize(compute.resource_id, compute.current_flavor)}>
                        Resize
                      </button>
                      <button className="btn-action btn-danger" onClick={() => handleDelete(compute.resource_id)}>
                        Delete
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className="no-resources">No compute instances yet. Create one to get started!</div>
          )}
        </div>
      )}
    </div>
  )
}

export default ComputePanel
