Feature: Concurrent Access
  As a multi-user system
  I want to handle concurrent access safely
  So that data integrity is maintained

  Background:
    Given I am authenticated as "admin"

  Scenario: Simultaneous inventory updates
    Given inventory has 100 units
    When user A updates to 90 units
    And user B updates to 80 units simultaneously
    Then final value should be consistent
    And audit log should show both attempts

  Scenario: Optimistic locking conflict
    Given product has version 1
    When user A updates with version 1
    And user B updates with version 1 simultaneously
    Then one update should succeed
    And other should receive 409 Conflict
    And conflict should include current version

  Scenario: Concurrent order creation
    When 10 users create orders simultaneously
    Then all orders should be created
    And each should have unique PO number

  Scenario: Race condition on stock check
    Given inventory has 10 units
    When 2 users try to reserve 8 units each simultaneously
    Then only one reservation should succeed
    And other should fail with insufficient stock

  Scenario: Database deadlock resolution
    When deadlock occurs between transactions
    Then one transaction should be rolled back
    And retry should be attempted
    And data should remain consistent

  Scenario: Read consistency during updates
    Given product is being updated
    When I read the product during update
    Then I should see consistent data
    And not partial updates

  Scenario: Bulk import concurrent safety
    When 2 imports run simultaneously
    Then both should complete successfully
    Or one should wait for other to finish
    And no data corruption should occur

  Scenario: Session isolation
    Given user has 2 active sessions
    When sessions access same resource
    Then each session should work independently
    And no cross-session pollution

  Scenario: Connection pool exhaustion
    Given connection pool is full
    When new request arrives
    Then request should wait or timeout
    And existing connections should not be affected

  Scenario: Write queue processing
    Given 100 write requests arrive simultaneously
    When queue processes them
    Then all should be processed in order
    And no writes should be lost
