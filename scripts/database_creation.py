"""
Database Creation Script

This script reads transaction data from CSV, cleans and transforms it,
and creates a SQLite database with the transactions table.

Usage:
    python scripts/database_creation.py
"""

import pandas as pd
import sqlite3
from sqlalchemy import create_engine, types
import os
import sys


def get_project_root():
    """Get the project root directory."""
    current_dir = os.getcwd()
    if os.path.basename(current_dir) == 'scripts':
        # If running from scripts directory, go up one level
        project_root = os.path.dirname(current_dir)
    else:
        # If running from project root, use current directory
        project_root = current_dir
    return project_root


def setup_paths():
    """Setup file paths for CSV and database."""
    project_root = get_project_root()
    csv_path = os.path.join(project_root, "data", "data.csv")
    db_path = os.path.join(project_root, "database", "transactions.db")
    table_name = "transactions"
    
    return csv_path, db_path, table_name


def create_database_directory(db_path):
    """Create database directory if it doesn't exist."""
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"Created database directory: {db_dir}")


def load_and_clean_data(csv_path):
    """Load CSV data and perform initial cleaning."""
    print(f"Reading CSV file from: {csv_path}")
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at {csv_path}")
    
    # Read CSV
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from CSV")
    
    # Remove duplicate columns
    df = df.loc[:, ~df.columns.duplicated()]
    
    # Clean column names: strip whitespace, replace spaces with underscores, lowercase
    df.columns = [c.strip().replace(" ", "_").lower() for c in df.columns]
    
    return df


def transform_data(df):
    """Transform data: rename columns, parse dates, add transaction type."""
    print("Transforming data...")
    
    # Rename columns to standard names
    rename_map = {
        "clnt_id": "client_id",
        "bank_id": "bank_id",
        "acc_id": "account_id",
        "txn_id": "transaction_id",
        "txn_date": "transaction_date",
        "desc": "description",
        "amt": "amount",
        "cat": "category",
        "merchant": "merchant",
    }
    df = df.rename(columns=rename_map)
    
    # Parse transaction_date including time (dayfirst=True for DD/MM/YYYY format)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], dayfirst=True)
    
    # Add transaction_type based on amount (positive = Credit, negative = Debit)
    df["transaction_type"] = df["amount"].apply(lambda x: "Credit" if x > 0 else "Debit")
    
    print(f"Data transformed. Shape: {df.shape}")
    return df


def create_database(df, db_path, table_name):
    """Create SQLite database and write DataFrame to it."""
    print(f"Creating database at: {db_path}")
    
    # Create database directory if needed
    create_database_directory(db_path)
    
    # Create SQLAlchemy engine for SQLite
    engine = create_engine(f"sqlite:///{db_path}")
    
    # Define SQLite datatypes for each column
    column_types = {
        "client_id": types.Integer(),
        "bank_id": types.Integer(),
        "account_id": types.Integer(),
        "transaction_id": types.Integer(),
        "transaction_date": types.DateTime(),
        "transaction_type": types.Text(),
        "description": types.Text(),
        "amount": types.Float(),
        "category": types.Text(),
        "merchant": types.Text(),
    }
    
    # Write DataFrame to SQLite with explicit schema
    df.to_sql(
        table_name,
        engine,
        if_exists="replace",   # replace table if already exists
        index=False,
        dtype=column_types     # apply schema
    )
    
    print("✅ CSV successfully imported into SQLite with explicit datatypes!")


def run_database_tests(db_path, table_name):
    """Run tests to verify database was created correctly."""
    print("\n" + "="*50)
    print("Running database tests...")
    print("="*50)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    def run_test(test_name, query, expected=None, check_fn=None):
        """Run a single test and print results."""
        print(f"\n=== {test_name} ===")
        result = cursor.execute(query).fetchall()
        print(f"Result: {result}")
        
        if expected is not None:
            if result == expected:
                print("✅ PASSED")
                return True
            else:
                print(f"❌ FAILED — expected: {expected}")
                return False
        elif check_fn:
            if check_fn(result):
                print("✅ PASSED")
                return True
            else:
                print("❌ FAILED")
                return False
        else:
            print("⚠️  No expected value provided")
            return None
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Table exists
    tests_total += 1
    if run_test(
        "Test 1: Table exists",
        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';",
        expected=[(table_name,)]
    ):
        tests_passed += 1
    
    # Test 2: Table is not empty
    tests_total += 1
    if run_test(
        "Test 2: Table is not empty",
        f"SELECT COUNT(*) FROM {table_name};",
        check_fn=lambda r: r[0][0] > 0
    ):
        tests_passed += 1
    
    # Test 3: Required columns exist
    required_cols = [
        "client_id", "bank_id", "account_id", "transaction_id",
        "transaction_date", "transaction_type", "description", 
        "amount", "category", "merchant"
    ]
    tests_total += 1
    if run_test(
        "Test 3: Required columns exist",
        f"PRAGMA table_info({table_name});",
        check_fn=lambda r: all(col in [row[1] for row in r] for col in required_cols)
    ):
        tests_passed += 1
    
    # Test 4: Sample query - check first 5 rows load correctly
    tests_total += 1
    run_test(
        "Test 4: Fetch Details",
        f"SELECT * FROM {table_name} WHERE client_id = 809 AND bank_id = 1 AND account_id = 1 AND transaction_id = 1 LIMIT 1;"
    )
    
    conn.close()
    
    print("\n" + "="*50)
    print(f"Tests completed: {tests_passed}/{tests_total} passed")
    print("="*50)
    
    return tests_passed == tests_total


def main():
    """Main function to orchestrate database creation."""
    try:
        print("="*50)
        print("Transaction Database Creation Script")
        print("="*50)
        
        # Setup paths
        csv_path, db_path, table_name = setup_paths()
        
        # Load and clean data
        df = load_and_clean_data(csv_path)
        
        # Transform data
        df = transform_data(df)
        
        # Create database
        create_database(df, db_path, table_name)
        
        # Run tests
        tests_passed = run_database_tests(db_path, table_name)
        
        if tests_passed:
            print("\n✅ Database creation completed successfully!")
            sys.exit(0)
        else:
            print("\n⚠️  Database created but some tests failed. Please review.")
            sys.exit(1)
            
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

