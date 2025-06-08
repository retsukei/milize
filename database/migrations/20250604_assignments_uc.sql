ALTER TABLE JobsAssignments
ADD CONSTRAINT jobsassignments_chapter_series_assigned_to UNIQUE (chapter_id, series_job_id, assigned_to);