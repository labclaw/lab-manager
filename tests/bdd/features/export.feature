# CSV export endpoints
Feature: CSV Export
  As a lab manager at Shen Lab
  I want to export data as CSV files
  So that I can share data with collaborators and create reports

  # --- Inventory CSV ---

  Scenario: Export inventory as CSV
    Given some inventory data exists for export
    When I download the inventory CSV
    Then the response should be a CSV file named inventory.csv
    And the CSV should have a header row

  Scenario: Export inventory CSV when empty
    When I download the inventory CSV
    Then the response should be a CSV file named inventory.csv

  # --- Orders CSV ---

  Scenario: Export orders as CSV
    Given some order data exists for export
    When I download the orders CSV
    Then the response should be a CSV file named orders.csv
    And the CSV should have a header row

  # --- Products CSV ---

  Scenario: Export products as CSV
    Given some product data exists for export
    When I download the products CSV
    Then the response should be a CSV file named products.csv
    And the CSV should have a header row

  # --- Vendors CSV ---

  Scenario: Export vendors as CSV
    Given some vendor data exists for export
    When I download the vendors CSV
    Then the response should be a CSV file named vendors.csv
    And the CSV should have a header row

  # --- Security ---

  Scenario: CSV export prevents formula injection
    Given a product exists with name "=SUM(A1:A10)"
    When I download the products CSV
    Then the CSV should escape dangerous characters
    And formula injection should be prevented

  Scenario: CSV handles special characters
    Given a product exists with name "Buffer (10x) - pH 7.4"
    When I download the products CSV
    Then the CSV should properly quote the name
    And special characters should be preserved

  Scenario: CSV handles unicode characters
    Given a vendor exists with name "Bio-Rad™ Laboratories"
    When I download the vendors CSV
    Then unicode characters should be preserved

  # --- Performance ---

  Scenario: Large export performance
    Given 1000 inventory items exist
    When I download the inventory CSV
    Then the response should complete within 10 seconds
    And the CSV should contain 1000 data rows

  # --- Error handling ---

  Scenario: Export without authentication
    Given I am not authenticated
    When I try to download the inventory CSV
    Then the response should be 401 Unauthorized
