CREATE TABLE transaction_log (
    tx_id VARCHAR(30) PRIMARY KEY,
    xid VARCHAR(64),
    phase VARCHAR(20),
    amount DECIMAL(15,2),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE accounts (
    account_number VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100),
    balance DECIMAL(15,2) CHECK (balance >= 0),
    account_type VARCHAR(50) DEFAULT NULL
) ENGINE=InnoDB;

INSERT INTO accounts (account_number, name, balance)
VALUES ('102938475612', 'Nguyễn Văn A', 1234567890);
