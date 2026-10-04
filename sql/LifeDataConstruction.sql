-- Bootstrap for a new database. For existing tables, also run
-- sql/001_align_lifedata_with_terplink.sql to add the missing columns.
-- IF NOT EXISTS preserves existing tables and rows when this file is rerun.
CREATE DATABASE IF NOT EXISTS LIFEDATA;
CREATE SCHEMA IF NOT EXISTS LIFEDATA.MAIN;
USE DATABASE LIFEDATA;
USE SCHEMA MAIN;

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER AUTOINCREMENT PRIMARY KEY,
    name VARCHAR,
    email VARCHAR,
    username VARCHAR,
    password VARCHAR
);

CREATE TABLE IF NOT EXISTS profiles (
    profile_id INTEGER AUTOINCREMENT PRIMARY KEY,
    user_id INTEGER UNIQUE,
    name VARCHAR,
    major VARCHAR,
    bio VARCHAR,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS groups (
    group_id INTEGER AUTOINCREMENT PRIMARY KEY,
    group_name VARCHAR,
    group_description VARCHAR,
    group_location VARCHAR,
    meeting_details VARCHAR,
    created_at TIMESTAMP_TZ
);

CREATE TABLE IF NOT EXISTS event_sources (
    source_id INTEGER AUTOINCREMENT PRIMARY KEY,
    source_name VARCHAR,
    source_url VARCHAR,
    source_type VARCHAR
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER AUTOINCREMENT PRIMARY KEY,
    event_title VARCHAR,
    event_description VARCHAR,
    event_location VARCHAR,
    event_date DATE,
    event_time TIME,
    created_at TIMESTAMP_TZ,
    source_id INTEGER,
    FOREIGN KEY (source_id)
        REFERENCES event_sources(source_id)
);
CREATE TABLE IF NOT EXISTS tags (
    tag_id INTEGER AUTOINCREMENT PRIMARY KEY,
    tag_name VARCHAR UNIQUE
);

CREATE TABLE IF NOT EXISTS profile_tags (
    profile_id INTEGER,
    tag_id INTEGER,

    PRIMARY KEY (profile_id, tag_id),

    FOREIGN KEY (profile_id)
        REFERENCES profiles(profile_id),

    FOREIGN KEY (tag_id)
        REFERENCES tags(tag_id)
);

CREATE TABLE IF NOT EXISTS group_tags (
    group_id INTEGER,
    tag_id INTEGER,

    PRIMARY KEY (group_id, tag_id),

    FOREIGN KEY (group_id)
        REFERENCES groups(group_id),

    FOREIGN KEY (tag_id)
        REFERENCES tags(tag_id)
);

CREATE TABLE IF NOT EXISTS event_tags (
    event_id INTEGER,
    tag_id INTEGER,

    PRIMARY KEY (event_id, tag_id),

    FOREIGN KEY (event_id)
        REFERENCES events(event_id),

    FOREIGN KEY (tag_id)
        REFERENCES tags(tag_id)
);
