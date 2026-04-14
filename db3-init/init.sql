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

INSERT INTO accounts (id, name, balance, phone, password, account_number, account_type)
VALUES (3, 'Lê Văn C', 8000000, '0923456789', 'e10adc3949ba59abbe56e057f20f883e', '3047 5612 8934', 'SILVER');
