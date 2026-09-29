# 🏦 SmartBank — Enterprise Full-Stack Bank Management System

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.3-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](https://www.mysql.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Bootstrap 5](https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![Tests](https://img.shields.io/badge/Tests-13%2F13%20Passing-success?style=for-the-badge&logo=pytest&logoColor=white)]()

A production-grade, full-stack **Core Banking & Bank Management Web Application** engineered with Python Flask, MySQL, Flask-SQLAlchemy, and Bootstrap 5. 

Built to deliver real-world financial transaction reliability, **SmartBank** enforces strict **ACID database transaction guarantees**, atomic debit/credit fund transfers with automatic rollback mechanisms, role-based access control (RBAC), multi-account portfolio management, automated 12-digit account provisioning, beneficiary address books, in-app notification alerts, and a complete suite of RESTful API endpoints.

Designed for a **BTech CSE Capstone Portfolio, GitHub Showcase, LinkedIn Project, and Technical Interview Demonstrations**.

---

## 📑 Table of Contents
1. [Core Features](#-core-features)
2. [Architecture & Workflow](#-architecture--workflow)
3. [Technology Stack](#-technology-stack)
4. [Database Architecture & ER Diagram](#-database-architecture--er-diagram)
5. [Project Directory Structure](#-project-directory-structure)
6. [Prerequisites](#-prerequisites)
7. [Installation & Setup](#-installation--setup)
8. [Database Initialization & Seeding](#-database-initialization--seeding)
9. [Running the Application](#-running-the-application)
10. [Demo Credentials](#-demo-credentials)
11. [RESTful API Documentation](#-restful-api-documentation)
12. [Running Automated Tests](#-running-automated-tests)
13. [Key Engineering Highlights & Security](#-key-engineering-highlights--security)
14. [Future Roadmap](#-future-roadmap)

---

## 🌟 Core Features

### 1. Robust Authentication & Role-Based Access Control (RBAC)
* **Secure Hashing**: Passwords hashed with PBKDF2:SHA256 via Werkzeug; no plain-text passwords stored.
* **Role Segregation**: Independent permissions and route guards for `Customer` and `Admin` users.
* **Session Lifecycle**: Protected sessions with `HttpOnly` cookies, `SameSite=Lax`, and inactivity timeouts.
* **Account Status Lifecycle**: Instant administrative activation and soft-deactivation preventing compromised logins.

### 2. Multi-Account Portfolio Management
* Support for **Savings**, **Current**, and **Salary** account types.
* Automatic unique 12-digit account number generation (`1001XXXXXXXX`).
* Real-time balance updates across individual and combined portfolios.
* Customers can open and manage multiple accounts under a single profile.

### 3. ACID Financial Transactions
* **Cash / Online Deposits**: Validates positive amounts up to ₹10,00,000 per transaction, updates ledger and balance atomically.
* **Cash Withdrawals**: Real-time balance verification prevents overdrafts; automatically triggers low-balance alert if balance breaches ₹1,000 threshold.
* **Inter-Account Fund Transfers**:
  - Sender and recipient account validation (checks existence and active status).
  - Atomic two-phase transfer: debits sender, credits recipient, and writes dual ledger records (`TRANSFER_SENT` & `TRANSFER_RECEIVED`).
  - Automatic rollback on any failure to preserve ledger integrity.
  - Self-transfer prevention.

### 4. Transaction Audit Ledger & History
* Comprehensive search by transaction reference (`TXN...`), remark, or counterparty.
* Filter by transaction type: `DEPOSIT`, `WITHDRAWAL`, `TRANSFER_SENT`, `TRANSFER_RECEIVED`.
* Filter by date range (From Date & To Date) and specific account.
* Sorting (Newest, Oldest, Highest Amount, Lowest Amount) and server-side pagination.

### 5. Beneficiary / Payee Directory
* Add, edit, and remove beneficiaries with bank name, IFSC code, and account number.
* One-click transfer initiation directly from the payee list.
* Quick-select dropdown on the transfer page that auto-populates the recipient account.

### 6. In-App Notification System
* Real-time notification banners for deposits, withdrawals, peer transfers, failed transactions, and status updates.
* Unread counter badge in top navigation.
* Dedicated notification center with "Mark All as Read" functionality.

### 7. Administrative Control Center
* Live dashboard showing total customers, total accounts, active/inactive counts, liquidity inflow/outflow, and transaction volumes.
* Customer onboarding and full CRUD (view details, edit contact info, update KYC compliance).
* Soft-delete / deactivation toggle for customers and accounts.
* Bank-wide transaction auditing.

### 8. Debit Card Services & Usage Simulator 💳
* **Instant Digital Card Issuance**: Provision Visa, Mastercard, or RuPay debit cards linked to any active account.
* **Realistic 3D Metallic Card UI**: Complete with metallic foil gradients, EMV chip, contactless waves, cardholder name, expiry, masked 16 digits, and CVV reveal toggles.
* **Channel Security Switches**: Independent toggles for **Online E-Commerce Transactions**, **Contactless Tap & Pay**, and **International Usage**.
* **Card Lifecycle Management**:
  - **Freeze / Lock Toggle**: Instantly freeze cards to decline transactions when misplaced; unfreeze anytime.
  - **Permanent Hotlisting**: Permanent block protection against compromised cards.
* **ATM PIN Management**: Hashed 4-digit PIN setup and update with cryptographic security.
* **Daily Spending Limits**: Configurable daily limit (₹500 to ₹2,00,000) with live spending meters and cap enforcement.
* **Interactive Transaction Sandbox**:
  - **Online / POS E-Commerce Checkout**: Enter card details, expiry, CVV, and merchant to execute real-time purchases.
  - **ATM Cash Withdrawal**: Verify 4-digit PIN and dispense cash with real-time balance deductions.
  - **Atomic Updates & Alerts**: Automatically debits linked accounts, logs transactions (`CARD_PAYMENT`, `ATM_WITHDRAWAL`), and dispatches notifications.

---

## 🏗 Architecture & Workflow

```mermaid
flowchart TD
    subgraph Client["Presentation Layer (Client)"]
        Browser["Modern Web Browser / REST API Consumer"]
        UI["Bootstrap 5.3 + Custom CSS + Vanilla JS"]
    end

    subgraph Server["Application Layer (Flask Backend)"]
        App["Flask Application Factory (app.py)"]
        AuthBP["Auth Blueprint (/auth)"]
        CustBP["Customer Blueprint (/customer)"]
        AdminBP["Admin Blueprint (/admin)"]
        TxnBP["Transaction Blueprint (/deposit, /withdraw, /transfer, /history)"]
        CardBP["Card Blueprint (/cards)"]
        ApiBP["REST API Blueprint (/api)"]
        Decorators["RBAC Guards (@login_required, @admin_required)"]
    end

    subgraph DataLayer["Data & Persistence Layer"]
        ORM["Flask-SQLAlchemy ORM"]
        MySQL[("MySQL 8.0 Database (InnoDB Engine)")]
    end

    Browser --> UI
    UI -->|HTTP / REST JSON| App
    App --> AuthBP
    App --> CustBP
    App --> AdminBP
    App --> TxnBP
    App --> CardBP
    App --> ApiBP
    
    AuthBP & CustBP & AdminBP & TxnBP & CardBP & ApiBP --> Decorators
    Decorators --> ORM
    ORM -->|Parameterized Queries & Transactions| MySQL
```

---

## 💻 Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend** | Python 3.11+ / Flask 3.1.3 | Web server, application factory, routing |
| **ORM** | Flask-SQLAlchemy 3.1.1 | Object-Relational Mapping & connection pooling |
| **Database** | MySQL 8.0+ (PyMySQL driver) | ACID-compliant relational data store with foreign key enforcement |
| **Security** | Werkzeug 3.1.8 | Cryptographic PBKDF2 password hashing & verification |
| **Frontend** | HTML5, CSS3, JavaScript (ES6) | Responsive client interface |
| **UI Framework**| Bootstrap 5.3.3 & Bootstrap Icons | Modern banking grid, responsive components, typography |
| **Configuration**| python-dotenv | Environment variable isolation & secret security |
| **Testing** | unittest (Python built-in) | Unit and integration test coverage |

---

## 🗄 Database Architecture & ER Diagram

The database is normalized to 3NF, utilizing foreign key constraints, unique indexes, and audit timestamps.

```mermaid
erDiagram
    USERS ||--o| CUSTOMERS : "has profile"
    USERS ||--o{ NOTIFICATIONS : "receives"
    CUSTOMERS ||--o{ ACCOUNTS : "owns"
    CUSTOMERS ||--o{ BENEFICIARIES : "saves"
    ACCOUNTS ||--o{ TRANSACTIONS : "records"
    ACCOUNTS ||--o{ CARDS : "issues"
    CARDS ||--o{ TRANSACTIONS : "authorizes"

    USERS {
        int id PK
        string username UK
        string email UK
        string password_hash
        string role "customer | admin"
        boolean is_active
        datetime created_at
    }

    CUSTOMERS {
        int id PK
        int user_id FK
        string customer_code UK "CUST-XXXXXX"
        string first_name
        string last_name
        string phone
        string address
        string city
        string state
        string pincode
        string kyc_status "VERIFIED | PENDING | REJECTED"
    }

    ACCOUNTS {
        int id PK
        int customer_id FK
        string account_number UK "12 Digits"
        string account_type "Savings | Current | Salary"
        decimal balance "15,2"
        string status "ACTIVE | INACTIVE | SUSPENDED"
        string currency "INR"
    }

    CARDS {
        int id PK
        int account_id FK
        string card_number UK "16 Digits"
        string card_holder_name
        string card_network "VISA | MASTERCARD | RUPAY"
        string card_type "Platinum | Classic | Business"
        int expiry_month
        int expiry_year
        string cvv "3 Digits"
        string pin_hash "Hashed"
        decimal daily_limit "15,2"
        string status "ACTIVE | LOCKED | BLOCKED | EXPIRED"
        boolean is_online_enabled
        boolean is_contactless_enabled
        boolean is_international_enabled
        datetime created_at
    }

    TRANSACTIONS {
        int id PK
        string transaction_ref UK "TXN... / POS... / ATM..."
        int account_id FK
        int card_id FK "nullable"
        string transaction_type "DEPOSIT | WITHDRAWAL | TRANSFER_SENT | TRANSFER_RECEIVED | CARD_PAYMENT | ATM_WITHDRAWAL"
        decimal amount "15,2"
        decimal balance_after "15,2"
        string recipient_account
        string description
        string status "COMPLETED | FAILED | PENDING"
        datetime created_at
    }

    BENEFICIARIES {
        int id PK
        int customer_id FK
        string name
        string account_number
        string bank_name
        string ifsc_code
        string email
    }

    NOTIFICATIONS {
        int id PK
        int user_id FK
        string title
        text message
        string type "INFO | SUCCESS | WARNING | DANGER"
        boolean is_read
        datetime created_at
    }
```

---

## 📁 Project Directory Structure

```text
banking/
├── app.py                      # Application factory, CLI commands, context processors
├── config.py                   # Environment configuration (Dev, Test, Prod)
├── requirements.txt            # Python dependencies
├── .env.example                # Template for environment variables
├── .env                        # Local environment credentials (git-ignored in production)
├── README.md                   # Complete documentation
│
├── models/                     # SQLAlchemy Models
│   ├── __init__.py             # Exports db and all models
│   ├── user.py                 # User authentication & RBAC model
│   ├── customer.py             # Customer profile & demographic model
│   ├── account.py              # Bank account entity & 12-digit generator
│   ├── card.py                 # Debit card entity, 16-digit generator, PIN hashing
│   ├── transaction.py          # Ledger audit records & reference generator
│   ├── beneficiary.py          # Payees directory model
│   └── notification.py         # System alerts and notifications model
│
├── routes/                     # Blueprint Route Controllers
│   ├── __init__.py             # Blueprint exporter
│   ├── helpers.py              # Login guards, RBAC decorators, notification helper
│   ├── auth.py                 # Registration, login, and logout routes
│   ├── customer.py             # Customer dashboard, profile, accounts, payees
│   ├── admin.py                # Admin console, customer CRUD, account management
│   ├── card.py                 # Debit card controls, PIN, limits, POS & ATM simulator
│   ├── transaction.py          # Deposit, withdrawal, transfer, history routes
│   └── api.py                  # Full RESTful JSON endpoints (including card APIs)
│
├── templates/                  # Jinja2 HTML Templates
│   ├── base.html               # Shared layout, navbar, footer, alert banners
│   ├── auth/
│   │   ├── login.html          # Login portal with demo quick-selector
│   │   └── register.html       # Customer self-registration & account opening
│   ├── customer/
│   │   ├── dashboard.html      # Customer dashboard with fast metrics & actions
│   │   ├── profile.html        # Profile update and password change
│   │   ├── accounts.html       # Bank accounts portfolio & new account modal
│   │   ├── cards.html          # 3D visual cards, limit controls, and simulators
│   │   ├── deposit.html        # Funds deposit screen
│   │   ├── withdraw.html       # Funds withdrawal screen
│   │   ├── transfer.html       # Atomic money transfer screen
│   │   ├── transactions.html   # Transaction history with multi-filter bar
│   │   ├── beneficiaries.html  # Saved payees management
│   │   └── notifications.html  # In-app notifications center
│   ├── admin/
│   │   ├── dashboard.html      # Administrative overview & statistics
│   │   ├── customers.html      # Customer listing, search, create modal, status toggle
│   │   ├── customer_edit.html  # Customer edit and KYC compliance form
│   │   ├── accounts.html       # Bank accounts registry & status toggle
│   │   └── transactions.html   # Global audit ledger
│   └── errors/
│       ├── 400.html            # Bad Request error page
│       ├── 403.html            # Forbidden Access error page
│       ├── 404.html            # Page Not Found error page
│       └── 500.html            # Internal Server Error & rollback note
│
├── static/                     # Static Web Assets
│   ├── css/
│   │   └── custom.css          # Fintech design styling, 3D metallic cards, tables
│   └── js/
│       └── main.js             # Client interactivity, copy clipboard, previews
│
├── database/                   # Database Scripts
│   ├── schema.sql              # Normalized DDL script for MySQL (with cards table)
│   └── seed.py                 # Demo seeder for users, accounts, cards, transactions
│
└── tests/                      # Automated Test Suite
    ├── __init__.py
    └── test_smartbank.py       # 13 integration & unit tests (including debit card tests)
```

---

## ⚙️ Prerequisites

1. **Python**: Version 3.10, 3.11, 3.12, or 3.14.
2. **MySQL Server**: Version 8.0 or MariaDB 10.5+.
3. **Git**: For version control.

---

## 🚀 Installation & Setup

### Step 1: Clone or Navigate to the Repository
```bash
git clone https://github.com/your-username/smartbank.git
cd smartbank
```

### Step 2: Create and Activate a Virtual Environment
**On Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**On Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Required Dependencies
```bash
pip install -r requirements.txt
```

---

## 🗄 Database Initialization & Seeding

### Step 1: Configure Environment Variables
Copy `.env.example` to `.env` and set your MySQL credentials:
```bash
cp .env.example .env
```

Edit `.env` (adjust MySQL password and port, e.g., `3306` or `3307`):
```ini
SECRET_KEY=smartbank-super-secret-key-2026-btech-cse
FLASK_ENV=development
FLASK_DEBUG=1
FLASK_PORT=5000

DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=smartbank_db

DATABASE_URL=mysql+pymysql://root:your_mysql_password@localhost:3306/smartbank_db
```

### Step 2: Initialize Database Tables
You can initialize tables in one of two ways:

**Option A (Using the MySQL CLI / Workbench with the SQL Schema):**
```bash
mysql -u root -p < database/schema.sql
```

**Option B (Using the Flask CLI):**
```bash
flask init-db
```

### Step 3: Seed Realistic Demo Data
Run the included seeder to populate administrator accounts, demo customers, accounts with starting balances, realistic transaction histories, and beneficiaries:
```bash
python database/seed.py
```

Output:
```text
Ensuring database tables exist...
Seeding administrative and demo accounts...
Database seed completed successfully!
```

---

## 💻 Running the Application

Start the local Flask development server:
```bash
python app.py
```

The server will initialize on:
```text
http://localhost:5000
```
Open your browser and navigate to `http://localhost:5000` to access the SmartBank portal.

---

## 🔑 Demo Credentials

For quick testing and technical demonstration, the following pre-configured accounts are available:

| Role | Username / Identifier | Password | Associated Accounts | Starting Balance |
| :--- | :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `Admin@1234` | System Console | N/A |
| **Customer** | `rahul_sharma` | `Password@123` | `100182749102` (Savings)<br>`100192847193` (Salary) | ₹45,500.00<br>₹1,20,000.00 |
| **Customer** | `priya_patel` | `Password@123` | `100173829104` (Savings) | ₹28,450.00 |
| **Customer** | `amit_verma` | `Password@123` | `100164829105` (Current) | ₹85,000.00 |

### 💳 Pre-Seeded Demo Debit Cards

| Network / Tier | Cardholder | 16-Digit Card Number | Expiry | CVV | 4-Digit PIN | Linked Account | Daily Limit |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Visa Platinum** | `RAHUL SHARMA` | `4532 8910 2345 6789` | 12/29 | 842 | `1234` | `100182749102` | ₹50,000.00 |
| **Mastercard Titanium** | `RAHUL SHARMA` | `5421 9876 5432 1098` | 08/30 | 319 | `4321` | `100192847193` | ₹1,00,000.00 |
| **RuPay Platinum** | `PRIYA PATEL` | `6071 8291 0293 8475` | 05/28 | 675 | `1234` | `100173829104` | ₹25,000.00 |
| **Visa Business** | `AMIT VERMA` | `4716 9012 3456 7890` | 11/29 | 528 | `9999` | `100164829105` | ₹75,000.00 |

> **Pro Tip**: The login page includes one-click autofill buttons for both **Customer** and **Admin** profiles. On the `/cards/` page, clicking any pre-set merchant or selecting a card automatically populates card credentials in the transaction simulator!

---

## 📡 RESTful API Documentation

All API endpoints return JSON payloads standardized with `success`, `message`, and `data` keys.

### Authentication Endpoints

#### 1. API Login
* **Endpoint**: `POST /api/login`
* **Request Body**:
```json
{
  "identifier": "rahul_sharma",
  "password": "Password@123"
}
```
* **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Login successful.",
  "data": {
    "id": 2,
    "username": "rahul_sharma",
    "email": "rahul.sharma@example.com",
    "role": "customer"
  }
}
```

#### 2. API Customer Self-Registration
* **Endpoint**: `POST /api/register`
* **Request Body**:
```json
{
  "username": "kavita_m",
  "email": "kavita@example.com",
  "password": "Password@123",
  "first_name": "Kavita",
  "last_name": "Mehta",
  "phone": "+919876501234",
  "account_type": "Savings",
  "initial_deposit": 5000.00
}
```
* **Response (201 Created)**: Returns created user, customer ID, and auto-generated 12-digit account number.

---

### Core Banking & Transaction API Endpoints

#### 3. Deposit Money
* **Endpoint**: `POST /api/deposit`
* **Request Body**:
```json
{
  "account_number": "100182749102",
  "amount": 2000.00,
  "description": "Consulting Fee Credit"
}
```
* **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Deposit completed successfully.",
  "data": {
    "account": {
      "account_number": "100182749102",
      "balance": 47500.0
    },
    "transaction": {
      "transaction_ref": "DEP202609281630129841",
      "amount": 2000.0,
      "balance_after": 47500.0
    }
  }
}
```

#### 4. Withdraw Money
* **Endpoint**: `POST /api/withdraw`
* **Request Body**:
```json
{
  "account_number": "100182749102",
  "amount": 1500.00,
  "description": "Cash ATM Withdrawal"
}
```

#### 5. Inter-Account Fund Transfer
* **Endpoint**: `POST /api/transfer`
* **Request Body**:
```json
{
  "sender_account": "100182749102",
  "recipient_account": "100173829104",
  "amount": 3500.00,
  "description": "Monthly rent settlement"
}
```
* **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Transfer completed successfully.",
  "data": {
    "reference_id": "TRF202609281635418192",
    "amount": 3500.0,
    "sender_balance": 44000.0
  }
}
```

#### 6. Retrieve Transaction Audit Log
* **Endpoint**: `GET /api/transactions?type=TRANSFER_SENT`
* **Response (200 OK)**: Returns list of transactions filtered by type with counterparty details.

#### 7. Beneficiary Management
* **List**: `GET /api/beneficiaries`
* **Add**: `POST /api/beneficiaries`
* **Update**: `PUT /api/beneficiaries/<id>`
* **Delete**: `DELETE /api/beneficiaries/<id>`

---

### Debit Card RESTful API Endpoints 💳

#### 8. Retrieve Customer Cards
* **Endpoint**: `GET /api/cards`
* **Response (200 OK)**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "account_number": "100182749102",
      "card_number": "4532 8910 2345 6789",
      "cardholder_name": "RAHUL SHARMA",
      "card_network": "VISA",
      "card_type": "DEBIT",
      "expiry": "12/29",
      "daily_limit": 50000.0,
      "spent_today": 0.0,
      "status": "ACTIVE",
      "is_online_enabled": true,
      "is_contactless_enabled": true,
      "is_international_enabled": false
    }
  ]
}
```

#### 9. Card Details & Limit Status
* **Endpoint**: `GET /api/cards/<id>`
* **Response (200 OK)**: Returns full metadata, daily limit remaining today, and operational switches.

#### 10. Instant Card Issuance
* **Endpoint**: `POST /api/cards/apply`
* **Request Body**:
```json
{
  "account_id": 1,
  "card_network": "VISA",
  "daily_limit": 50000.0,
  "pin": "1234"
}
```

#### 11. Freeze / Unfreeze Card Toggle
* **Endpoint**: `POST /api/cards/<id>/toggle-lock`
* **Response (200 OK)**: Toggles card between `ACTIVE` and `LOCKED` status.

#### 12. Online / POS Card Payment Authorization
* **Endpoint**: `POST /api/cards/pay`
* **Request Body**:
```json
{
  "card_number": "4532891023456789",
  "expiry_month": 12,
  "expiry_year": 2029,
  "cvv": "842",
  "amount": 2499.00,
  "merchant": "Amazon India",
  "category": "SHOPPING"
}
```
* **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Payment of ₹2,499.00 at Amazon India was authorized successfully.",
  "data": {
    "transaction_ref": "POS202609291122339871",
    "amount": 2499.0,
    "remaining_balance": 43001.0,
    "spent_today": 2499.0
  }
}
```

---

## 🧪 Running Automated Tests

The application includes an automated test suite covering registration, authentication, authorization, deposit limits, overdraft protection, atomic fund transfers, self-transfer prevention, customer deactivation, RESTful API endpoints, debit card issuance, payment simulation, and ATM cash withdrawal.

To run tests:
```bash
python -m unittest tests/test_smartbank.py -v
```

Expected Output:
```text
test_admin_customer_deactivation ... ok
test_api_deposit_and_transfer ... ok
test_atm_card_withdrawal_simulation ... ok
test_beneficiary_lifecycle ... ok
test_customer_registration ... ok
test_debit_card_issuance_and_management ... ok
test_debit_card_payment_simulation ... ok
test_deposit_operations ... ok
test_fund_transfer_atomic_execution ... ok
test_fund_transfer_self_transfer_prevention ... ok
test_login_and_logout ... ok
test_role_authorization_protection ... ok
test_withdrawal_operations ... ok

----------------------------------------------------------------------
Ran 13 tests in 9.381s

OK
```

---

## 🛡️ Key Engineering Highlights & Security

1. **ACID Transaction Guarantees**:
   - In all monetary operations (deposit, withdrawal, and fund transfers), operations are encapsulated inside `db.session` transaction blocks.
   - If any step fails (e.g. invalid recipient account, network glitch, database exception), `db.session.rollback()` is automatically invoked, preventing orphaned ledger records or "lost money" anomalies.

2. **Defense-in-Depth Authentication**:
   - Werkzeug secure password hashing (`generate_password_hash`) uses salt and 600,000 PBKDF2 iterations.
   - Passwords are never stored or logged in plain text.
   - Protected routes verify that the authenticated user has not been deactivated in the database on every request.

3. **Role-Based Authorization (RBAC)**:
   - Specialized `@admin_required` and `@customer_required` decorators ensure that customers cannot access administrative controls or view other customers' account ledgers.

4. **SQL Injection Defense**:
   - Every database operation is performed through SQLAlchemy parameterized queries, preventing SQL injection vulnerabilities.

5. **Financial Ledger Immutability**:
   - Transaction records are write-only.
   - Soft-deactivation is implemented instead of hard deletion so that financial history is preserved for compliance and auditing.

---

## 🔮 Future Roadmap

* [ ] Two-Factor Authentication (2FA) via OTP or Authenticator app (TOTP)
* [ ] PDF Account Statement Generation & Download
* [ ] Scheduled Recurring Standing Instructions (Auto-debit)
* [ ] Fixed Deposit (FD) and Recurring Deposit (RD) Calculators
* [ ] Dark Theme toggle and Multi-Currency support

---

## 👨‍💻 Author & Attribution

Developed with pride as a showcase **Full-Stack Core Banking Web Application**. Suitable for BTech CSE Capstone Projects, technical interview evaluations, and portfolio presentations.
