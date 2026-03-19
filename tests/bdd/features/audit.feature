# Audit log query and record history endpoints
Feature: Audit Log
  As a lab manager at Shen Lab
  I want to query audit logs and view change history
  So that I can track who changed what and when

  # --- List audit logs ---

  Scenario: List audit logs returns paginated results
    When I list audit logs
    Then the audit response should include pagination info
    And the audit response should be successful

  Scenario: List audit logs with table filter
    When I list audit logs filtered by table "vendors"
    Then the audit response should be successful

  # --- Record history ---

  Scenario: Get record history for a specific entity
    When I get audit history for table "vendors" record 1
    Then the audit response should be successful
    And the audit response should include pagination info
