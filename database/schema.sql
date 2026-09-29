-- ====================================================================
-- SmartBank Database Schema
-- Normalized schema for MySQL 8.0+
-- Engine: InnoDB with strict foreign key constraints & UTF8MB4 charset
-- ====================================================================

CREATE DATABASE IF NOT EXISTS `smartbank_db` 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE `smartbank_db`;

-- Drop tables in reverse dependency order if recreating
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `notifications`;
DROP TABLE IF EXISTS `beneficiaries`;
DROP TABLE IF EXISTS `transactions`;
DROP TABLE IF EXISTS `cards`;
DROP TABLE IF EXISTS `accounts`;
DROP TABLE IF EXISTS `customers`;
DROP TABLE IF EXISTS `users`;
SET FOREIGN_KEY_CHECKS = 1;

-- 1. Users Table (Core authentication & role-based access)
CREATE TABLE `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `email` VARCHAR(100) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `role` ENUM('customer', 'admin') NOT NULL DEFAULT 'customer',
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_users_username` (`username`),
    INDEX `idx_users_email` (`email`),
    INDEX `idx_users_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Customers Table (Customer Profile Information)
CREATE TABLE `customers` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL UNIQUE,
    `customer_code` VARCHAR(20) NOT NULL UNIQUE,
    `first_name` VARCHAR(50) NOT NULL,
    `last_name` VARCHAR(50) NOT NULL,
    `phone` VARCHAR(20) NOT NULL,
    `address` TEXT NULL,
    `city` VARCHAR(50) NULL,
    `state` VARCHAR(50) NULL,
    `pincode` VARCHAR(10) NULL,
    `date_of_birth` DATE NULL,
    `kyc_status` ENUM('PENDING', 'VERIFIED', 'REJECTED') NOT NULL DEFAULT 'VERIFIED',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_customers_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    INDEX `idx_customers_code` (`customer_code`),
    INDEX `idx_customers_phone` (`phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Accounts Table (Savings, Current, Salary Accounts)
CREATE TABLE `accounts` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `customer_id` INT NOT NULL,
    `account_number` VARCHAR(20) NOT NULL UNIQUE,
    `account_type` ENUM('Savings', 'Current', 'Salary') NOT NULL DEFAULT 'Savings',
    `balance` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    `status` ENUM('ACTIVE', 'INACTIVE', 'SUSPENDED') NOT NULL DEFAULT 'ACTIVE',
    `currency` VARCHAR(5) NOT NULL DEFAULT 'INR',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_accounts_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE RESTRICT,
    INDEX `idx_accounts_customer` (`customer_id`),
    INDEX `idx_accounts_num` (`account_number`),
    INDEX `idx_accounts_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Debit Cards Table (Card issuance, PIN, limits, and channel security)
CREATE TABLE `cards` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `account_id` INT NOT NULL,
    `card_number` VARCHAR(19) NOT NULL UNIQUE,
    `card_holder_name` VARCHAR(100) NOT NULL,
    `card_network` VARCHAR(20) NOT NULL DEFAULT 'VISA',
    `card_type` VARCHAR(20) NOT NULL DEFAULT 'Platinum',
    `expiry_month` INT NOT NULL,
    `expiry_year` INT NOT NULL,
    `cvv` VARCHAR(4) NOT NULL,
    `pin_hash` VARCHAR(255) NOT NULL,
    `daily_limit` DECIMAL(15, 2) NOT NULL DEFAULT 50000.00,
    `status` VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    `is_online_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `is_contactless_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `is_international_enabled` BOOLEAN NOT NULL DEFAULT FALSE,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_cards_account` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`) ON DELETE CASCADE,
    INDEX `idx_cards_account` (`account_id`),
    INDEX `idx_cards_number` (`card_number`),
    INDEX `idx_cards_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Transactions Table (Auditable ledger records with card transaction tracking)
CREATE TABLE `transactions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `transaction_ref` VARCHAR(35) NOT NULL UNIQUE,
    `account_id` INT NOT NULL,
    `card_id` INT NULL,
    `transaction_type` VARCHAR(30) NOT NULL,
    `amount` DECIMAL(15, 2) NOT NULL,
    `balance_after` DECIMAL(15, 2) NOT NULL,
    `recipient_account` VARCHAR(35) NULL,
    `description` VARCHAR(255) NULL,
    `status` ENUM('COMPLETED', 'FAILED', 'PENDING') NOT NULL DEFAULT 'COMPLETED',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_transactions_account` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`) ON DELETE RESTRICT,
    CONSTRAINT `fk_transactions_card` FOREIGN KEY (`card_id`) REFERENCES `cards` (`id`) ON DELETE SET NULL,
    INDEX `idx_transactions_account` (`account_id`),
    INDEX `idx_transactions_card` (`card_id`),
    INDEX `idx_transactions_ref` (`transaction_ref`),
    INDEX `idx_transactions_type` (`transaction_type`),
    INDEX `idx_transactions_date` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Beneficiaries Table (Saved payees for fund transfers)
CREATE TABLE `beneficiaries` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `customer_id` INT NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    `account_number` VARCHAR(30) NOT NULL,
    `bank_name` VARCHAR(100) NOT NULL,
    `ifsc_code` VARCHAR(20) NOT NULL,
    `email` VARCHAR(100) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_beneficiaries_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE,
    INDEX `idx_beneficiaries_cust` (`customer_id`),
    INDEX `idx_beneficiaries_acc` (`account_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Notifications Table (System & transaction alerts)
CREATE TABLE `notifications` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL,
    `title` VARCHAR(150) NOT NULL,
    `message` TEXT NOT NULL,
    `type` ENUM('INFO', 'SUCCESS', 'WARNING', 'DANGER') NOT NULL DEFAULT 'INFO',
    `is_read` BOOLEAN NOT NULL DEFAULT FALSE,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_notifications_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    INDEX `idx_notifications_user` (`user_id`),
    INDEX `idx_notifications_read` (`is_read`),
    INDEX `idx_notifications_date` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
