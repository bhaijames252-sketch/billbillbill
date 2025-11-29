import { useState, useEffect } from 'react'
import { walletAPI, billingAPI } from '../api/api'
import './Sidebar.css'

function Sidebar({ userId, refreshTrigger }) {
  const [wallet, setWallet] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [bills, setBills] = useState([])
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('wallet')
  const [creditAmount, setCreditAmount] = useState('100')

  useEffect(() => {
    if (userId) {
      fetchData()
    }
  }, [userId, refreshTrigger])

  const fetchData = async () => {
    setLoading(true)
    try {
      try {
        const walletRes = await walletAPI.getWallet(userId)
        setWallet(walletRes.data)
      } catch (error) {
        if (error.response?.status === 404) {
          await walletAPI.createWallet(userId, 1000.0)
          const walletRes = await walletAPI.getWallet(userId)
          setWallet(walletRes.data)
        }
      }

      const [transRes, billsRes] = await Promise.all([
        walletAPI.getTransactions(userId).catch(() => ({ data: { transactions: [] } })),
        billingAPI.getUserBills(userId).catch(() => ({ data: [] }))
      ])
      
      setTransactions(transRes.data.transactions || [])
      setBills(billsRes.data)
    } catch (error) {
      console.error('Error fetching data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAddCredit = async () => {
    try {
      await walletAPI.addCredit(userId, parseFloat(creditAmount), 'Manual top-up')
      alert('Credit added successfully!')
      fetchData()
    } catch (error) {
      alert('Error adding credit: ' + (error.response?.data?.detail || error.message))
    }
  }

  const handleComputeBill = async () => {
    try {
      const result = await billingAPI.computeBill(userId)
      alert(`Bill computed! Total: $${result.data.total_amount}`)
      fetchData()
    } catch (error) {
      alert('Error computing bill: ' + (error.response?.data?.detail || error.message))
    }
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-tabs">
        <button 
          className={activeTab === 'wallet' ? 'active' : ''}
          onClick={() => setActiveTab('wallet')}
        >
          💰 Wallet
        </button>
        <button 
          className={activeTab === 'transactions' ? 'active' : ''}
          onClick={() => setActiveTab('transactions')}
        >
          📊 Transactions
        </button>
        <button 
          className={activeTab === 'bills' ? 'active' : ''}
          onClick={() => setActiveTab('bills')}
        >
          🧾 Bills
        </button>
      </div>

      <div className="sidebar-content">
        {loading ? (
          <div className="loading">Loading...</div>
        ) : (
          <>
            {activeTab === 'wallet' && (
              <div className="wallet-section">
                {wallet ? (
                  <>
                    <div className="balance-card">
                      <h3>Current Balance</h3>
                      <div className="balance-amount">
                        ${wallet.balance ?? '0'}
                      </div>
                      <div className="balance-currency">{wallet.currency}</div>
                    </div>

                    <div className="add-credit">
                      <h4>Add Credit</h4>
                      <div className="credit-input-group">
                        <input
                          type="number"
                          value={creditAmount}
                          onChange={(e) => setCreditAmount(e.target.value)}
                          placeholder="Amount"
                          min="0"
                          step="10"
                        />
                        <button onClick={handleAddCredit} className="btn-primary">
                          Add
                        </button>
                      </div>
                    </div>

                    <div className="compute-bill">
                      <button onClick={handleComputeBill} className="btn-compute">
                        🧮 Compute Bill Now
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="no-data">No wallet found</div>
                )}
              </div>
            )}

            {activeTab === 'transactions' && (
              <div className="transactions-section">
                <h3>Transaction History</h3>
                {transactions.length > 0 ? (
                  <div className="transactions-list">
                    {transactions.slice().reverse().map((tx, idx) => (
                      <div key={tx.tx_id || idx} className={`transaction-item ${tx.type}`}>
                        <div className="tx-header">
                          <span className="tx-type">{tx.type}</span>
                          <span className={`tx-amount ${tx.type}`}>
                            {tx.type === 'credit' ? '+' : '-'}${Math.abs(tx.amount)}
                          </span>
                        </div>
                        <div className="tx-reason">{tx.reason}</div>
                        <div className="tx-date">
                          {tx.time ? new Date(tx.time).toLocaleString() : 'N/A'}
                        </div>
                        <div className="tx-balance">
                          Balance: ${tx.balance_after ?? 'N/A'}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="no-data">No transactions yet</div>
                )}
              </div>
            )}

            {activeTab === 'bills' && (
              <div className="bills-section">
                <h3>Billing History</h3>
                {bills.length > 0 ? (
                  <div className="bills-list">
                    {bills.map((bill) => (
                      <div key={bill.id} className={`bill-item ${bill.status}`}>
                        <div className="bill-header">
                          <span className="bill-status">{bill.status}</span>
                          <span className="bill-amount">${bill.total_amount}</span>
                        </div>
                        <div className="bill-period">
                          Period: {new Date(bill.period_start).toLocaleDateString()} - {new Date(bill.period_end).toLocaleDateString()}
                        </div>
                        {bill.items && (
                          <div className="bill-items">
                            {bill.items.map((item, idx) => (
                              <div key={idx} className="bill-item-detail">
                                {item.resource_type} - ${item.amount}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="no-data">No bills yet</div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  )
}

export default Sidebar
