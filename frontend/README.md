# BillingCloud Test UI

A simple React-based web UI to test and simulate the BillingCloud billing engine.

## Features

- **Compute Instances**: Create, start, stop, resize, and delete compute instances
- **Disk Volumes**: Create, resize, and delete disk volumes
- **Floating IPs**: Allocate and release floating IP addresses
- **Wallet Management**: View balance, add credit, and compute bills
- **Transaction History**: View all wallet transactions
- **Billing History**: View all billing cycles and their details

## Setup

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. Make sure your backend API is running on `http://localhost:8000`

4. Open your browser and navigate to `http://localhost:3000`

## Usage

1. **Select User**: Enter a user ID in the header (default: user-001)
2. **Create Resources**: Use the "+" buttons to create compute instances, disks, or floating IPs
3. **Manage Resources**: Use the action buttons on each resource card to start, stop, resize, or delete
4. **View Billing**: Check the sidebar for wallet balance, transactions, and billing history
5. **Add Credit**: Use the "Add Credit" section in the wallet tab
6. **Compute Bill**: Click "Compute Bill Now" to generate a bill for current resource usage

## Tech Stack

- React 18
- Vite
- Axios
- CSS3

## Notes

This is an MVP for testing purposes. It provides basic functionality to simulate cloud resource operations and billing.
