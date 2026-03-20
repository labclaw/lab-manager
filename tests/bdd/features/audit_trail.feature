Feature: Audit Trail
  As a lab manager
  I want to track all changes to records
  So that I can maintain accountability and compliance

  Background:
    Given I am authenticated as "admin"

  Scenario: View audit log for inventory changes
    Given an inventory item was created
    And the quantity was adjusted from 100 to 95
    And the item was consumed 10 units
    When I view audit history for the inventory item
    Then I should see 3 audit entries
    And each entry should have timestamp, user, and action

  Scenario: View audit log for order changes
    Given an order was created
    And the order status changed from "pending" to "shipped"
    And the order status changed from "shipped" to "received"
    When I view audit history for the order
    Then I should see 3 audit entries
    And status changes should be recorded

  Scenario: Audit log shows user attribution
    Given user "scientist" created a vendor
    And user "admin" updated the vendor
    When I view audit history for the vendor
    Then "scientist" should be listed as creator
    And "admin" should be listed as updater

  Scenario: Audit log for document review
    Given a document was uploaded by "tech"
    And the document was reviewed by "scientist"
    When I view audit history for the document
    Then upload action should be attributed to "tech"
    And review action should be attributed to "scientist"

  Scenario: Query audit log by table
    Given audit entries exist for:
      | table     | count |
      | inventory | 10    |
      | orders    | 5     |
      | vendors   | 3     |
    When I query audit log for table "inventory"
    Then I should receive 10 entries
    And all entries should be for inventory records

  Scenario: Audit log pagination
    Given 50 audit entries exist
    When I request audit log page 1 with page size 20
    Then I should receive 20 entries
    And entries should be ordered by timestamp descending

  Scenario: Audit log filtering by date
    Given audit entries on dates:
      | date       |
      | 2024-01-15 |
      | 2024-02-20 |
      | 2024-03-10 |
    When I filter audit log from "2024-02-01" to "2024-03-31"
    Then I should receive 2 entries

  Scenario: Audit log entry detail
    Given an inventory item was adjusted
    When I view the audit entry detail
    Then I should see:
      | field      |
      | timestamp  |
      | user_id    |
      | action     |
      | table_name |
      | record_id  |
      | old_value  |
      | new_value  |

  Scenario: Soft delete audit trail
    Given a vendor was deleted
    When I view audit history for the vendor
    Then a delete action should be recorded
    And the record should still exist in database

  Scenario: Audit log cannot be modified
    Given an audit entry exists
    When I try to update the audit entry
    Then the request should fail
    And audit entries should be immutable
