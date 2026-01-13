-- Database schema for Greyhound Racing Value Finder
-- PostgreSQL DDL for races, dogs, and odds tables

-- Races table: stores scheduled and completed greyhound races
CREATE TABLE IF NOT EXISTS races (
    race_id VARCHAR(100) PRIMARY KEY,
    track_name VARCHAR(255) NOT NULL,
    race_time TIMESTAMP NOT NULL,
    distance INTEGER,
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for time-based queries (finding upcoming races, filtering by date range)
CREATE INDEX IF NOT EXISTS idx_races_race_time ON races(race_time);

-- Dogs table: stores greyhound entries for races with statistics
-- Note: race_id and trap_number can be NULL for stats-only dogs (Phase 2)
-- These fields are populated when dogs are assigned to races (Phase 3)
CREATE TABLE IF NOT EXISTS dogs (
    dog_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    race_id VARCHAR(100) REFERENCES races(race_id) ON DELETE CASCADE,
    trap_number INTEGER CHECK (trap_number IS NULL OR (trap_number BETWEEN 1 AND 6)),
    stats JSONB,
    last_stats_update TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for efficient joins with races table
CREATE INDEX IF NOT EXISTS idx_dogs_race_id ON dogs(race_id);

-- Odds table: stores historical odds data from bookmakers
CREATE TABLE IF NOT EXISTS odds (
    odds_id VARCHAR(100) PRIMARY KEY,
    race_id VARCHAR(100) NOT NULL REFERENCES races(race_id) ON DELETE CASCADE,
    dog_id VARCHAR(100) NOT NULL REFERENCES dogs(dog_id) ON DELETE CASCADE,
    bookmaker VARCHAR(100),
    decimal_odds DECIMAL(10,2),
    fractional_odds VARCHAR(20),
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Composite index for efficient odds history queries (by race, dog, and time)
CREATE INDEX IF NOT EXISTS idx_odds_race_dog_timestamp ON odds(race_id, dog_id, timestamp);
