# Deployment readiness — guards against regressions found during DO App Platform deploy
Feature: Deployment Readiness
  As a lab administrator
  I want the app to survive real-world deployment conditions
  So that the system stays available on managed platforms like DigitalOcean App Platform

  Background:
    Given a Lab Manager instance with auth enabled

  # === Health check ===

  Scenario: Health endpoint returns ok with all service statuses
    When I request the health endpoint
    Then the response status should be 200
    And the response JSON "status" should be "ok"
    And the health response should include service statuses for "postgresql", "meilisearch", "llm", "disk"

  Scenario: Health check succeeds when meilisearch is down
    Given meilisearch is unreachable
    When I request the health endpoint
    Then the response status should be 200
    And the response JSON "status" should be "ok"
    And the health service "meilisearch" should be "error"
    And the health service "postgresql" should be "ok"

  # === Auth allowlist (public endpoints) ===

  Scenario Outline: Public endpoints are accessible without authentication
    When I request "<path>" without authentication
    Then the response status should not be 401

    Examples:
      | path               |
      | /                  |
      | /api/health        |
      | /api/v1/setup/status|
      | /api/v1/config     |
      | /favicon.svg       |
      | /icons.svg         |
      | /sw.js             |
      | /manifest.json     |

  # === Auth blocks protected endpoints ===

  Scenario Outline: Protected API endpoints require authentication
    When I request "<path>" without authentication
    Then the response status should be 401

    Examples:
      | path               |
      | /api/v1/vendors/   |
      | /api/v1/products/  |
      | /api/v1/orders/    |

  # === Frontend resilience ===

  Scenario: App starts even when dist/assets does not exist
    Given the SPA build artifacts do not exist
    When I create the app
    Then the app should start successfully
    And the root path should serve an HTML page

  Scenario: SPA mode is active when dist/assets exists
    Given the SPA build artifacts exist
    When I create the app
    Then the app should be in SPA mode

  Scenario: Legacy mode serves static/index.html when dist/assets is missing
    Given the SPA build artifacts do not exist
    When I create the app
    Then the app should be in legacy mode

  # === Legacy frontend login page ===

  Scenario: Root path returns HTML page when auth is enabled
    When I request "/" without authentication
    Then the response status should not be 401
    And the response content type should contain "text/html"

  # === Setup flow on fresh deployment ===

  Scenario: Fresh deployment returns needs_setup true
    Given no admin user exists
    When I request "/api/setup/status" without authentication
    Then the response status should be 200
    And the response JSON "needs_setup" should be true

  Scenario: Completing setup creates admin account
    Given no admin user exists
    When I complete setup with name "Dr. Smith" email "admin@example.com" and password "labclaw2026"
    Then the response status should be 200
    And the response JSON "status" should be "ok"
    And the setup status should indicate setup is no longer needed

  # === Proxy headers ===

  @wip
  Scenario: Admin URLs use correct scheme behind reverse proxy
    Given the app is behind a reverse proxy with HTTPS
    When I access an admin page with header "X-Forwarded-Proto" set to "https"
    Then all links in the response should use the "https" scheme

  # === Database schema ===

  Scenario: Tables are created under labmanager schema on PostgreSQL
    Given a PostgreSQL database is available
    When the database migrations are applied
    Then tables should exist in the "labmanager" search path
    And the "staff" table should be queryable
