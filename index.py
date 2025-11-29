### what i am doing is creating a cloud billing engine 
### can you implement it full, fix test recursively and all?


### Implement api for user balance computing, it allows negative allways, auto recharge false default. it will have amount and essentials in mysql and old archival in mongodb
### and for computing, it will allways use latest pricing data version from mysql price_table which we created earlier
#### it should get current user balance, get archival data.
{
    "user_id": "10101010",
    "balance": 12.52,
    "currency": "USD",
    "wallet": {
        "auto_recharge": false,
        "allow_negative": true,
        "last_deducted_at": "2023-09-01T12:05:00Z",
    },
    "_id_l_transactions_nosql_archival": "101010", ### link to mongodb archival collection
}


#### have it below in mongodb: archival
{
    "_id": "10101010",
    "_id_l_transactions_sql_parent": [
        {
            "tx_id": "tx_001",
            "time": "2023-09-01T00:00:00Z",
            "amount": 10,
            "balance_after": 10,
            "type": "credit",
            "reason": "Initial Bonus",
        },
        {
            "tx_id": "tx_002",
            "time": "2023-09-01T12:05:00Z",
            "amount": -2.5,
            "balance_after": 7.5,
            "type": "debit",
            "reason": "Compute Usage",
            "billing_cycle.price_version": "2023-09-01_v1",
        },
    ],
}

### also when every computation of bills, implement like below billing document in mongodb to save
### so in case of failure while charging user, we have the data stored and start billing the user from last  period_end/billed_until time
{
    "bill_id": "bill_2023_10_01_10101010",
    "user_id": "10101010",
    "period_start": "2023-09-01T00:00:00Z",
    "period_end": "2023-09-30T23:59:59Z",
    "status": "success",
    "charges": [
        {"type": "compute", "amount": 8.2},
        {"type": "disk", "amount": 2.5},
        {"type": "floating_ip", "amount": 0.7},
    ],
    "total": 11.4,
    "paid": true,
    "billing_cycle.price_version": "2023-09-01_v1",
    "generated_at": "2023-10-01T00:00:00Z",
}


#### we will store data in the below format in mongodb for resource usage archival


{
    "resource_id": "compute_001",
    "user_id": "10101010",
    "state": "running",
    "current_flavor": "medium",
    "created_at": "2023-09-01T00:00:00Z",
    "deleted_at": null,
    "last_billed_until": "2023-09-01T12:00:00Z",
    "events": [
        {
            "event_id": "evt_001",
            "time": "2023-09-01T00:00:00Z",
            "type": "create",
            "meta": {"flavor": "small"},
        }
    ],
}


{
    "resource_id": "disk_001",
    "user_id": "10101010",
    "size_gb": 200,
    "state": "attached",
    "attached_to": "compute_001",
    "created_at": "2023-09-01T01:00:00Z",
    "deleted_at": null,
    "last_billed_until": "2023-09-01T12:00:00Z",
    "events": [
        {
            "event_id": "evt_d001",
            "type": "create",
            "time": "2023-09-01T01:00:00Z",
            "meta": {"size_gb": 100},
        }
    ],
}


{
    "resource_id": "ip_001",
    "user_id": "10101010",
    "ip_address": "124.41.23.13",
    "port_id": "123130a03",
    "created_at": "2023-09-01T00:30:00Z",
    "released_at": null,
    "attached_to": "compute_001",
    "last_billed_until": "2023-09-01T12:00:00Z",
    "events": [
        {"event_id": "evt_ip_001", "type": "allocate", "time": "2023-09-01T00:30:00Z"}
    ],
}









### Implement an API where  can get, set the price and on adding or editing price, append as a new version in price_history 

## below in mongodb:
{
    "latest": "2023-09-01_v1",
    "price_history": [
        {
            "price_version": "2023-09-01_v1",
            "pricing": [
                {
                    "currency": "USD",
                    "compute": {
                        "small": {"per_hour": 0.5},
                        "medium": {"per_hour": 1},
                        "large": {"per_hour": 2},
                        "others": {"per_hour": 0.1},
                    },
                    "disk": {"per_gb_hour": 0.002},
                    "floating_ip": {"per_hour": 0.01},
                },
                {
                    "currency": "INR",
                    "compute": {
                        "small": {"per_hour": 0.6},
                        "medium": {"per_hour": 1.2},
                        "large": {"per_hour": 2.4},
                        "others": {"per_hour": 0.12},
                    },
                    "disk": {"per_gb_hour": 0.0025},
                    "floating_ip": {"per_hour": 0.012},
                },
            ],
        },
    ],
},

### below in mysql latest_prices table:
{
    "compute": {
        "small": {"per_hour": 0.5},
        "medium": {"per_hour": 1},
        "large": {"per_hour": 2},
        "others": {"per_hour": 0.1}
    },
    "disk": {"per_gb_hour": 0.002},
    "floating_ip": {"per_hour": 0.01},
    "currency": "USD",
}
{
      "compute": {
        "small": {"per_hour": 0.5},
        "medium": {"per_hour": 1},
        "large": {"per_hour": 2},
        "others": {"per_hour": 0.12}
    },
    "disk": {"per_gb_hour": 0.002},
    "floating_ip": {"per_hour": 0.01},
    "currency": "INR",
}

{
    "compute": {
        "small": {"per_hour": 0.5},
        "medium": {"per_hour": 1},
        "large": {"per_hour": 2},
    },
    "disk": {"per_gb_hour": 0.002},
    "floating_ip": {"per_hour": 0.01},
    "currency": "USD",
}