# Komodo Hub Software Requirements Specification

**Version** V1.1· **Date** 26 September 2026  
**Source**: `06_source_materials/Study case 01_Komodo Hub.pdf` (Yayasan Komodo)

---

## 1. Overview

Komodo Hub is a **national digital conservation platform** initiated by **Yayasan Komodo (Komodo Foundation)** for Indonesian endemic species, serving the public, **schools**, and **community organisations** from remote areas to cities.

**Vision**: Explore, identify, and protect endemic species; educate citizens; mobilise communities; **registered users extend the knowledge base** by sharing species records (case Background).

**This increment**: Web front-end prototype; no production backend.

**Flagship species in the case** (examples): Javan Rhinoceros (Ujung Kulon), Sumatran Tiger, Bali Myna, Javan Eagle, Tarsius, Celebes Crested Macaque.

---

## 2. Case interviews → requirements

| Interviewee | Key needs |
|---|---|
| **Bintang Akbar (teacher)** | Pick platform content + add class material; message students; notes on work and sighting reports; assess progress |
| **Khairunnisa (principal)** | School account; **school library public**, **student profiles not public**; **unique student access code** |
| **Ayu Lestari (school admin)** | Subscription, registration, enrolment (prototype: admin/teacher + access code) |
| **Asnawi (foundation admin)** | Register schools/communities; accounts; **business dashboard** |
| **Tegar (project director)** | **School vs community** visibility rules; ISO 9241-210; scalable cloud; management metrics |
| **Besoeki (#SaveOurAnimals)** | Community library; **public member profiles and contributions**; sightings |
| **Bhaskara (security)** | Children’s data protection end-to-end; RBAC; audit |

---

## 3. Schools vs communities (core case rule)

| | **School** | **Community** |
|---|---|---|
| Public sees | **School library** (anonymised pupil work) | Org page, library, **member profiles & contributions** |
| Not public | **Student profiles** and private class data | — |
| Join pupils | **Unique access code** | Leader approves members |

---

## 4. Roles and portals

Student, Teacher, Public/Guest, Community leader, Foundation Administrator — separate UI after login.

---

## 5–7. Portal summary, FR-01–FR-08, NFR

Same structure as the Chinese SRS: species library for all; moderated observations; school library vs community public pages; class access codes; business dashboard; ISO 9241-210 usability; security per Interview 07.

---

## 8. Prototype traceability

| Case point | Prototype |
|---|---|
| Ujung Raya / teacher | `teacher@komodo.id` (Bintang Akbar) |
| Class access code | Teacher class screen; student registration |
| School library vs student privacy | Guest/Public **School library** |
| Community member pages | Public **Communities & members** |
| #SaveOurAnimals | `community@komodo.id` |
| Foundation superuser | `admin@komodo.id` |
| Demo credentials | Project root `README.md` (not shown on login UI) |

See `04_web_prototype/src/README.md`.
