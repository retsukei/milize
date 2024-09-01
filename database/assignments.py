from utils.checks import check_connection
from utils.constants import JobStatus

class Assignments:
    def __init__(self, connection, cursor):
        self.connection = connection
        self.cursor = cursor

    @check_connection
    def new(self, chapter_id, series_job_id, user_id):
        try:
            self.cursor.execute("INSERT INTO jobsassignments (chapter_id, series_job_id, assigned_to) VALUES (%s, %s, %s) ON CONFLICT (chapter_id, series_job_id) DO NOTHING RETURNING assignment_id;", (chapter_id, series_job_id, user_id))
            self.connection.commit()

            assignment = self.cursor.fetchone()
            
            if assignment:
                return assignment[0]

            return None
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to assign for series job with ID '{series_job_id}' to user '{user_id}': {e}")
            return None

    @check_connection
    def get_by_user(self, user_id):
        try:
            self.cursor.execute("SELECT assignment_id, chapter_id, series_job_id, assigned_to, status, created_at, completed_at, reminded_at FROM jobsassignments WHERE assigned_to = %s", (user_id,))
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get job assignments for user '{user_id}': {e}")
            return None

    @check_connection
    def get_by_user_uncompleted(self, user_id):
        try:
            self.cursor.execute("SELECT assignment_id, chapter_id, series_job_id, assigned_to, status, created_at, completed_at, reminded_at FROM jobsassignments WHERE assigned_to = %s AND status != 2", (user_id,))
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get job assignments for user '{user_id}': {e}")
            return None

    @check_connection
    def get_completed_by_user(self, user_id):
        try:
            self.cursor.execute("SELECT assignment_id, chapter_id, series_job_id, assigned_to, status, created_at, completed_at FROM jobsassignments WHERE assigned_to = %s AND status = %s", (user_id, JobStatus.Completed))
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get completed job assignments for user '{user_id}': {e}")
            return None

    @check_connection
    def get_by_user_archive(self, user_id):
        try:
            self.cursor.execute("SELECT assignment_id, chapter_id, series_job_id, assigned_to, status, created_at, completed_at FROM JobsAssignmentsArchive WHERE assigned_to = %s", (user_id,))
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get job assignments from archive for user '{user_id}': {e}")
            return None

    @check_connection
    def get_completed_by_user_archive(self, user_id):
        try:
            self.cursor.execute("SELECT assignment_id, chapter_id, series_job_id, assigned_to, status, created_at, completed_at FROM JobsAssignmentsArchive WHERE assigned_to = %s AND status = %s", (user_id, JobStatus.Completed))
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get completed job assignments from archive for user '{user_id}': {e}")
            return None

    @check_connection
    def get(self, chapter_id, series_job_id):
        try:
            self.cursor.execute("SELECT assignment_id, chapter_id, series_job_id, assigned_to, status, created_at, completed_at FROM jobsassignments WHERE chapter_id = %s AND series_job_id = %s", (chapter_id, series_job_id))
            self.connection.commit()
            return self.cursor.fetchone()
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to get job assignment for chapter id '{chapter_id}': {e}")
            return None
        
    @check_connection
    def delete(self, chapter_id, series_job_id):
        try:
            self.cursor.execute("DELETE FROM jobsassignments WHERE chapter_id = %s AND series_job_id = %s", (chapter_id, series_job_id))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to delete job assignment for chapter id '{chapter_id}': {e}")
            return None

    @check_connection
    def update_status(self, chapter_id, series_job_id, status):
        try:
            if status == JobStatus.Completed:
                self.cursor.execute("UPDATE jobsassignments SET status = %s, completed_at = CURRENT_TIMESTAMP WHERE chapter_id = %s AND series_job_id = %s", (status, chapter_id, series_job_id))
            else:
                self.cursor.execute("UPDATE jobsassignments SET status = %s WHERE chapter_id = %s AND series_job_id = %s", (status, chapter_id, series_job_id))

            self.cursor.execute("UPDATE jobsassignments SET status = %s WHERE chapter_id = %s AND series_job_id = %s", (status, chapter_id, series_job_id))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to update job status for chapter id '{chapter_id}': {e}")
            return None

    @check_connection
    def update_user(self, assignment_id, user_id):
        try:
            self.cursor.execute("UPDATE jobsassignments SET assigned_to = %s WHERE assignment_id = %s", (user_id, assignment_id))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to update user for assignment '{assignment_id}': {e}")
            return None

    @check_connection
    def is_first(self, user_id):
        try:
            query = """
            SELECT COUNT(*) FROM (
                SELECT assignment_id FROM JobsAssignments WHERE assigned_to = %s
                UNION ALL
                SELECT assignment_id FROM JobsAssignmentsArchive WHERE assigned_to = %s
            ) AS combined_jobs;
            """
            self.cursor.execute(query, (user_id, user_id))
            self.connection.commit()
            return self.cursor.fetchone()[0] == 0
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to check if first job: {e}")
            return None

    @check_connection
    def update_reminder(self, assignment_id):
        try:
            self.cursor.execute("UPDATE jobsassignments SET reminded_at = CURRENT_TIMESTAMP WHERE assignment_id = %s", (assignment_id,))
            self.connection.commit()
            return self.cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            print(f"Failed to update reminder for assignment '{assignment_id}': {e}")
            return None