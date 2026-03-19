# Edge cases for document management
Feature: Document Edge Cases
  As a lab manager at Shen Lab
  I want robust error handling for document operations
  So that document data stays consistent and secure

  # --- Not found ---

  Scenario: Get non-existent document returns 404
    When I get document with id 99999
    Then the doc response status should be 404

  # --- Path traversal validation ---

  Scenario: Reject document with path traversal
    When I try to create a document with path "../../etc/passwd"
    Then the doc response status should be 422

  # --- Status validation ---

  Scenario: Reject document with invalid status
    When I try to create a document with invalid status "fake_status"
    Then the doc response status should be 422

  # --- Update ---

  Scenario: Update document fields
    Given a test document exists with status "pending"
    When I update the document vendor_name to "Updated Vendor"
    Then the document should have vendor_name "Updated Vendor"

  # --- Soft delete ---

  Scenario: Delete document soft-deletes
    Given a test document exists with status "pending"
    When I delete the test document
    Then the doc delete response should be 204

  # --- List and filter ---

  Scenario: List documents by document_type
    Given 3 test documents with type "packing_list" exist
    And 2 test documents with type "invoice" exist
    When I list documents with type "packing_list"
    Then I should see 3 documents in the doc list

  Scenario: Search documents by file name
    Given a test document "special_scan_report.jpg" exists
    When I search documents with query "special_scan"
    Then I should see 1 document in the doc list

  # --- Review edge cases ---

  Scenario: Approve document without extracted data creates no order
    Given a test document exists with status "needs_review" and no extracted data
    When I approve the document
    Then the document status should be "approved" after review
    And no order should be created from this document

  # --- Get single document ---

  Scenario: Get document by id
    Given a test document exists with status "approved"
    When I get the test document by id
    Then the doc detail status should be "approved"
