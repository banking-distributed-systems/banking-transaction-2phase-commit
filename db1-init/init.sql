CREATE TABLE accounts (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    balance DECIMAL(15, 2) CHECK (balance >= 0),
    phone VARCHAR(20),
    password VARCHAR(255),
    account_number VARCHAR(20),
    account_type VARCHAR(50) DEFAULT 'STANDARD'
) ENGINE=InnoDB;
SET @@auto_increment_increment = 3;

CREATE TABLE transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tx_id VARCHAR(30) NOT NULL UNIQUE,
    from_account_number VARCHAR(20) NOT NULL,
    from_name VARCHAR(100) NOT NULL,
    to_account_number VARCHAR(20) NOT NULL,
    to_name VARCHAR(100) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    description VARCHAR(255) DEFAULT '',
    status VARCHAR(20) DEFAULT 'SUCCESS',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Bảng ghi log trạng thái từng phase của 2PC
CREATE TABLE transaction_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tx_id    VARCHAR(30)  NOT NULL UNIQUE,
    xid      VARCHAR(64)  NOT NULL,
    from_account_number VARCHAR(20)  NOT NULL,
    from_name           VARCHAR(100) NOT NULL,
    to_account_number   VARCHAR(20)  NOT NULL,
    to_name             VARCHAR(100) NOT NULL,
    amount      DECIMAL(15,2)  NOT NULL,
    description VARCHAR(255)   DEFAULT '',
    phase       VARCHAR(20)    NOT NULL DEFAULT 'PREPARING',
    -- PREPARING → PREPARED → COMMITTED | ABORTED
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

INSERT INTO accounts (id, name, balance, phone, password, account_number, account_type)
VALUES (1, 'Nguyễn Văn A', 1234567890, '0901234567', 'e10adc3949ba59abbe56e057f20f883e', '1029 3847 5612', 'VCB PLATINUM');
