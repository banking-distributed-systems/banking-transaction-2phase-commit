CREATE TABLE accounts (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    balance DECIMAL(15, 2) CHECK (balance >= 0),
    phone VARCHAR(20),
    password VARCHAR(255),
    account_number VARCHAR(20),
    account_type VARCHAR(50) DEFAULT 'STANDARD'
) ENGINE=InnoDB;

INSERT INTO accounts (id, name, balance, phone, password, account_number, account_type)
VALUES (2, 'Trần Thị B', 2000000, '0912345678', 'e10adc3949ba59abbe56e057f20f883e', '2038 4756 9801', 'GOLD');
