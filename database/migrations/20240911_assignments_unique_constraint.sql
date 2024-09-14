ALTER TABLE JobsAssignmentsArchive
ADD CONSTRAINT jobsassignmentsarchive_chapter_series_assigned_to UNIQUE (chapter_id, series_job_id, assigned_to);

ALTER TABLE Members ADD reminded_at TIMESTAMPTZ DEFAULT NULL;