Feature: Document Workflow Management
  As a lab manager
  I want to manage document processing workflow
  So that all documents are properly reviewed and tracked

  Background:
    Given the database is clean
    And I am authenticated

  Scenario: Upload document with valid image
    When I upload a document "packing_list.jpg" with content type "image/jpeg"
    Then the response status should be 201
    And the document should have status "pending"

  Scenario: Upload document with invalid file type
    When I upload a document "malware.exe" with content type "application/octet-stream"
    Then the response status should be 422
    And the error message should contain "unsupported file type"

  Scenario: Upload document exceeding size limit
    When I upload a document "large.pdf" with size 60000000
    Then the response status should be 413

  Scenario: List documents with pagination
    Given 25 documents exist
    When I request documents with page 1 and page_size 10
    Then the response should contain 10 documents
    And total count should be 25
    And page count should be 3

  Scenario: Filter documents by status
    Given 5 documents with status "pending" exist
    And 3 documents with status "approved" exist
    When I request documents with status "pending"
    Then the response should contain 5 documents

  Scenario: Get document by ID
    Given a document exists with ID "doc-123"
    When I request document "doc-123"
    Then the response status should be 200
    And the document ID should be "doc-123"

  Scenario: Get non-existent document
    When I request document "non-existent-id"
    Then the response status should be 404

  Scenario: Review document with approval
    Given a document exists with status "pending"
    When I approve the document with notes "Verified correct"
    Then the document status should be "approved"
    And review notes should be "Verified correct"

  Scenario: Review document with rejection
    Given a document exists with status "pending"
    When I reject the document with reason "Invalid vendor"
    Then the document status should be "rejected"
    And review notes should contain "Invalid vendor"

  Scenario: Cannot review already reviewed document
    Given a document exists with status "approved"
    When I try to review the document
    Then the response status should be 400

  Scenario: Get document statistics
    Given 10 documents with status "pending" exist
    And 20 documents with status "approved" exist
    And 5 documents with status "rejected" exist
    When I request document statistics
    Then pending count should be 10
    And approved count should be 20
    And rejected count should be 5

  Scenario: Delete pending document
    Given a document exists with status "pending"
    When I delete the document
    Then the response status should be 204
    And the document should no longer exist

  Scenario: Cannot delete approved document
    Given a document exists with status "approved"
    When I try to delete the document
    Then the response status should be 400

  Scenario: Upload document with duplicate filename
    Given a document "invoice.pdf" already exists
    When I upload another document "invoice.pdf"
    Then the response status should be 201
    And the second document should have a different filename

  Scenario: Search documents by vendor name
    Given documents from vendors "Sigma", "Fisher", "VWR" exist
    When I search documents for vendor "Sigma"
    Then only documents from "Sigma" should be returned

  Scenario: Get documents needing review
    Given 7 documents with extraction confidence below 0.8 exist
    When I request documents needing review
    Then the response should contain 7 documents

  Scenario: Batch update document status
    Given 10 documents with status "pending" exist
    When I batch update 5 documents to status "approved"
    Then 5 documents should have status "approved"
    And 5 documents should have status "pending"

  Scenario: Document with OCR failure
    Given a document with unreadable content exists
    When the document is processed
    Then OCR status should be "failed"
    And an alert should be created

  Scenario: Document with extraction error
    Given a document with extraction error exists
    When I request the document details
    Then extraction status should be "error"
    And error message should be present

  Scenario: Document processing time tracking
    Given a document was uploaded 5 minutes ago
    When I request the document
    Then processing duration should be recorded

  Scenario: Document with multiple pages
    When I upload a multi-page PDF document
    Then all pages should be processed
    And page count should be accurate
