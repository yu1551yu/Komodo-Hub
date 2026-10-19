# Sprint 1 Week 1 Progress Report

**Komodo Hub – Digital Animal Conservation Platform**  
**Module**: CUH601CMD · **Document type**: Weekly Scrum Report / Sprint 1 Week 1 Increment  
**Sprint**: Sprint 1 · Week 1  
**Version**: 2026-09-26  
**Team repository**: [github.com/liyitong1219/komodo-hub-platform](https://github.com/liyitong1219/komodo-hub-platform/tree/main) (`main` branch)  
**Evidence**: `05_project_management/`, `evidence/<member>/`, Git commits (see repository above), prototype screenshots

---

## 1. Sprint Goal

This week is the project kick-off. The aim is to complete **overall planning, requirements analysis**, and a **demonstrable baseline system framework** for the Komodo Hub digital conservation platform—and to show **Scrum practice, teamwork, requirements work, and project management**.

Specific objectives:

1. Confirm project direction and system positioning;
2. Analyse multi-role user needs and freeze the V1.1 requirements baseline;
3. Complete overall architecture and page-structure planning;
4. Set up the front-end prototype environment (`04_web_prototype/`);
5. Implement basic login/registration and multi-portal navigation;
6. Establish initial student–teacher interaction via **class access codes**.

**Product Goal (Week 1 agreement)**: Support community-based conservation learning—students learn and submit observations safely in school contexts; teachers manage classes and tasks; public and community users contribute; admins review and govern the platform.

---

## 2. Team Activities

### 2.1 Project selection and requirements discussion

The team held a topic-selection discussion and agreed on:

**Komodo Hub – A Digital Platform for Community-Supported Animal Conservation**

Discussion points and outcomes (record in meeting minutes):

| Topic | Summary |
|---|---|
| How students take part in conservation learning | Class tasks, species library, activity sign-up, observation reports (visible to teachers; anonymised in community) |
| How teachers manage learning | Classes, access codes, task publishing, report review, course materials |
| How public users participate | Browse species, submit sightings, comment, favourites, join activities and communities |
| How admins maintain the platform | User and organisation approval, species and content moderation, activity governance |
| Community organisation role | Org home, members, library, activities, post moderation |

**Sprint ceremonies (Week 1)**:

- **Sprint Planning**: Sprint Goal, backlog priority, Definition of Done, role rotation (see `05_project_management/Role_Rotation_and_Evidence.md`)
- **Daily Scrum**: progress, blockers, plan for the day
- **Internal increment demo**: log in per portal, student joins class, teacher views access code

### 2.2 System portals (aligned with prototype)

| Portal | Description |
|---|---|
| Student Portal | Learning, tasks, reports, class messaging, community (privacy-preserving display) |
| Teacher Portal | Classroom management, report review, course materials, tasks and feedback |
| Public User Portal | Species, search, community feed, favourites, activities |
| Community Portal | Organisation operations, members, library, activities, post moderation |
| Admin Portal | Users, organisations, species, moderation queue, activities |
| Guest | Browse species and public activities (read-only) |

---

## 3. Requirement Analysis

This week we completed the functional framework and produced/updated:

- `01_requirements/Komodo_Hub_SRS_CN.md`, `Komodo_Hub_SRS_EN.md` (V1.1, aligned with the case study)
- Use cases and states: observation reports `pending_teacher` / `pending_admin` / `approved` / `rejected`, etc.
- Privacy rules: student **name, class**, and similar fields are **not exposed** on the public community feed (PublicReportView / de-identification)

### 3.1 Student Portal

Main features (Week 1 scope; further split in later sprints):

- Registration and login (students need a **class access code** to register)
- Join a class (at registration or after login with the code)
- Browse species library and public activities
- Learning tasks and submissions (after joining a class)
- Observation report submission (after joining a class; teacher review chain extended in later Sprint 1 weeks)

**Student–teacher linking**:

```
Teacher registers / creates class
        ↓
System generates class access code
        ↓
Student registers (or joins) with access code
        ↓
Student linked to class & teacher
        ↓
Teacher manages class, tasks, and review
```

Demo access code (seed data): `UJUNG-5A-2026` (view/copy/regenerate under teacher **Classroom**).

### 3.2 Teacher Portal

Main features:

- Teacher registration (grade and class; in the demo, admin approval may be required before login)
- After login: create/manage class, view and share access code
- Publish tasks and course materials (pages and local data flow in prototype)
- Entry point for reviewing class student reports

Relationship model:

```
Teacher → Class → Students
```

### 3.3 Other roles (Week 1 analysis scope)

- **Public**: species, reports, comments, favourites, activities, join community organisations  
- **Community**: org home, members, library, activities, post moderation  
- **Admin**: users, organisation approval, species, global moderation and activities  

---

## 4. Front-end Framework Development

### 4.1 Multi-role page structure

Single-page-style prototype (Vanilla JS) with role-based navigation and views:

```
Komodo Hub
├── Guest / Public browse
├── Student Portal
├── Teacher Portal
├── Public User Portal
├── Community Portal
└── Admin Portal
```

Entry: `04_web_prototype/index.html`. Modules: `store.js` (data), `auth.js` (session and navigation), `views.js` (views), `app.js` (events and modals).

Baseline layout: fixed left sidebar + main content area on the right.

### 4.2 Authentication UI

- **Login**: email + password; guest browse; reset demo data  
- **Register**: tabs — Public / Student / Teacher  
  - **Student**: class access code, student ID, full name, date of birth, email, password, etc.  
  - **Teacher**: name, email, password, school name (optional), grade, class (registration creates demo class and access-code logic)  

Demo accounts: see root `README.md` (not shown on the login page, per demo security practice).

---

## 5. Basic Functional Implementation

### 5.1 Student–teacher registration and class join

| Role | Behaviour |
|---|---|
| Teacher | Register → (after approval) login → classroom → view/copy/regenerate access code |
| Student | Enter code when registering → bound to class and teacher; if not in a class, tasks/reports/messages are gated with prompts |

These flows were validated in the prototype using local data.

### 5.2 User registration and local persistence

After successful registration (Public / Student / Teacher), the new account is **written immediately** to this browser’s **localStorage** (key `komodo_hub_v1_4`, `users` array) via `KOMODO_STORE.save()`:

| Registration type | Also updated locally |
|---|---|
| Public | New user, `favorites` init; auto sign-in (session in `sessionStorage`) |
| Student | New user, class `studentIds`, `learningProgress` |
| Teacher | New user (`accountStatus: pending`), new `classes` row and generated access code |

After refresh or closing the tab, you can sign in again with the **same browser**, email, and password. Data stays on **this device only** (no sync to other machines). **Reset demo data** on the login page restores seed data and **removes** locally registered accounts.

Implementation: `04_web_prototype/src/auth.js` (`register` / `registerStudent` / `registerTeacher`), `store.js` (`save` / `load`).

### 5.3 Other local data (prototype phase)

Classes, access codes, tasks, reports, activities, species, and other runtime data live in the same `localStorage` blob; the active session uses **sessionStorage**.

**Purpose**: fast validation of flows and UI/permission boundaries.  
**Later sprints**: database design, backend API, secure authentication and password hashing.

---

## 6. Web Function Analysis

The team drafted an initial split of the full product backlog:

| Role | Later focus |
|---|---|
| Student | Dashboard, learning progress, activity participation, reports and tasks end-to-end |
| Teacher | Class insights, course publishing, assignment grading and feedback |
| Public | Search, favourites, activity sign-up, community interaction |
| Admin | Moderation policy, audit log, content and user governance |
| Community | Library, activity operations, members and muting |

The team will continue refining these features in upcoming weeks.

---

## 7. Team Collaboration

**Collaboration repository**: [https://github.com/liyitong1219/komodo-hub-platform/tree/main](https://github.com/liyitong1219/komodo-hub-platform/tree/main) — requirements, Sprint records, prototype code, and commit history are traced in this repo.

### 7.1 Roles and contributions (Week 1)

Fill in names and evidence links per your team agreement. The table below reflects our Week 1 structure.

| Member | Sprint 1 Week 1 role | Main contribution |
|---|---|---|
| Li Yitong | Product Owner / coordination | Project kick-off, facilitated requirements discussions, backlog priority, aligned teacher portal and class-join flow |
| Li Yitong | Scrum Master | Planning/daily scrum notes, Definition of Done, evidence checklist |
| All members | Architect | Use cases/state flows, privacy boundaries, module split |
| All members | Database | Initial entities, report/class relationship modelling |
| Li Yitong | Web | Prototype shell, login/registration, multi-portal navigation |

Because this was the first week of the project, not all members were fully available. **Most Week 1 deliverables were completed by Li Yitong**, with the group participating in discussions and suggestions; **work will be divided more evenly from Week 2 onward**.

Everyone contributed to: topic selection, user-story discussion, page-flow input, and test-scenario ideas.

---

## 8. Next Sprint Plan (Sprint 1 · Week 2 and beyond)

Suggested focus for Week 2:

**Student / Teacher**

- Deepen student dashboard and learning resources  
- Teacher class student list and task-publishing loop  
- Report review → admin moderation status linkage  

**Engineering**

- Test scenarios and screenshots (S1-05)  
- Requirements–implementation traceability matrix update (S1-06)  
- Initial database table design and migration plan  
