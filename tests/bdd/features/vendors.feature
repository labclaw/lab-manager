# Vendor CRUD and relationship management
Feature: Vendor Management
  As a lab manager at Shen Lab
  I want to manage vendors through the full CRUD lifecycle
  So that I can track our suppliers and their products/orders

  # --- Create ---

  Scenario: Create a new vendor with minimal info
    When I create a vendor with name "Fisher Scientific"
    Then the vendor should be created with name "Fisher Scientific"
    And the vendor should have a valid id

  Scenario: Create a vendor with full details
    When I create a vendor with:
      | field   | value                     |
      | name    | Sigma-Aldrich             |
      | website | https://sigmaaldrich.com  |
      | phone   | 1-800-325-3010            |
      | email   | orders@sial.com           |
      | notes   | Preferred chemical vendor |
    Then the vendor should be created with name "Sigma-Aldrich"
    And the vendor website should be "https://sigmaaldrich.com"

  # --- Read ---

  Scenario: Get vendor by id
    Given a vendor "Thermo Fisher" exists in the system
    When I get the vendor by id
    Then I should receive the vendor details
    And the vendor name should be "Thermo Fisher"

  Scenario: Get non-existent vendor returns 404
    When I get vendor with id 99999
    Then the response status should be 404

  # --- List ---

  Scenario: List vendors returns paginated results
    Given the following vendors exist:
      | name              |
      | VWR International |
      | Fisher Scientific |
      | Sigma-Aldrich     |
    When I list all vendors
    Then I should see 3 vendors in the list
    And the response should include pagination info

  Scenario: Search vendors by name
    Given the following vendors exist:
      | name                     |
      | Thermo Fisher Scientific |
      | Fisher Scientific        |
      | Sigma-Aldrich            |
    When I search vendors with query "fisher"
    Then I should see 2 vendors in the list

  # --- Update ---

  Scenario: Update vendor details
    Given a vendor "Old Name Corp" exists in the system
    When I update the vendor name to "New Name Corp"
    Then the vendor name should be "New Name Corp"

  # --- Delete ---

  Scenario: Delete vendor with no references
    Given a vendor "Temporary Vendor" exists in the system
    When I delete the vendor
    Then the delete response status should be 204
    And the vendor should no longer exist

  @requires_postgresql
  Scenario: Delete vendor with linked products returns 409
    Given a vendor "Linked Vendor" exists in the system
    And a product linked to that vendor exists
    When I try to delete the vendor
    Then the response status should be 409

  # --- Linked resources ---

  Scenario: List products for a vendor
    Given a vendor "Bio-Rad" exists in the system
    And 3 products linked to "Bio-Rad" exist
    When I list products for the vendor
    Then I should see 3 products

  Scenario: List orders for a vendor
    Given a vendor "Corning" exists in the system
    And 2 orders linked to "Corning" exist
    When I list orders for the vendor
    Then I should see 2 orders

  # --- Edge cases ---

  Scenario: List vendors when database is empty
    When I list all vendors
    Then I should see 0 vendors in the list

  Scenario: Vendor name with special characters
    When I create a vendor with name "R&D Systems / Bio-Techne"
    Then the vendor should be created with name "R&D Systems / Bio-Techne"
