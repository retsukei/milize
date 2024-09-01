import psycopg2
import os
from psycopg2 import sql
from psycopg2.extras import NamedTupleCursor

from utils.checks import check_connection

from .groups import Groups
from .series import Series
from .chapters import Chapters
from .jobs import Jobs
from .assignments import Assignments
from .members import Members
from .boardposts import Boardposts
from .subscriptions import Subscriptions

class DatabaseManager:
    def __init__(self, database, host, user, password, port=5432):
        try:
            self.connection = psycopg2.connect(
                database=database,
                host=host,
                user=user,
                password=password,
                port=port
            )
            self.cursor = self.connection.cursor(cursor_factory=NamedTupleCursor)
            self.create_tables()

            self.groups = Groups(self.connection, self.cursor)
            self.series = Series(self.connection, self.cursor)
            self.chapters = Chapters(self.connection, self.cursor)
            self.jobs = Jobs(self.connection, self.cursor)
            self.assignments = Assignments(self.connection, self.cursor)
            self.members = Members(self.connection, self.cursor)
            self.boardposts = Boardposts(self.connection, self.cursor)
            self.subscriptions = Subscriptions(self.connection, self.cursor)

            print("Connected to PostgreSQL.")
        except Exception as e:
            print(f"Failed to connect to PostgreSQL: {e}")
            self.connection = None
            self.cursor = None

    def create_tables(self):
        try:
            with open(f"{os.path.realpath(os.path.dirname(__file__))}/schema.sql", "r") as file:
                schema_sql = file.read()

            self.cursor.execute(schema_sql)
            self.connection.commit()
        except Exception as e:
            print(f"Failed to create tables: {e}")

    @check_connection
    def chapter_job_data(self, chapter_id):
        try:
            query = """
            WITH SeriesJobsDetails AS (
                SELECT
                    sj.series_id,
                    j.job_id,
                    j.job_name,
                    ja.assigned_to,
                    ja.status,
                    c.chapter_id,
                    c.chapter_name
                FROM
                    SeriesJobs sj
                JOIN
                    Jobs j ON sj.job_id = j.job_id
                LEFT JOIN
                    JobsAssignments ja ON j.job_id = ja.job_id
                LEFT JOIN
                    Chapters c ON ja.chapter_id = c.chapter_id
                WHERE
                    c.chapter_id = %s
            )
            SELECT
                job_id,
                job_name,
                assigned_to,
                status
            FROM
                SeriesJobsDetails
            WHERE
                series_id = (SELECT series_id FROM Chapters WHERE chapter_id = %s);
            """

            self.cursor.execute(query, (chapter_id, chapter_id))
            self.connection.commit()
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Failed to recieve job data for chapter ID '{chapter_id}': {e}")
            return None