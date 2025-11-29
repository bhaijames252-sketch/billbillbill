import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

export const walletAPI = {
  getWallet: (userId) => api.get(`/wallets/${userId}`),
  getTransactions: (userId) => api.get(`/wallets/${userId}/transactions`),
  addCredit: (userId, amount, reason) => 
    api.post(`/wallets/${userId}/credit`, { amount, reason }),
  createWallet: (userId, balance = 1000.0) =>
    api.post('/wallets/', {
      user_id: userId,
      balance,
      currency: 'USD',
      auto_recharge: false,
      allow_negative: false,
    }),
}

export const resourceAPI = {
  getComputes: (userId) => api.get(`/resources/computes/user/${userId}`),
  createCompute: (resourceId, userId, flavor) =>
    api.post('/resources/computes', { resource_id: resourceId, user_id: userId, flavor }),
  updateCompute: (resourceId, state, flavor) =>
    api.patch(`/resources/computes/${resourceId}`, { state, flavor }),
  deleteCompute: (resourceId) => api.delete(`/resources/computes/${resourceId}`),

  getDisks: (userId) => api.get(`/resources/disks/user/${userId}`),
  createDisk: (resourceId, userId, sizeGb, attachedTo = null) =>
    api.post('/resources/disks', { 
      resource_id: resourceId, 
      user_id: userId, 
      size_gb: sizeGb, 
      attached_to: attachedTo 
    }),
  updateDisk: (resourceId, state, sizeGb, attachedTo) =>
    api.patch(`/resources/disks/${resourceId}`, { state, size_gb: sizeGb, attached_to: attachedTo }),
  deleteDisk: (resourceId) => api.delete(`/resources/disks/${resourceId}`),

  getFloatingIPs: (userId) => api.get(`/resources/floating-ips/user/${userId}`),
  createFloatingIP: (resourceId, userId, ipAddress, attachedTo = null) =>
    api.post('/resources/floating-ips', { 
      resource_id: resourceId, 
      user_id: userId, 
      ip_address: ipAddress,
      attached_to: attachedTo 
    }),
  deleteFloatingIP: (resourceId) => api.delete(`/resources/floating-ips/${resourceId}`),
}

export const billingAPI = {
  getUserBills: (userId) => api.get(`/billing/user/${userId}`),
  computeBill: (userId, periodEnd = null) =>
    api.post('/billing/compute', { 
      user_id: userId, 
      period_end: periodEnd 
    }),
}

export const priceAPI = {
  getLatestPrices: () => api.get('/prices/'),
  getPriceByCurrency: (currency) => api.get(`/prices/currency/${currency}`),
}

export default api
