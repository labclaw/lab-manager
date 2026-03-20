Feature: Edge Cases Documents
  As a system
  I want to handle document edge cases
  So that document processing is robust

  Background:
    Given I am authenticated as "admin"

  Scenario: Empty document upload
    When I upload 0-byte file
    Then upload should fail
    And error should indicate empty file

  Scenario: Document too large
    When I upload 100MB file
    Then upload should fail
    And size limit should be indicated

  Scenario: Unsupported file format
    When I upload .xyz file
    Then upload should fail
    And supported formats should be listed

  Scenario: Corrupted PDF upload
    When I upload corrupted PDF
    Then upload should succeed
    And OCR should fail gracefully
    And document should be flagged

  Scenario: Image with no text
    When I upload blank image
    Then OCR should return empty
    And document should be processable
    And no crash should occur

  Scenario: Multi-page PDF handling
    When I upload 50-page PDF
    Then all pages should be processed
    And progress should be shown

  Scenario: Password-protected PDF
    When I upload encrypted PDF
    Then processing should fail
    And error should indicate protection

  Scenario: Handwritten document
    When I upload handwritten note
    Then OCR should attempt
    And low confidence should be flagged

  Scenario: Document with handwriting and print
    When I upload mixed document
    Then extraction should separate
    And confidence should vary by region

  Scenario: Upside-down image
    When I upload rotated image
    Then auto-rotation should be attempted
    And text should be readable

  Scenario: Low resolution image
    When I upload 72dpi image
    Then OCR should attempt
    And quality warning should be shown

  Scenario: Document with multiple languages
    When I upload bilingual document
    Then both languages should be extracted
    And language should be detected

  Scenario: Document with tables
    When I upload document with tables
    Then table structure should be preserved
    And data should be extractable

  Scenario: Document with stamps/watermarks
    When I upload stamped document
    Then stamps should not confuse extraction
    And main text should be extracted

  Scenario: Document reprocessing
    Given document was already processed
    When I reprocess document
    Then new extraction should be created
    And version history should be maintained

  Scenario: Document deletion during processing
    Given document is being processed
    When I delete document
    Then processing should stop
    And cleanup should occur
