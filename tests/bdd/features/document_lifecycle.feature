Feature: Document Lifecycle
  As a lab manager
  I want to manage the full document lifecycle
  So that all documents are properly processed from upload to inventory

  Background:
    Given I am authenticated as "admin"

  Scenario: Full document lifecycle
    Given I upload a document "packing_list.jpg"
    And the document is processed with OCR
    And extraction completes with high confidence
    When I approve the document
    Then the document status should be "reviewed"
    And inventory records should be created
    And the document should be searchable

  Scenario: Document rejection flow
    Given I upload a document "unclear_scan.jpg"
    And the document extraction has low confidence
    When I reject the document with reason "Image too blurry to read"
    Then the document status should be "rejected"
    And rejection reason should be saved
    And no inventory should be created

  Scenario: Document re-extraction after rejection
    Given a rejected document exists
    When I request re-extraction with a different provider
    Then the document status should change to "processing"
    And new extraction results should be generated

  Scenario: Bulk document approval
    Given 10 documents are pending review
    And all documents have confidence above 90%
    When I bulk approve all documents
    Then all 10 documents should have status "reviewed"
    And inventory records should be created for each

  Scenario: Document with duplicate PO detection
    Given an approved document exists with PO number "PO-12345"
    When I upload a new document with PO number "PO-12345"
    Then a duplicate warning should be shown
    And the document should still be processed

  Scenario: Document deletion before review
    Given a pending document exists
    When I delete the document
    Then the document should be marked as deleted
    And the document should not appear in review queue

  Scenario: Document deletion after review
    Given a reviewed document exists
    And inventory was created from the document
    When I delete the document
    Then the document should be marked as deleted
    And existing inventory should NOT be deleted

  Scenario: Document statistics
    Given documents exist:
      | status    | count |
      | pending   | 5     |
      | processing| 2     |
      | reviewed  | 20    |
      | rejected  | 3     |
    When I request document statistics
    Then the response should contain correct counts
    And total should be 30

  Scenario: Document search by vendor
    Given 5 documents from "Sigma-Aldrich" exist
    And 3 documents from "Fisher" exist
    When I search documents for vendor "Sigma-Aldrich"
    Then I should receive 5 documents
    And all should be from "Sigma-Aldrich"

  Scenario: Document pagination
    Given 50 documents exist
    When I request documents page 1 with page size 20
    Then I should receive 20 documents
    And total should be 50
    And page count should be 3

  Scenario: Document filtering by date range
    Given documents uploaded:
      | date       |
      | 2024-01-15 |
      | 2024-02-20 |
      | 2024-03-10 |
    When I filter documents from "2024-02-01" to "2024-03-31"
    Then I should receive 2 documents
