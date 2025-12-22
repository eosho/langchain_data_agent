import argparse
import json
import os
import struct
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR = Path(__file__).parent.parent / "src" / "data_agent" / "config"


def load_config(config_name: str, agent_name: str | None = None) -> dict:
    """Load Azure SQL config from YAML file."""
    config_path = CONFIG_DIR / f"{config_name}.yaml"
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for agent in config.get("data_agents", []):
        if agent.get("azure_sql_config"):
            if agent_name is None or agent.get("name") == agent_name:
                sql_config = agent["azure_sql_config"]
                return {
                    "server": sql_config.get("server", ""),
                    "database": sql_config.get("database", ""),
                    "use_aad": sql_config.get("use_aad", False),
                    "username": sql_config.get("username", ""),
                    "password": os.getenv(
                        "AZURE_SQL_PASSWORD", sql_config.get("password", "")
                    ),
                    "driver": sql_config.get("driver", "ODBC Driver 18 for SQL Server"),
                    "connection_string": os.getenv(
                        "AZURE_SQL_CONNECTION_STRING",
                        sql_config.get("connection_string", ""),
                    ),
                }

    print(
        f"No azure_sql_config found in {config_name}.yaml"
        + (f" for agent '{agent_name}'" if agent_name else "")
    )
    sys.exit(1)


SCHEMA_SQL = """
IF OBJECT_ID('dbo.TimeOffRequests', 'U') IS NOT NULL DROP TABLE dbo.TimeOffRequests;
IF OBJECT_ID('dbo.PerformanceReviews', 'U') IS NOT NULL DROP TABLE dbo.PerformanceReviews;
IF OBJECT_ID('dbo.Employees', 'U') IS NOT NULL DROP TABLE dbo.Employees;
IF OBJECT_ID('dbo.Departments', 'U') IS NOT NULL DROP TABLE dbo.Departments;

CREATE TABLE dbo.Departments (
    DepartmentID INT PRIMARY KEY,
    Name NVARCHAR(100) NOT NULL,
    Budget MONEY NOT NULL,
    ManagerID INT NULL
);

CREATE TABLE dbo.Employees (
    EmployeeID INT PRIMARY KEY,
    FirstName NVARCHAR(50) NOT NULL,
    LastName NVARCHAR(50) NOT NULL,
    Email NVARCHAR(100) NOT NULL,
    DepartmentID INT NOT NULL REFERENCES dbo.Departments(DepartmentID),
    Title NVARCHAR(100) NOT NULL,
    HireDate DATE NOT NULL,
    Salary MONEY NOT NULL,
    ManagerID INT NULL,
    IsActive BIT DEFAULT 1
);

CREATE TABLE dbo.PerformanceReviews (
    ReviewID INT PRIMARY KEY,
    EmployeeID INT NOT NULL REFERENCES dbo.Employees(EmployeeID),
    ReviewDate DATE NOT NULL,
    Rating INT NOT NULL CHECK (Rating BETWEEN 1 AND 5),
    ReviewerID INT NOT NULL REFERENCES dbo.Employees(EmployeeID),
    Comments NVARCHAR(500)
);

CREATE TABLE dbo.TimeOffRequests (
    RequestID INT PRIMARY KEY,
    EmployeeID INT NOT NULL REFERENCES dbo.Employees(EmployeeID),
    StartDate DATE NOT NULL,
    EndDate DATE NOT NULL,
    Type NVARCHAR(20) NOT NULL CHECK (Type IN ('Vacation', 'Sick', 'Personal', 'Conference')),
    Status NVARCHAR(20) NOT NULL CHECK (Status IN ('Pending', 'Approved', 'Denied')),
    DaysRequested INT NOT NULL
);

CREATE INDEX IX_Employees_Department ON dbo.Employees(DepartmentID);
CREATE INDEX IX_Employees_Manager ON dbo.Employees(ManagerID);
CREATE INDEX IX_Employees_IsActive ON dbo.Employees(IsActive);
CREATE INDEX IX_PerformanceReviews_Employee ON dbo.PerformanceReviews(EmployeeID);
CREATE INDEX IX_PerformanceReviews_Rating ON dbo.PerformanceReviews(Rating);
CREATE INDEX IX_TimeOffRequests_Employee ON dbo.TimeOffRequests(EmployeeID);
CREATE INDEX IX_TimeOffRequests_Status ON dbo.TimeOffRequests(Status);
"""


def load_data() -> dict:
    """Load sample data from JSON file."""
    data_file = Path(__file__).parent / "data" / "azure_sql_data.json"
    if not data_file.exists():
        sys.exit(1)

    with Path(data_file).open(encoding="utf-8") as f:
        return json.load(f)


def _get_access_token() -> bytes:
    """Get an Azure AD access token for SQL Database."""
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError:
        print(
            "azure-identity is required for AAD authentication. Install with: uv add azure-identity"
        )
        sys.exit(1)

    credential = DefaultAzureCredential()
    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-le")
    return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)


def seed_azure_sql(config_name: str, agent_name: str | None = None) -> None:
    """Seed Azure SQL Database with HR data from JSON file."""
    try:
        import pyodbc
    except ImportError:
        print("pyodbc is required. Install with: uv add pyodbc")
        sys.exit(1)

    config = load_config(config_name, agent_name)

    if config["connection_string"]:
        print("Connecting to Azure SQL using connection string...")
        conn = pyodbc.connect(config["connection_string"])
    elif config["use_aad"]:
        if not config["server"]:
            print("server is required in azure_sql_config when use_aad=true")
            sys.exit(1)
        print(
            f"Connecting to {config['server']} using Azure AD (DefaultAzureCredential)..."
        )
        conn_str = (
            f"DRIVER={{{config['driver']}}};"
            f"SERVER={config['server']};"
            f"DATABASE={config['database']};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
            f"Connection Timeout=30;"
        )
        token_struct = _get_access_token()
        SQL_COPT_SS_ACCESS_TOKEN = 1256
        conn = pyodbc.connect(
            conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct}
        )
    else:
        if not config["server"]:
            print("server is required in azure_sql_config")
            sys.exit(1)
        if not config["username"] or not config["password"]:
            print(
                "username and password (or AZURE_SQL_PASSWORD env var) are required when use_aad=false"
            )
            sys.exit(1)
        conn_str = (
            f"DRIVER={{{config['driver']}}};"
            f"SERVER={config['server']};"
            f"DATABASE={config['database']};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
            f"Connection Timeout=30;"
            f"UID={config['username']};PWD={config['password']};"
        )
        print(f"Connecting to {config['server']} using SQL authentication...")
        conn = pyodbc.connect(conn_str)

    try:
        cursor = conn.cursor()

        for statement in SCHEMA_SQL.split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        conn.commit()

        # Load data
        data = load_data()

        # Insert departments
        for dept in data["departments"]:
            cursor.execute(
                """
                INSERT INTO dbo.Departments (DepartmentID, Name, Budget, ManagerID)
                VALUES (?, ?, ?, ?)
                """,
                dept["DepartmentID"],
                dept["Name"],
                dept["Budget"],
                dept["ManagerID"],
            )
        conn.commit()

        # Insert employees
        for emp in data["employees"]:
            cursor.execute(
                """
                INSERT INTO dbo.Employees
                (EmployeeID, FirstName, LastName, Email, DepartmentID, Title, HireDate, Salary, ManagerID, IsActive)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                emp["EmployeeID"],
                emp["FirstName"],
                emp["LastName"],
                emp["Email"],
                emp["DepartmentID"],
                emp["Title"],
                emp["HireDate"],
                emp["Salary"],
                emp["ManagerID"],
                1 if emp["IsActive"] else 0,
            )
        conn.commit()

        # Insert performance reviews
        for review in data["performance_reviews"]:
            cursor.execute(
                """
                INSERT INTO dbo.PerformanceReviews
                (ReviewID, EmployeeID, ReviewDate, Rating, ReviewerID, Comments)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                review["ReviewID"],
                review["EmployeeID"],
                review["ReviewDate"],
                review["Rating"],
                review["ReviewerID"],
                review["Comments"],
            )
        conn.commit()

        # Insert time off requests
        for req in data["time_off_requests"]:
            cursor.execute(
                """
                INSERT INTO dbo.TimeOffRequests
                (RequestID, EmployeeID, StartDate, EndDate, Type, Status, DaysRequested)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                req["RequestID"],
                req["EmployeeID"],
                req["StartDate"],
                req["EndDate"],
                req["Type"],
                req["Status"],
                req["DaysRequested"],
            )
        conn.commit()

        print("Successfully seeded Azure SQL database!")
        print(f"   - {len(data['departments'])} departments")
        print(f"   - {len(data['employees'])} employees")
        print(f"   - {len(data['performance_reviews'])} performance reviews")
        print(f"   - {len(data['time_off_requests'])} time off requests")

        cursor.close()
        conn.close()

    except pyodbc.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed Azure SQL database with sample HR data"
    )
    parser.add_argument(
        "--config",
        "-c",
        default="adventure_works",
        help="Config file name (without .yaml extension)",
    )
    parser.add_argument(
        "--agent",
        "-a",
        default="contoso_hr",
        help="Agent name within the config (default: first agent with azure_sql_config)",
    )
    args = parser.parse_args()

    seed_azure_sql(args.config, args.agent)
