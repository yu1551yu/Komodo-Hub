from __future__ import annotations

from database.connection import connection

DDL = [
    """CREATE TABLE IF NOT EXISTS users (
        id VARCHAR(191) PRIMARY KEY, name VARCHAR(255) NOT NULL, email VARCHAR(320) NOT NULL UNIQUE,
        password_hash VARCHAR(512), role VARCHAR(40) NOT NULL, profile JSON,
        created_at VARCHAR(40), updated_at VARCHAR(40), payload JSON NOT NULL
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS student_profiles (
        user_id VARCHAR(191) PRIMARY KEY, profile JSON NOT NULL,
        CONSTRAINT fk_student_profile_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS teacher_profiles (
        user_id VARCHAR(191) PRIMARY KEY, profile JSON NOT NULL,
        CONSTRAINT fk_teacher_profile_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS organizations (
        id VARCHAR(191) PRIMARY KEY, name VARCHAR(255) NOT NULL, region VARCHAR(255), status VARCHAR(40),
        created_at VARCHAR(40), updated_at VARCHAR(40), payload JSON NOT NULL
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS organization_members (
        id VARCHAR(191) PRIMARY KEY, organization_id VARCHAR(191) NOT NULL, user_id VARCHAR(191) NOT NULL,
        role VARCHAR(40) NOT NULL, status VARCHAR(40) NOT NULL, payload JSON NOT NULL,
        UNIQUE KEY uq_org_member (organization_id,user_id),
        CONSTRAINT fk_org_member_org FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
        CONSTRAINT fk_org_member_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS organization_join_requests (
        id VARCHAR(191) PRIMARY KEY, organization_id VARCHAR(191) NOT NULL, user_id VARCHAR(191) NOT NULL,
        status VARCHAR(40) NOT NULL, payload JSON NOT NULL,
        UNIQUE KEY uq_org_join_request (organization_id,user_id),
        CONSTRAINT fk_join_org FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
        CONSTRAINT fk_join_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS classes (
        id VARCHAR(191) PRIMARY KEY, teacher_id VARCHAR(191) NOT NULL, name VARCHAR(255) NOT NULL,
        access_code VARCHAR(100) UNIQUE, payload JSON NOT NULL,
        CONSTRAINT fk_class_teacher FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS class_memberships (
        id VARCHAR(191) PRIMARY KEY, class_id VARCHAR(191) NOT NULL, student_id VARCHAR(191) NOT NULL,
        joined_at VARCHAR(40), payload JSON NOT NULL, UNIQUE KEY uq_class_student (class_id,student_id),
        CONSTRAINT fk_enrollment_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
        CONSTRAINT fk_enrollment_student FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS school_programs (
        id VARCHAR(191) PRIMARY KEY, teacher_id VARCHAR(191), title VARCHAR(255) NOT NULL,
        status VARCHAR(40), payload JSON NOT NULL,
        CONSTRAINT fk_school_program_teacher FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE SET NULL
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS program_activities (
        id VARCHAR(191) PRIMARY KEY, program_id VARCHAR(191), title VARCHAR(255) NOT NULL,
        status VARCHAR(40), payload JSON NOT NULL,
        CONSTRAINT fk_activity_program FOREIGN KEY (program_id) REFERENCES school_programs(id) ON DELETE CASCADE
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS conservation_programs (
        id VARCHAR(191) PRIMARY KEY, title VARCHAR(255) NOT NULL, status VARCHAR(40), payload JSON NOT NULL
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS program_participation (
        id VARCHAR(191) PRIMARY KEY, program_id VARCHAR(191) NOT NULL, user_id VARCHAR(191) NOT NULL,
        organization_id VARCHAR(191), status VARCHAR(40), payload JSON NOT NULL,
        UNIQUE KEY uq_program_user_org (program_id,user_id,organization_id),
        CONSTRAINT fk_participation_program FOREIGN KEY (program_id) REFERENCES conservation_programs(id) ON DELETE CASCADE,
        CONSTRAINT fk_participation_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_participation_org FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS species (
        id VARCHAR(191) PRIMARY KEY, name VARCHAR(255) NOT NULL, scientific_name VARCHAR(255),
        conservation_status VARCHAR(100), payload JSON NOT NULL
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS contributions (
        id VARCHAR(191) PRIMARY KEY, author_id VARCHAR(191) NOT NULL, organization_id VARCHAR(191),
        title VARCHAR(255) NOT NULL, type VARCHAR(60) NOT NULL, status VARCHAR(40), payload JSON NOT NULL,
        CONSTRAINT fk_contribution_author FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_contribution_org FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS sighting_reports (
        id VARCHAR(191) PRIMARY KEY, reporter_id VARCHAR(191) NOT NULL, species_id VARCHAR(191) NOT NULL,
        organization_id VARCHAR(191), status VARCHAR(40), payload JSON NOT NULL,
        CONSTRAINT fk_sighting_reporter FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_sighting_species FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE RESTRICT,
        CONSTRAINT fk_sighting_org FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS sessions (
        token_hash CHAR(64) PRIMARY KEY, user_id VARCHAR(191) NOT NULL, expires_at VARCHAR(40) NOT NULL,
        CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS app_records (
        collection_name VARCHAR(128) NOT NULL, record_id VARCHAR(191) NOT NULL, position_no INT NOT NULL,
        payload JSON NOT NULL, PRIMARY KEY(collection_name,record_id),
        KEY ix_collection_position(collection_name,position_no)
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS app_documents (
        document_key VARCHAR(128) PRIMARY KEY, payload JSON NOT NULL, updated_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB""",
]


def create_schema() -> None:
    with connection() as conn:
        cursor = conn.cursor()
        for statement in DDL:
            cursor.execute(statement)
        conn.commit()
        cursor.close()
