Feature: Export Functionality
  As a lab manager
  I want to export data in various formats
  So that I can analyze data externally and create reports

  Background:
    Given the database is clean
    And I am authenticated

  Scenario: Export inventory to CSV
    Given 50 inventory items exist
    When I export inventory to CSV
    Then the response content type should be "text/csv"
    And CSV should have 51 rows (header + 50 data)
    And CSV should contain columns: name, quantity, location, status

  Scenario: Export inventory with custom columns
    Given 20 inventory items exist
    When I export inventory with columns "name,quantity,expiry_date"
    Then CSV should only contain specified columns

  Scenario: Export inventory filtered by location
    Given 30 inventory items in "Freezer A" exist
    And 20 inventory items in "Freezer B" exist
    When I export inventory filtered by location "Freezer A"
    Then CSV should have 31 rows
    And all items should be from "Freezer A"

  Scenario: Export inventory filtered by status
    Given 25 available inventory items exist
    And 15 expired inventory items exist
    When I export inventory with status "expired"
    Then CSV should have 16 rows

  Scenario: Export orders to CSV
    Given 40 orders exist
    When I export orders to CSV
    Then the response content type should be "text/csv"
    And CSV should have 41 rows

  Scenario: Export orders with date range
    Given 10 orders in January exist
    And 15 orders in February exist
    And 20 orders in March exist
    When I export orders from "2026-02-01" to "2026-02-28"
    Then CSV should have 16 rows

  Scenario: Export orders with vendor filter
    Given 20 orders from "Sigma" exist
    And 30 orders from "Fisher" exist
    When I export orders from vendor "Sigma"
    Then CSV should have 21 rows

  Scenario: Export products to CSV
    Given 100 products exist
    When I export products to CSV
    Then the response content type should be "text/csv"
    And CSV should have 101 rows

  Scenario: Export products with category filter
    Given 30 chemicals exist
    And 40 consumables exist
    When I export products with category "chemicals"
    Then CSV should have 31 rows

  Scenario: Export vendors to CSV
    Given 25 vendors exist
    When I export vendors to CSV
    Then the response content type should be "text/csv"
    And CSV should have 26 rows

  Scenario: Export vendors with active filter
    Given 20 active vendors exist
    And 5 inactive vendors exist
    When I export active vendors
    Then CSV should have 21 rows

  Scenario: Export with pagination
    Given 1000 inventory items exist
    When I export inventory with limit 500
    Then CSV should have 501 rows

  Scenario: Export empty dataset
    Given no inventory items exist
    When I export inventory to CSV
    Then CSV should have 1 row (header only)

  Scenario: Export handles special characters
    Given inventory with name "Chemical <test> & "quotes"" exists
    When I export inventory to CSV
    Then special characters should be properly escaped

  Scenario: Export handles unicode characters
    Given inventory with name "Chemical α-β-γ" exists
    When I export inventory to CSV
    Then CSV should be UTF-8 encoded
    And unicode characters should be preserved

  Scenario: Export handles large numbers
    Given inventory with quantity 999999999 exists
    When I export inventory to CSV
    Then numbers should not be formatted as scientific notation

  Scenario: Export handles null values
    Given inventory with null expiry date exists
    When I export inventory to CSV
    Then null values should be empty strings

  Scenario: Export with sort order
    Given inventory items with names "Zinc", "Alpha", "Beta" exist
    When I export inventory sorted by name ascending
    Then CSV rows should be ordered Alpha, Beta, Zinc

  Scenario: Export with descending sort
    Given inventory items with quantities 10, 20, 30 exist
    When I export inventory sorted by quantity descending
    Then CSV rows should be ordered 30, 20, 10

  Scenario: Export filename format
    When I export inventory to CSV
    Then filename should match pattern "inventory_YYYYMMDD.csv"

  Scenario: Export orders filename format
    When I export orders to CSV
    Then filename should match pattern "orders_YYYYMMDD.csv"

  Scenario: Export with timestamp in filename
    When I export with timestamp option
    Then filename should include time component

  Scenario: Concurrent export requests
    Given 1000 inventory items exist
    When I make 5 concurrent export requests
    Then all requests should succeed
    And all responses should be valid CSV

  Scenario: Export request timeout handling
    Given very large dataset exists
    When export takes longer than timeout
    Then appropriate error should be returned

  Scenario: Export audit log
    Given 50 audit records exist
    When I export audit log to CSV
    Then the response content type should be "text/csv"
    And CSV should contain all audit fields

  Scenario: Export audit log with date filter
    Given audit records across multiple days exist
    When I export audit log for specific date
    Then only records for that date should be included

  Scenario: Export document metadata
    Given 30 documents exist
    When I export document metadata to CSV
    Then CSV should contain document info but not file contents

  Scenario: Export with custom delimiter
    Given 20 items exist
    When I export with delimiter ";"
    Then CSV should use semicolon as delimiter

  Scenario: Export to JSON format
    Given 20 inventory items exist
    When I export inventory to JSON
    Then the response content type should be "application/json"
    And response should be valid JSON array
