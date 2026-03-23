# Analytics and dashboard endpoints
Feature: Analytics and Dashboard
  As a lab manager in the lab
  I want to view dashboard statistics and analytics
  So that I can monitor lab operations and make data-driven decisions

  # --- Dashboard ---

  Scenario: Dashboard returns summary statistics
    Given some baseline data exists for analytics
    When I request the dashboard
    Then the dashboard should include total counts
    And the dashboard should include orders_by_status
    And the dashboard should include inventory_by_status

  Scenario: Dashboard on empty database
    When I request the dashboard
    Then the dashboard total_products should be 0
    And the dashboard total_vendors should be 0
    And the dashboard total_orders should be 0

  # --- Spending ---

  Scenario: Spending by vendor
    Given a vendor "SpendVendor" with orders and priced items exists
    When I request spending by vendor
    Then the spending list should not be empty
    And the first vendor should have order_count and total_spend

  Scenario: Spending by month
    When I request spending by month
    Then the spending by month response should be a list

  # --- Inventory analytics ---

  Scenario: Inventory value
    When I request inventory value
    Then the response should include total_value and item_count

  Scenario: Top products
    Given a vendor "TopVendor" with ordered products exists
    When I request top products
    Then the top products list should not be empty

  # --- Order history ---

  Scenario: Order history
    Given a vendor "HistVendor" with 3 orders exists
    When I request order history
    Then the order history should contain at least 3 entries

  # --- Staff activity ---

  Scenario: Staff activity
    When I request staff activity
    Then the staff activity response should be a list

  # --- Vendor summary ---

  Scenario: Vendor summary
    Given a vendor "SummaryVendor" with products and orders exists
    When I request the vendor summary
    Then the summary should include products_supplied and order_count

  Scenario: Vendor summary for non-existent vendor returns 404
    When I request vendor summary for id 99999
    Then the vendor summary response status should be 404

  # --- Document processing stats ---

  Scenario: Document processing stats
    Given 5 documents exist for analytics
    When I request document processing stats via analytics
    Then the analytics doc stats should include total_documents
