
-- 活動資料表
CREATE TABLE activities (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    event_date TIMESTAMP NOT NULL,
    registration_deadline TIMESTAMP NOT NULL
);

-- 報名資料表
CREATE TABLE registrations (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    activity_id INTEGER NOT NULL,
    name VARCHAR(50) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (activity_id)
        REFERENCES activities(id)
        ON DELETE CASCADE,

    UNIQUE (activity_id, name, phone)
);
