CREATE DATABASE LIFEDATA;
CREATE SCHEMA LIFEDATA:
CREATE OR REPLACE TABLE users (
    user_id INTEGER AUTOINCREMENT PRIMARY KEY,
    name VARCHAR,
    email VARCHAR,
    username VARCHAR,
    password VARCHAR
);

CREATE OR REPLACE TABLE profiles (
    profile_id INTEGER AUTOINCREMENT PRIMARY KEY,
    user_id INTEGER UNIQUE,
    name VARCHAR,
    major VARCHAR,
    bio VARCHAR,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
);

CREATE OR REPLACE TABLE groups (
    group_id INTEGER AUTOINCREMENT PRIMARY KEY,
    group_name VARCHAR
);

CREATE OR REPLACE TABLE event_sources (
    source_id INTEGER AUTOINCREMENT PRIMARY KEY,
    source_name VARCHAR,
    source_url VARCHAR,
    source_type VARCHAR
);

CREATE OR REPLACE TABLE events (
    event_id INTEGER AUTOINCREMENT PRIMARY KEY,
    event_title VARCHAR,
    event_description VARCHAR,
    source_id INTEGER,
    FOREIGN KEY (source_id)
        REFERENCES event_sources(source_id)
);
CREATE OR REPLACE TABLE tags (
    tag_id INTEGER AUTOINCREMENT PRIMARY KEY,
    tag_name VARCHAR UNIQUE
);

CREATE OR REPLACE TABLE profile_tags (
    profile_id INTEGER,
    tag_id INTEGER,

    PRIMARY KEY (profile_id, tag_id),

    FOREIGN KEY (profile_id)
        REFERENCES profiles(profile_id),

    FOREIGN KEY (tag_id)
        REFERENCES tags(tag_id)
);

CREATE OR REPLACE TABLE group_tags (
    group_id INTEGER,
    tag_id INTEGER,

    PRIMARY KEY (group_id, tag_id),

    FOREIGN KEY (group_id)
        REFERENCES groups(group_id),

    FOREIGN KEY (tag_id)
        REFERENCES tags(tag_id)
);

CREATE OR REPLACE TABLE event_tags (
    event_id INTEGER,
    tag_id INTEGER,

    PRIMARY KEY (event_id, tag_id),

    FOREIGN KEY (event_id)
        REFERENCES events(event_id),

    FOREIGN KEY (tag_id)
        REFERENCES tags(tag_id)
);