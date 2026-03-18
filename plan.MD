# Current Plan

**Task Summary:** Design and provide a codebase for a dormitory room reservation/booking system.
**Task Type:** mixed
**Execution Mode:** multi_agent
**Recommended Agent Count:** 4

## Planning Rationale
- A single agent risks missing critical aspects (race conditions, domain rules, security, test coverage).
- Four agents cleanly separate architecture/domain, implementation, and verification without redundancy.
- Keeps below the 5-agent cap while enabling parallel progress and independent review.

## Agents

### agent_1 - System Architect (Domain + API Designer)
- Category: specialist
- Purpose: Define requirements, core domain model, booking rules, and external interfaces to guide implementation.
- Mandatory: True
- Parallelizable: False
- Responsibilities:
  - Elicit/assume and document functional requirements (search, availability, booking, cancel, admin management).
  - Define domain entities and relationships (Dorm, Building, Room, Bed, User, Reservation, Policy).
  - Specify booking/availability rules (date ranges, check-in/out, overlaps, capacity, holds, cancellations).
  - Design API surface (REST endpoints, request/response schemas, errors) and roles (student/admin).
  - Define non-functional requirements (concurrency control, audit logs, rate limiting, observability).
- Outputs:
  - Architecture spec (components, data flow)
  - Domain model + constraints
  - API specification (endpoint list + schemas)
  - Concurrency and consistency approach
- Dependencies: None

### agent_2 - Backend Implementer (API + Persistence)
- Category: generalist
- Purpose: Build the working codebase for the reservation system per the architecture: backend services, database schema, and runnable project structure.
- Mandatory: True
- Parallelizable: False
- Responsibilities:
  - Choose a practical stack (e.g., FastAPI/Node/Nest/Spring) and create repository layout.
  - Implement authentication/authorization (JWT/session) and role-based access control.
  - Implement core endpoints: rooms listing, availability query, create reservation, cancel, admin CRUD.
  - Design and apply DB schema/migrations (PostgreSQL recommended).
  - Implement overlap prevention using transactions and constraints (e.g., exclusion constraints or serializable txn).
  - Add input validation, error handling, and idempotency where appropriate.
- Outputs:
  - Complete backend codebase (source tree)
  - Database migrations/schema
  - Configuration examples (.env.sample)
  - Minimal run instructions
- Dependencies: agent_1

### agent_3 - Quality Engineer (Tests + Verification)
- Category: verifier
- Purpose: Validate correctness, prevent regressions, and ensure concurrency/edge cases are covered with tests and review.
- Mandatory: True
- Parallelizable: True
- Responsibilities:
  - Create automated tests (unit + integration) for booking flows and edge cases (overlap, boundary dates, cancellation).
  - Add concurrency test or simulation to attempt double-booking and verify protection.
  - Review API responses for consistency (status codes, error formats).
  - Check schema constraints and migration correctness.
  - Provide a verification report and required fixes list.
- Outputs:
  - Test suite added to repo
  - Verification report (pass/fail + gaps)
  - Recommended fixes/patch list
- Dependencies: agent_1, agent_2

### agent_4 - DevOps/Packaging (Local Deploy + Docs)
- Category: specialist
- Purpose: Make the codebase easy to run and evaluate with reproducible environments and concise documentation.
- Mandatory: True
- Parallelizable: True
- Responsibilities:
  - Add Docker Compose for app + database (and migrations on startup).
  - Provide Makefile/scripts for common tasks (run, test, migrate, seed).
  - Add concise README with setup, environment variables, and example API calls.
  - Optional: add OpenAPI/Swagger publishing and seed data.
- Outputs:
  - docker-compose.yml and Dockerfiles (if needed)
  - Run/test scripts
  - README documentation
- Dependencies: agent_2, agent_3

## Execution Plan
- Order: agent_1, agent_2, agent_3, agent_4
- Merge Strategy: Agent_2 owns the main branch; agent_3 and agent_4 deliver patches/PRs merged after review. Resolve conflicts by prioritizing correctness (tests) over convenience (docs), then update docs accordingly.

## Verification Strategy
- Needed: True
- Integration tests for reservation lifecycle (create/cancel/list).
- Edge-case tests: overlapping ranges, same-day boundaries, invalid dates, capacity limits.
- Concurrency simulation: two parallel requests attempting to book the same room/bed.
- Security review: role enforcement and auth checks on admin endpoints.
- Schema verification: constraints and indexes support the rules and performance basics.

## Stop Conditions
- Repository contains runnable backend, DB migrations, tests, and documentation.
- All critical tests pass including overlap/concurrency prevention.
- API matches the spec and supports booking, cancellation, and admin room management.
- No unresolved high-risk verification findings remain (overbooking, auth bypass).
