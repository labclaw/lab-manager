Feature: Ask AI Extended
  As a lab manager
  I want to ask natural language questions about my data
  So that I can get insights without learning SQL

  Background:
    Given I am authenticated as "admin"
    And inventory data exists:
      | product   | quantity | location  |
      | PBS       | 100      | Freezer A |
      | Ethanol   | 50       | Cabinet B |
      | Tips      | 500      | Shelf C   |

  Scenario: Ask simple inventory question
    When I ask "How many items do we have in inventory?"
    Then I should receive a natural language answer
    And the answer should mention the total quantity

  Scenario: Ask about specific product
    When I ask "How much PBS do we have?"
    Then I should receive an answer mentioning PBS
    And the quantity should be 100

  Scenario: Ask about low stock
    Given the low stock threshold is 20
    And an item with quantity 10 exists
    When I ask "Which items are low in stock?"
    Then I should receive a list of low stock items

  Scenario: Ask about vendor spending
    Given orders exist for vendors:
      | vendor    | total   |
      | Sigma     | 5000.00 |
      | Fisher    | 3000.00 |
    When I ask "Which vendor did we spend the most with?"
    Then the answer should mention "Sigma"

  Scenario: Ask about expiring items
    Given items expiring:
      | product | expiration_date |
      | Reagent | 2024-04-01      |
      | Buffer  | 2024-05-01      |
    When I ask "What items are expiring soon?"
    Then I should receive a list of expiring items

  Scenario: Ask with invalid query
    When I ask "DELETE FROM inventory"
    Then the query should be rejected
    And an error should be returned

  Scenario: Ask returns fallback to search
    When I ask a question that cannot be converted to SQL
    Then the system should fallback to search
    And I should still receive relevant results

  Scenario: Ask with date range
    When I ask "What orders did we receive this month?"
    Then the answer should be scoped to current month
    And only relevant orders should be included

  Scenario: Ask about order history
    Given orders exist:
      | po_number | date       |
      | PO-001    | 2024-01-15 |
      | PO-002    | 2024-02-20 |
    When I ask "Show me orders from January"
    Then I should see PO-001
    And I should not see PO-002

  Scenario: Ask result pagination
    When I ask a question with many results
    Then the results should be paginated
    And I should be able to request more pages

  Scenario: Ask preserves context
    When I ask "How much PBS do we have?"
    And I ask "And Ethanol?"
    Then the context from the previous question should be used

  Scenario: Ask with aggregation
    When I ask "What is the total value of our inventory?"
    Then I should receive a numeric total
    And the answer should be accurate
