CREATE TABLE transaction_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tx_id VARCHAR(30) NOT NULL UNIQUE,
    xid VARCHAR(64) NOT NULL,
    from_account_number VARCHAR(20) NOT NULL,
    from_name VARCHAR(100) NOT NULL,
    to_account_number VARCHAR(20) NOT NULL,
    to_name VARCHAR(100) NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    description VARCHAR(255) NOT NULL DEFAULT '',
    phase VARCHAR(20) NOT NULL DEFAULT 'PREPARING',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE accounts (
    account_number VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100),
    balance DECIMAL(15,2),
    account_type VARCHAR(50) DEFAULT NULL
) ENGINE=InnoDB;

INSERT INTO accounts (account_number, name, balance)
VALUES ('304756128934', 'Lê Văn C', 8000000);
