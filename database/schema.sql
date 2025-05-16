-- Create Groups Table
CREATE TABLE IF NOT EXISTS Groups (
    group_id SERIAL PRIMARY KEY,
    group_name VARCHAR(100) NOT NULL UNIQUE,
    discord VARCHAR(100),
    website VARCHAR(100),
    creator_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS group_name_idx ON groups USING hash(group_name);

-- Create Series Table
CREATE TABLE IF NOT EXISTS Series (
    series_id SERIAL PRIMARY KEY,
    series_name VARCHAR(100) NOT NULL UNIQUE,
    series_drive_link VARCHAR(255) NOT NULL,
    style_guide VARCHAR(255),
    mangadex VARCHAR(255),
    github_link VARCHAR(255),
    thumbnail VARCHAR(255),
    blocked_websites VARCHAR(100)[],
    is_archived BOOLEAN DEFAULT FALSE,
    group_id INT REFERENCES Groups(group_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS series_name_idx ON series USING hash(series_name);

-- Create Chapters Table
CREATE TABLE IF NOT EXISTS Chapters (
    chapter_id SERIAL PRIMARY KEY,
    chapter_name VARCHAR(100) NOT NULL,
    drive_link VARCHAR(255),
    series_id INT REFERENCES Series(series_id) ON DELETE CASCADE,
    is_archived BOOLEAN DEFAULT FALSE,
    UNIQUE(series_id, chapter_name)
);

CREATE INDEX IF NOT EXISTS chapter_name_idx ON chapters USING hash(chapter_name);

-- Create Jobs Table
CREATE TABLE IF NOT EXISTS Jobs (
    job_id SERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL UNIQUE,
    role_id VARCHAR(100) NOT NULL,
    job_type INT NOT NULL,
    jobboard_channel VARCHAR(100),
    creator_id VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS job_name_idx ON jobs USING hash(job_name);

-- Create Series Jobs Table
CREATE TABLE IF NOT EXISTS SeriesJobs (
    series_job_id SERIAL PRIMARY KEY,
    series_id INT REFERENCES Series(series_id) ON DELETE CASCADE,
    job_id INT REFERENCES Jobs(job_id) ON DELETE CASCADE,
    UNIQUE(series_id, job_id)
);

-- Create Chapter Jobs Assignments Table
CREATE TABLE IF NOT EXISTS JobsAssignments (
    assignment_id SERIAL PRIMARY KEY,
    chapter_id INT REFERENCES Chapters(chapter_id) ON DELETE CASCADE,
    series_job_id INT REFERENCES SeriesJobs(series_job_id) ON DELETE CASCADE,
    assigned_to VARCHAR(100) NOT NULL,
    status INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    reminded_at TIMESTAMPTZ,
    available_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    account BOOLEAN DEFAULT TRUE,
    UNIQUE(chapter_id, series_job_id)
);

-- Create Series Assignments Table
CREATE TABLE IF NOT EXISTS SeriesAssignments (
    series_assignment_id SERIAL PRIMARY KEY,
    series_id INT REFERENCES Series(series_id) ON DELETE CASCADE,
    series_job_id INT REFERENCES SeriesJobs(series_job_id) ON DELETE CASCADE,
    assigned_to VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(series_id, series_job_id)
);

-- Create Members Table
CREATE TABLE IF NOT EXISTS Members (
    member_id SERIAL PRIMARY KEY,
    discord_id VARCHAR(100) NOT NULL UNIQUE,
    credit_name VARCHAR(100),
    authority_level INT DEFAULT 0 CHECK (authority_level IN (0, 1, 2)),
    reminder_notifications INT DEFAULT 2, -- 0: Never, 1: 3 days, 2: 7 days, 3: 14 days
    jobboard_notifications BOOLEAN DEFAULT TRUE,
    stage_notifications BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    reminded_at TIMESTAMPTZ DEFAULT NULL
);

-- Create Series Subscriptions Table
CREATE TABLE IF NOT EXISTS SeriesSubscriptions (
    subscription_id SERIAL PRIMARY KEY,
    member_id INT REFERENCES Members(member_id) ON DELETE CASCADE,
    series_id INT REFERENCES Series(series_id) ON DELETE CASCADE,
    subscribed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(member_id, series_id)
);

-- Job Board Posts Table
CREATE TABLE IF NOT EXISTS BoardPosts (
    boardpost_id SERIAL PRIMARY KEY,
    message_id VARCHAR(100) NOT NULL,
    chapter_id INT REFERENCES Chapters(chapter_id) ON DELETE CASCADE,
    series_job_id INT REFERENCES SeriesJobs(series_job_id) ON DELETE CASCADE,
    staff_level INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chapter_id, series_job_id)
);

-- Retired Members Table
CREATE TABLE IF NOT EXISTS MembersRetired (
    member_id INT PRIMARY KEY,
    discord_id VARCHAR(100) NOT NULL,
    credit_name VARCHAR(100),
    authority_level INT,
    reminder_notifications INT,
    jobboard_notifications BOOLEAN,
    stage_notifications BOOLEAN,
    created_at TIMESTAMPTZ,
    retired_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    roles VARCHAR(100)[]
);

-- Upload Scheduler Table
CREATE TABLE IF NOT EXISTS UploadSchedules (
    upload_id SERIAL PRIMARY KEY,
    volume_number INT,
    chapter_number INT NOT NULL,
    language VARCHAR(20) NOT NULL,
    chapter_name VARCHAR(100),
    group_ids VARCHAR(100)[] NOT NULL,
    series_id VARCHAR(100) NOT NULL,
    folder_name VARCHAR(100) NOT NULL,
    upload_time TIMESTAMPTZ NOT NULL,
    discord_id VARCHAR(100) NOT NULL,
    series_name VARCHAR(100) NOT NULL,
    group_name VARCHAR(100) NOT NULL,
    github_link VARCHAR(100),
    upload_websites VARCHAR(100)[] NOT NULL,
    chapter_id INT REFERENCES Chapters(chapter_id) ON DELETE CASCADE
);

-- ======================================================================
-- ==================== DATA ARCHIVE AFTER THIS LINE ====================
-- ======================================================================
CREATE TABLE IF NOT EXISTS JobsAssignmentsArchive (
    assignment_id INT PRIMARY KEY,
    chapter_id INT,
    series_job_id INT,
    assigned_to VARCHAR(100) NOT NULL,
    status INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    available_at TIMESTAMPTZ,
    reminded_at TIMESTAMPTZ,
    account BOOLEAN DEFAULT TRUE,
    archived_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chapter_id, series_job_id, assigned_to)
);

CREATE OR REPLACE FUNCTION archive_jobs_assignments() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO JobsAssignmentsArchive
    (assignment_id, chapter_id, series_job_id, assigned_to, status, created_at, completed_at, reminded_at, available_at, account)
    VALUES
    (OLD.assignment_id, OLD.chapter_id, OLD.series_job_id, OLD.assigned_to, OLD.status, OLD.created_at, OLD.completed_at, OLD.reminded_at, OLD.available_at, OLD.account)
    ON CONFLICT(chapter_id, series_job_id, assigned_to)
    DO UPDATE SET
        status = EXCLUDED.status,
        created_at = EXCLUDED.created_at,
        completed_at = EXCLUDED.completed_at,
        reminded_at = EXCLUDED.reminded_at,
        available_at = EXCLUDED.available_at,
        account = EXCLUDED.account;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'archive_jobs_before_delete'
    ) THEN
        CREATE TRIGGER archive_jobs_before_delete
        BEFORE DELETE ON JobsAssignments
        FOR EACH ROW
        EXECUTE FUNCTION archive_jobs_assignments();
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS MembersArchive (
    member_id INT PRIMARY KEY,
    discord_id VARCHAR(100) NOT NULL,
    credit_name VARCHAR(100),
    authority_level INT,
    reminder_notifications INT,
    jobboard_notifications BOOLEAN,
    stage_notifications BOOLEAN,
    created_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(discord_id)
);

CREATE OR REPLACE FUNCTION archive_members() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO MembersArchive
    (member_id, discord_id, credit_name, authority_level, reminder_notifications, jobboard_notifications, stage_notifications, created_at)
    VALUES
    (OLD.member_id, OLD.discord_id, OLD.credit_name, OLD.authority_level, OLD.reminder_notifications, OLD.jobboard_notifications, OLD.stage_notifications, OLD.created_at)
    ON CONFLICT (discord_id)
    DO UPDATE SET
        member_id = EXCLUDED.member_id,
        credit_name = EXCLUDED.credit_name,
        authority_level = EXCLUDED.authority_level,
        reminder_notifications = EXCLUDED.reminder_notifications,
        jobboard_notifications = EXCLUDED.jobboard_notifications,
        stage_notifications = EXCLUDED.stage_notifications,
        created_at = EXCLUDED.created_at;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'archive_members_before_delete'
    ) THEN
        CREATE TRIGGER archive_members_before_delete
        BEFORE DELETE ON Members
        FOR EACH ROW
        EXECUTE FUNCTION archive_members();
    END IF;
END;
$$ LANGUAGE plpgsql;