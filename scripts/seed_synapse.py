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
    """Load Synapse config from YAML file."""
    config_path = CONFIG_DIR / f"{config_name}.yaml"
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for agent in config.get("data_agents", []):
        if agent.get("synapse_config"):
            if agent_name is None or agent.get("name") == agent_name:
                synapse_config = agent["synapse_config"]
                return {
                    "server": synapse_config.get("server", ""),
                    "database": synapse_config.get("database", ""),
                    "use_aad": synapse_config.get("use_aad", False),
                    "username": synapse_config.get("username", ""),
                    "password": os.getenv(
                        "SYNAPSE_PASSWORD", synapse_config.get("password", "")
                    ),
                    "driver": synapse_config.get(
                        "driver", "ODBC Driver 18 for SQL Server"
                    ),
                    "connection_string": os.getenv(
                        "SYNAPSE_CONNECTION_STRING",
                        synapse_config.get("connection_string", ""),
                    ),
                }

    print(
        f"No synapse_config found in {config_name}.yaml"
        + (f" for agent '{agent_name}'" if agent_name else "")
    )
    sys.exit(1)


SCHEMA_SQL = """
IF OBJECT_ID('dbo.FactReservations', 'U') IS NOT NULL DROP TABLE dbo.FactReservations;
IF OBJECT_ID('dbo.DimBookingChannel', 'U') IS NOT NULL DROP TABLE dbo.DimBookingChannel;
IF OBJECT_ID('dbo.DimGuest', 'U') IS NOT NULL DROP TABLE dbo.DimGuest;
IF OBJECT_ID('dbo.DimRoomType', 'U') IS NOT NULL DROP TABLE dbo.DimRoomType;
IF OBJECT_ID('dbo.DimHotel', 'U') IS NOT NULL DROP TABLE dbo.DimHotel;
IF OBJECT_ID('dbo.DimDate', 'U') IS NOT NULL DROP TABLE dbo.DimDate;

CREATE TABLE dbo.DimDate (
    DateKey INT NOT NULL,
    FullDate DATE NOT NULL,
    Year INT NOT NULL,
    Quarter INT NOT NULL,
    Month INT NOT NULL,
    MonthName NVARCHAR(20) NOT NULL,
    WeekOfYear INT NOT NULL,
    DayOfWeek INT NOT NULL,
    IsWeekend BIT NOT NULL,
    IsHoliday BIT NOT NULL,
    HolidayName NVARCHAR(50) NULL
)
WITH (DISTRIBUTION = REPLICATE);

CREATE TABLE dbo.DimHotel (
    HotelKey INT NOT NULL,
    HotelName NVARCHAR(100) NOT NULL,
    Brand NVARCHAR(50) NOT NULL,
    City NVARCHAR(50) NOT NULL,
    State NVARCHAR(20) NOT NULL,
    Country NVARCHAR(50) NOT NULL,
    Region NVARCHAR(20) NOT NULL,
    StarRating INT NOT NULL,
    TotalRooms INT NOT NULL,
    HasPool BIT NOT NULL,
    HasSpa BIT NOT NULL,
    HasRestaurant BIT NOT NULL
)
WITH (DISTRIBUTION = REPLICATE);

CREATE TABLE dbo.DimRoomType (
    RoomTypeKey INT NOT NULL,
    RoomTypeName NVARCHAR(50) NOT NULL,
    MaxOccupancy INT NOT NULL,
    SquareFeet INT NOT NULL,
    HasBalcony BIT NOT NULL,
    HasOceanView BIT NOT NULL
)
WITH (DISTRIBUTION = REPLICATE);

CREATE TABLE dbo.DimGuest (
    GuestKey INT NOT NULL,
    GuestName NVARCHAR(100) NOT NULL,
    Email NVARCHAR(100) NOT NULL,
    LoyaltyTier NVARCHAR(20) NOT NULL,
    LoyaltyPoints INT NOT NULL,
    Country NVARCHAR(50) NOT NULL,
    State NVARCHAR(20) NULL
)
WITH (DISTRIBUTION = REPLICATE);

CREATE TABLE dbo.DimBookingChannel (
    ChannelKey INT NOT NULL,
    ChannelName NVARCHAR(50) NOT NULL,
    ChannelType NVARCHAR(20) NOT NULL,
    CommissionRate DECIMAL(5,2) NOT NULL
)
WITH (DISTRIBUTION = REPLICATE);

CREATE TABLE dbo.FactReservations (
    ReservationKey BIGINT NOT NULL,
    CheckInDateKey INT NOT NULL,
    CheckOutDateKey INT NOT NULL,
    BookingDateKey INT NOT NULL,
    HotelKey INT NOT NULL,
    RoomTypeKey INT NOT NULL,
    GuestKey INT NOT NULL,
    ChannelKey INT NOT NULL,
    NightsStayed INT NOT NULL,
    RoomRate DECIMAL(10,2) NOT NULL,
    TotalRoomRevenue DECIMAL(10,2) NOT NULL,
    FoodBevRevenue DECIMAL(10,2) NOT NULL,
    SpaRevenue DECIMAL(10,2) NOT NULL,
    OtherRevenue DECIMAL(10,2) NOT NULL,
    TotalRevenue DECIMAL(10,2) NOT NULL,
    Adults INT NOT NULL,
    Children INT NOT NULL,
    IsCancelled BIT NOT NULL,
    CancellationReason NVARCHAR(100) NULL
)
WITH (DISTRIBUTION = HASH(HotelKey));
"""


def load_data() -> dict:
    """Load sample data from JSON file."""
    data_file = Path(__file__).parent / "data" / "synapse_data.json"
    if not data_file.exists():
        print(f"Data file not found: {data_file}")
        sys.exit(1)

    with Path(data_file).open(encoding="utf-8") as f:
        return json.load(f)


def _get_access_token() -> bytes:
    """Get an Azure AD access token for Synapse Analytics."""
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError:
        print(
            "azure-identity is required for AAD authentication. Install with: uv add azure-identity"
        )
        sys.exit(1)

    credential = DefaultAzureCredential()
    token = credential.get_token("https://database.windows.net/.default")
    print("Token acquired")
    token_bytes = token.token.encode("utf-16-le")
    return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)


def seed_synapse(config_name: str, agent_name: str | None = None) -> None:
    """Seed Synapse Analytics with hotel reservation data from JSON file."""
    try:
        import pyodbc
    except ImportError:
        print("pyodbc is required. Install with: uv add pyodbc")
        sys.exit(1)

    config = load_config(config_name, agent_name)

    if not config["server"]:
        print("server is required in synapse_config")
        sys.exit(1)

    SQL_COPT_SS_ACCESS_TOKEN = 1256

    if config["connection_string"]:
        print("Connecting to Synapse using connection string...")
        conn = pyodbc.connect(config["connection_string"], autocommit=True)
    elif config["use_aad"]:
        if not config["server"]:
            print("server is required in synapse_config when use_aad=true")
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
        conn = pyodbc.connect(
            conn_str,
            attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct},
            autocommit=True,
        )
    else:
        if not config["server"]:
            print("server is required in synapse_config")
            sys.exit(1)
        if not config["username"] or not config["password"]:
            print(
                "username and password (or SYNAPSE_PASSWORD env var) are required when use_aad=false"
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
        conn = pyodbc.connect(conn_str, autocommit=True)

    print(f"Connected to {config['database']}")

    try:
        cursor = conn.cursor()

        print("Creating schema...")
        for statement in SCHEMA_SQL.split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        print("Schema created")

        # Load data
        data = load_data()

        # Insert DimDate
        for row in data["dim_date"]:
            cursor.execute(
                """
                INSERT INTO dbo.DimDate
                (DateKey, FullDate, Year, Quarter, Month, MonthName, WeekOfYear, DayOfWeek, IsWeekend, IsHoliday, HolidayName)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row["DateKey"],
                row["FullDate"],
                row["Year"],
                row["Quarter"],
                row["Month"],
                row["MonthName"],
                row["WeekOfYear"],
                row["DayOfWeek"],
                1 if row["IsWeekend"] else 0,
                1 if row["IsHoliday"] else 0,
                row.get("HolidayName"),
            )
        print(f"Inserted {len(data['dim_date'])} date records")

        # Insert DimHotel
        for row in data["dim_hotel"]:
            cursor.execute(
                """
                INSERT INTO dbo.DimHotel
                (HotelKey, HotelName, Brand, City, State, Country, Region, StarRating, TotalRooms, HasPool, HasSpa, HasRestaurant)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row["HotelKey"],
                row["HotelName"],
                row["Brand"],
                row["City"],
                row["State"],
                row["Country"],
                row["Region"],
                row["StarRating"],
                row["TotalRooms"],
                1 if row["HasPool"] else 0,
                1 if row["HasSpa"] else 0,
                1 if row["HasRestaurant"] else 0,
            )
        print(f"Inserted {len(data['dim_hotel'])} hotel records")

        # Insert DimRoomType
        for row in data["dim_room_type"]:
            cursor.execute(
                """
                INSERT INTO dbo.DimRoomType
                (RoomTypeKey, RoomTypeName, MaxOccupancy, SquareFeet, HasBalcony, HasOceanView)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                row["RoomTypeKey"],
                row["RoomTypeName"],
                row["MaxOccupancy"],
                row["SquareFeet"],
                1 if row["HasBalcony"] else 0,
                1 if row["HasOceanView"] else 0,
            )
        print(f"Inserted {len(data['dim_room_type'])} room type records")

        # Insert DimGuest
        for row in data["dim_guest"]:
            cursor.execute(
                """
                INSERT INTO dbo.DimGuest
                (GuestKey, GuestName, Email, LoyaltyTier, LoyaltyPoints, Country, State)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                row["GuestKey"],
                row["GuestName"],
                row["Email"],
                row["LoyaltyTier"],
                row["LoyaltyPoints"],
                row["Country"],
                row.get("State"),
            )
        print(f"Inserted {len(data['dim_guest'])} guest records")

        # Insert DimBookingChannel
        for row in data["dim_booking_channel"]:
            cursor.execute(
                """
                INSERT INTO dbo.DimBookingChannel
                (ChannelKey, ChannelName, ChannelType, CommissionRate)
                VALUES (?, ?, ?, ?)
                """,
                row["ChannelKey"],
                row["ChannelName"],
                row["ChannelType"],
                row["CommissionRate"],
            )
        print(f"Inserted {len(data['dim_booking_channel'])} booking channel records")

        # Insert FactReservations
        for row in data["fact_reservations"]:
            cursor.execute(
                """
                INSERT INTO dbo.FactReservations
                (ReservationKey, CheckInDateKey, CheckOutDateKey, BookingDateKey, HotelKey, RoomTypeKey,
                 GuestKey, ChannelKey, NightsStayed, RoomRate, TotalRoomRevenue, FoodBevRevenue,
                 SpaRevenue, OtherRevenue, TotalRevenue, Adults, Children, IsCancelled, CancellationReason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row["ReservationKey"],
                row["CheckInDateKey"],
                row["CheckOutDateKey"],
                row["BookingDateKey"],
                row["HotelKey"],
                row["RoomTypeKey"],
                row["GuestKey"],
                row["ChannelKey"],
                row["NightsStayed"],
                row["RoomRate"],
                row["TotalRoomRevenue"],
                row["FoodBevRevenue"],
                row["SpaRevenue"],
                row["OtherRevenue"],
                row["TotalRevenue"],
                row["Adults"],
                row["Children"],
                1 if row["IsCancelled"] else 0,
                row.get("CancellationReason"),
            )
        print(f"Inserted {len(data['fact_reservations'])} fact reservations")

        print("Synapse database seeded successfully!")
        cursor.close()
        conn.close()

    except pyodbc.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed Azure Synapse with hotel analytics data"
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
        default="hotel_analytics",
        help="Agent name within the config (default: first agent with synapse_config)",
    )
    args = parser.parse_args()
    seed_synapse(args.config, args.agent)
