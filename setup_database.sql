-- Irium Database Setup Script
-- Run this in pgAdmin Query Tool or psql

-- Create user for Irium
CREATE USER irium WITH PASSWORD 'irium_password';

-- Create database
CREATE DATABASE irium_db OWNER irium;

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE irium_db TO irium;

-- Connect to the new database (if using psql, uncomment the line below)
-- \c irium_db

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO irium;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO irium;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO irium;

-- Verify setup
SELECT 'Database setup complete! Use this connection string:' as message;
SELECT 'postgresql://irium:irium_password@localhost:5432/irium_db' as connection_string;
