CREATE TABLE transactions (
    tx_id VARCHAR(30) PRIMARY KEY,
    from_account VARCHAR(20),
    to_account VARCHAR(20),
    amount DECIMAL(15,2),
    status VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE idempotency_keys (
    idem_key VARCHAR(128) PRIMARY KEY,
    status VARCHAR(20),
    tx_id VARCHAR(30)
) ENGINE=InnoDB;
