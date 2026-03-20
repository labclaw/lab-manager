Feature: Vendor Management
  As a lab manager
  I want to manage vendor information
  So that I can track suppliers and place orders

  Background:
    Given the database is clean
    And I am authenticated

  Scenario: Create vendor with all fields
    When I create vendor with:
      | name        | Sigma-Aldrich           |
      | contact     | sales@sigmaaldrich.com  |
      | phone       | +1-800-123-4567         |
      | address     | 123 Main St, St Louis   |
      | website     | https://sigmaaldrich.com|
    Then the response status should be 201
    And vendor name should be "Sigma-Aldrich"

  Scenario: Create vendor with minimal fields
    When I create vendor with:
      | name | New Vendor |
    Then the response status should be 201

  Scenario: Create vendor with duplicate name
    Given vendor "Sigma-Aldrich" exists
    When I create vendor with name "Sigma-Aldrich"
    Then the response status should be 409

  Scenario: Create vendor without name
    When I create vendor without name
    Then the response status should be 422

  Scenario: Get vendor by ID
    Given vendor with ID "vendor-123" exists
    When I request vendor "vendor-123"
    Then the response status should be 200
    And vendor ID should be "vendor-123"

  Scenario: Get non-existent vendor
    When I request vendor "non-existent-id"
    Then the response status should be 404

  Scenario: List all vendors
    Given 20 vendors exist
    When I request all vendors
    Then the response should contain 20 vendors

  Scenario: List vendors with pagination
    Given 50 vendors exist
    When I request vendors with page 1 and page_size 10
    Then the response should contain 10 vendors
    And total count should be 50

  Scenario: Search vendors by name
    Given vendors "Sigma-Aldrich", "Fisher Scientific", "VWR" exist
    When I search vendors for "Sigma"
    Then only "Sigma-Aldrich" should be returned

  Scenario: Filter active vendors
    Given 15 active vendors exist
    And 5 inactive vendors exist
    When I request active vendors
    Then the response should contain 15 vendors

  Scenario: Update vendor name
    Given vendor with name "Old Name" exists
    When I update vendor name to "New Name"
    Then vendor name should be "New Name"

  Scenario: Update vendor contact
    Given vendor with contact "old@email.com" exists
    When I update vendor contact to "new@email.com"
    Then vendor contact should be "new@email.com"

  Scenario: Deactivate vendor
    Given active vendor exists
    When I deactivate the vendor
    Then vendor status should be "inactive"

  Scenario: Reactivate vendor
    Given inactive vendor exists
    When I reactivate the vendor
    Then vendor status should be "active"

  Scenario: Delete vendor with no orders
    Given vendor with no orders exists
    When I delete the vendor
    Then the response status should be 204
    And the vendor should no longer exist

  Scenario: Cannot delete vendor with orders
    Given vendor with existing orders exists
    When I try to delete the vendor
    Then the response status should be 400

  Scenario: Get vendor products
    Given vendor "Sigma" with 10 products exists
    When I request products for vendor "Sigma"
    Then the response should contain 10 products

  Scenario: Get vendor products with pagination
    Given vendor with 25 products exists
    When I request vendor products with page 1 and page_size 10
    Then the response should contain 10 products

  Scenario: Get vendor orders
    Given vendor "Fisher" with 15 orders exists
    When I request orders for vendor "Fisher"
    Then the response should contain 15 orders

  Scenario: Vendor order history
    Given vendor with orders across multiple months exists
    When I request vendor order history
    Then orders should be ordered by date descending

  Scenario: Vendor spending summary
    Given vendor with orders totaling $5000 exists
    When I request vendor spending summary
    Then total spending should be $5000

  Scenario: Vendor performance metrics
    Given vendor with order history exists
    When I request vendor metrics
    Then average delivery time should be included
    And order success rate should be included

  Scenario: Add vendor note
    Given vendor exists
    When I add note "Preferred vendor for antibodies"
    Then note should be added to vendor
    And note should have timestamp

  Scenario: Get vendor notes
    Given vendor with 3 notes exists
    When I request vendor notes
    Then response should contain 3 notes

  Scenario: Vendor with special characters
    When I create vendor with name "O'Brien & Sons"
    Then vendor name should be "O'Brien & Sons"

  Scenario: Vendor with unicode name
    When I create vendor with name "Müller Lab Supplies"
    Then vendor name should be preserved correctly

  Scenario: Vendor contact validation
    When I create vendor with invalid email "not-an-email"
    Then the response status should be 422

  Scenario: Vendor phone validation
    When I create vendor with invalid phone "abc123"
    Then the response status should be 422

  Scenario: Vendor website validation
    When I create vendor with invalid website "not-a-url"
    Then the response status should be 422

  Scenario: Bulk vendor import
    Given CSV with 10 vendors
    When I import vendors from CSV
    Then 10 vendors should be created
    And import report should show success

  Scenario: Bulk import with errors
    Given CSV with 5 valid and 2 invalid vendors
    When I import vendors from CSV
    Then 5 vendors should be created
    And 2 errors should be reported

  Scenario: Export vendors
    Given 25 vendors exist
    When I export vendors to CSV
    Then the response content type should be "text/csv"
    And CSV should have 26 rows

  Scenario: Vendor address format
    Given vendor with multi-line address exists
    When I request vendor details
    Then address should be formatted correctly

  Scenario: Vendor payment terms
    Given vendor with payment terms "Net 30" exists
    When I request vendor details
    Then payment terms should be "Net 30"

  Scenario: Set vendor as preferred
    Given vendor exists
    When I set vendor as preferred
    Then vendor should be marked preferred
    And vendor should appear first in lists

  Scenario: Remove preferred status
    Given preferred vendor exists
    When I remove preferred status
    Then vendor should not be marked preferred
